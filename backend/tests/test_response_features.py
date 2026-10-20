# 作者：LHF。
# 时间：2026-10-20。
# 作用：离线验证思考解析、工具偏好与执行后的追问，禁止真实模型调用。
import asyncio
import json

import httpx
import pytest

from app.llm import ModelFailure, OpenAIModel
from app.runtime import DomainError
from app.schemas import MessageRequest, ModelReply, SteeringRequest, ToolCall
from app.storage import uid
from tests.test_runtime import send, terminal

PROFILE = {"base_url": "https://fixture.invalid/v1", "model": "fixture"}


def test_think_tags_split_at_every_character_and_unclosed_reasoning():
    # 作用：验证逐字分片的 think 标签正确解析，未闭合思考不泄漏到正文。
    from app.response_parser import ReasoningParser

    parser = ReasoningParser()
    fragments = [piece for char in "<think>先计算</think>答案是2" for piece in parser.push(char)]
    fragments.extend(parser.finish())
    assert "".join(text for kind, text in fragments if kind == "reasoning") == "先计算"
    assert "".join(text for kind, text in fragments if kind == "text") == "答案是2"
    parser = ReasoningParser()
    assert parser.push("<think>尚未结束") + parser.finish() == [("reasoning", "尚未结束")]


@pytest.mark.parametrize("field", ["reasoning_content", "reasoning"])
async def test_native_reasoning_nonstreaming_is_separate_from_answer(field):
    # 作用：验证非流式响应的独立思考字段与答案分离。
    def respond(request):
        # 作用：构造假 HTTP 响应并检查请求参数，用于非流式响应的独立思考字段与答案分离。
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "<think>标签思考</think>答案", field: "独立思考"},
                         "finish_reason": "stop"}],
        })

    reply = await OpenAIModel(httpx.MockTransport(respond)).complete(PROFILE, [], None, None, 5)
    assert reply.text == "答案"
    assert reply.reasoning == "独立思考标签思考"


async def test_streaming_reasoning_tool_arguments_and_auto_tool_choice():
    # 作用：验证流式思考、工具参数和自动工具选择可同时处理。
    def respond(request):
        # 作用：构造假 HTTP 响应并检查请求参数，用于流式思考、工具参数和显式工具选择可同时处理。
        payload = json.loads(request.content)
        assert payload["tool_choice"] == "auto"
        deltas = [
            {"reasoning_content": "先算"}, {"content": "<thi"}, {"content": "nk>再核对</th"},
            {"content": "ink>开始计算", "tool_calls": [{"index": 0, "id": "c1", "type": "function",
              "function": {"name": "calculator", "arguments": '{"expression":'}}]},
            {"tool_calls": [{"index": 0, "function": {"arguments": '"1+1"}'}}]},
        ]
        chunks = [{"choices": [{"index": 0, "delta": delta,
                   "finish_reason": "tool_calls" if index == len(deltas) - 1 else None}]}
                  for index, delta in enumerate(deltas)]
        return httpx.Response(200, text="".join("data: " + json.dumps(c) + "\n\n" for c in chunks)
                              + "data: [DONE]\n\n", headers={"content-type": "text/event-stream"})

    text, reasoning = [], []

    async def on_text(value):
        # 作用：收集模型输出的正文片段，供测试检查拼接结果。
        text.append(value)

    async def on_reasoning(value):
        # 作用：收集模型输出的思考片段，供测试检查独立展示。
        reasoning.append(value)

    reply = await OpenAIModel(httpx.MockTransport(respond)).complete(
        PROFILE, [], [{"type": "function", "function": {"name": "calculator", "parameters": {}}}],
        None, 5, on_text, on_reasoning=on_reasoning,
    )
    assert reply.text == "开始计算" == "".join(text)
    assert reply.reasoning == "先算再核对" == "".join(reasoning)
    assert reply.calls[0].arguments == '{"expression":"1+1"}'


async def test_runtime_persists_reasoning_and_emits_it_separately(harness):
    # 作用：验证 Runtime 保存思考元数据，并广播独立思考事件。
    rt, model, client, session, _ = harness
    model.replies = [ModelReply(text="答案", reasoning="模型返回的思考")]
    run = await send(rt, client, session)
    assert (await terminal(rt, run["id"]))["status"] == "completed"
    rows = await rt.db.list("message", parent=session["id"])
    assert rows[-1]["reasoning"] == "模型返回的思考"
    assert rows[-1]["message"]["content"] == "答案"
    events = await rt.db.history_events("A")
    assert any(e["type"] == "model.reasoning.delta" for e in events)


async def test_selected_tool_preference_and_results_feed_followup(harness):
    # 作用：验证工具偏好进入模型上下文，实际工具结果仍用于后续回答。
    rt, model, client, session, _ = harness
    model.replies = [ModelReply(calls=[ToolCall(id="chosen", name="calculator",
                      arguments='{"expression":"6*7"}')]), ModelReply(text="42")]
    run = await rt.submit(session["id"], "A", MessageRequest(
        client_id=client.id, request_id=uid(), content="@calculator 计算6*7", tool_names=["calculator"],
    ))
    assert (await terminal(rt, run["id"]))["status"] == "completed"
    assert "用户希望优先考虑使用这些工具，但不强制调用" in model.inputs[0][-1]["content"]
    rows = await rt.db.list("message", parent=session["id"])
    assert rows[0]["message"]["content"] == "@calculator 计算6*7"
    assert rows[0]["tool_names"] == ["calculator"]
    assert "42" in json.dumps(model.inputs[1])


async def test_unknown_selected_tool_is_rejected_before_queuing(harness):
    # 作用：验证未知工具在任务入队前就被拒绝。
    rt, _, client, session, _ = harness
    with pytest.raises(DomainError, match="未知工具"):
        await rt.submit(session["id"], "A", MessageRequest(
            client_id=client.id, request_id=uid(), content="测试", tool_names=["shell"],
        ))
    assert not await rt.db.list("run", parent=session["id"])


async def test_missing_tool_parameters_allow_clarification(harness):
    # 作用：验证信息不足时模型可以先提问，不会因未调用提及工具而失败。
    rt, model, client, session, _ = harness
    model.replies = [ModelReply(text="请提供需要计算的表达式。")]
    run = await rt.submit(session["id"], "A", MessageRequest(
        client_id=client.id, request_id=uid(), content="计算", tool_names=["calculator"],
    ))
    result = await terminal(rt, run["id"])
    assert result["status"] == "completed"
    assert result["tool_calls"] == 0
    assert "信息或必要参数不足时，先向用户澄清" in model.inputs[0][-1]["content"]


async def test_reasoning_only_failure_is_not_retried_and_is_preserved(harness):
    # 作用：验证仅返回思考后断流也不自动重试，已收到内容仍保留。
    rt, model, client, session, waits = harness

    async def complete(profile, messages, tools, max_tokens, timeout, on_text=None,
                       on_reasoning=None):
        # 作用：模拟思考输出后断流，用于仅返回思考后断流也不自动重试，已收到内容仍保留。
        await on_reasoning("已产生的思考")
        raise ModelFailure("断流", True)

    model.complete = complete
    run = await send(rt, client, session)
    assert (await terminal(rt, run["id"]))["status"] == "failed"
    assert waits == []
    rows = await rt.db.list("message", parent=session["id"])
    assert rows[-1]["reasoning"] == "已产生的思考"


async def test_multiple_mentions_allow_a_different_tool_order(harness):
    # 作用：验证多个偏好去重，模型可以先执行后提及的工具并跳过其余工具。
    rt, model, client, session, _ = harness
    model.replies = [
        ModelReply(calls=[ToolCall(id="todo", name="todo", arguments='{"action":"add","title":"4"}')]),
        ModelReply(text="已记入待办"),
    ]
    run = await rt.submit(session["id"], "A", MessageRequest(
        client_id=client.id, request_id=uid(), content="计算并记录",
        tool_names=["calculator", "todo", "calculator"],
    ))
    assert (await terminal(rt, run["id"]))["status"] == "completed"
    assert "工具：calculator、todo。" in model.inputs[0][-1]["content"]
    assert (await rt.db.get(run["id"]))["tool_names"] == ["calculator", "todo"]
    assert len(await rt.db.list("todo", owner="A")) == 1


async def test_tool_preference_allows_other_tools(harness):
    # 作者：LHF；时间：2026-10-20；作用：验证模型可以使用未被 @ 提及的适用工具。
    rt, model, client, session, _ = harness
    model.replies = [
        ModelReply(calls=[ToolCall(id="other", name="calculator", arguments='{"expression":"2+3"}')]),
        ModelReply(text="5"),
    ]
    run = await rt.submit(session["id"], "A", MessageRequest(
        client_id=client.id, request_id=uid(), content="@search 计算2+3", tool_names=["search"],
    ))
    assert (await terminal(rt, run["id"]))["status"] == "completed"
    assert "工具：search。" in model.inputs[0][-1]["content"]
    assert "5" in json.dumps(model.inputs[1])


async def test_direct_steering_mentions_allow_clarification(harness):
    # 作者：LHF；时间：2026-10-20；作用：验证运行中引导保留工具偏好，允许先询问缺失信息。
    rt, model, client, session, _ = harness
    entered, release = asyncio.Event(), asyncio.Event()

    async def block(messages, on_text):
        # 作用：暂停首轮响应，确保引导在任务运行期间提交。
        entered.set()
        await release.wait()
        return ModelReply(text="初稿")

    model.replies = [block, ModelReply(text="请提供待办内容。")]
    run = await send(rt, client, session)
    await asyncio.wait_for(entered.wait(), 2)
    await rt.steer(run["id"], "A", SteeringRequest(
        content="@todo 帮我记录", request_id=uid(), tool_names=["todo"],
    ))
    release.set()
    result = await terminal(rt, run["id"])
    assert result["status"] == "completed"
    assert result["tool_calls"] == 0
    assert "工具：todo。" in model.inputs[1][-1]["content"]
    rows = await rt.db.list("message", parent=session["id"])
    steering = next(row for row in rows if row["input_kind"] == "steering")
    assert steering["message"]["content"] == "@todo 帮我记录"
    assert steering["tool_names"] == ["todo"]


async def test_queued_mentions_survive_conversion_to_steering(harness):
    # 作用：验证排队消息转为引导后保留工具选择，原任务不再执行。
    rt, model, client, session, _ = harness
    entered, release = asyncio.Event(), asyncio.Event()

    async def block(messages, on_text):
        # 作用：阻塞模拟模型直至测试释放或取消，用于排队消息转为引导后保留工具选择，原任务不再执行。
        entered.set()
        await release.wait()
        return ModelReply(text="初稿")

    model.replies = [block, ModelReply(calls=[ToolCall(
        id="steered-calc", name="calculator", arguments='{"expression":"2+3"}',
    )]), ModelReply(text="5")]
    first = await send(rt, client, session)
    await asyncio.wait_for(entered.wait(), 2)
    queued = await rt.submit(session["id"], "A", MessageRequest(
        client_id=client.id, request_id=uid(), content="@calculator 计算2+3", tool_names=["calculator"],
    ))
    item = await rt.steer_queued(queued["id"], "A")
    assert item["tool_names"] == ["calculator"]
    release.set()
    assert (await terminal(rt, first["id"]))["status"] == "completed"
    assert "本条消息的工具偏好" not in json.dumps(model.inputs[0], ensure_ascii=False)
    assert "工具：calculator。" in model.inputs[1][-1]["content"]
    assert (await rt.db.get(queued["id"]))["reason"] == "converted_to_steering"


def test_tool_catalog_comes_from_registry_and_requires_valid_demo_user(tmp_path):
    # 作用：验证工具列表来自注册表，接口拒绝无效演示身份。
    from fastapi.testclient import TestClient

    from app.llm import ScriptedModel
    from app.main import create_app

    with TestClient(create_app(str(tmp_path / "catalog.db"), ScriptedModel([]))) as client:
        response = client.get("/api/tools")
        assert response.status_code == 200
        assert {item["name"] for item in response.json()} == {"calculator", "search", "todo"}
        assert all(item["description"] for item in response.json())
        assert client.get("/api/tools", headers={"X-Demo-User": "other"}).status_code == 400

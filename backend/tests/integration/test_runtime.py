# 作者：LHF；时间：2026-10-23；作用：验证工具执行预算与不完整输出的安全边界。

import json

import pytest

from app.context import tool_groups
from app.llm import ModelFailure
from app.runtime import Client
from app.schemas import ModelReply, ToolCall
from app.storage import uid
from tests.support.runtime import send, terminal


async def test_direct_answer(harness):
    # 作者：LHF；时间：2026-10-23；作用：普通回答无需工具，且文本实际保存。
    rt, model, client, session, _ = harness
    model.replies = [ModelReply(text="你好，毛毛")]
    run = await send(rt, client, session)
    result = await terminal(rt, run["id"])
    assert result["status"] == "completed" and result["tool_calls"] == 0
    assert result["model_calls"] == 1
    assert (await rt.db.list("message", parent=session["id"]))[-1]["message"]["content"] == "你好，毛毛"


async def test_single_tool_result_feeds_answer(harness):
    # 作者：LHF；时间：2026-10-23；作用：一次工具执行结果必须进入后续真实上下文。
    rt, model, client, session, _ = harness
    model.replies = [
        ModelReply(calls=[ToolCall(id="calc", name="calculator", arguments='{"expression":"6*7"}')]),
        ModelReply(text="42"),
    ]
    run = await send(rt, client, session, "请用计算器计算6*7")
    result = await terminal(rt, run["id"])
    assert result["status"] == "completed" and result["model_calls"] == 2
    tool_message = next(message for message in model.inputs[1] if message["role"] == "tool")
    assert tool_message["tool_call_id"] == "calc"
    assert json.loads(tool_message["content"])["result"]["result"] == "42"


async def test_multiple_tools_then_followup(harness):
    # 作者：LHF；时间：2026-10-23；作用：计算后写待办并追问，工具结果全程可用。
    rt, model, client, session, _ = harness
    model.replies = [
        ModelReply(calls=[ToolCall(id="calc", name="calculator", arguments='{"expression":"128*36"}')]),
        ModelReply(calls=[ToolCall(id="todo", name="todo", arguments='{"action":"add","title":"结果4608"}')]),
        ModelReply(text="已记下4608"),
        ModelReply(text="刚才的结果是4608"),
    ]
    run = await send(rt, client, session, "计算128*36并记为待办")
    result = await terminal(rt, run["id"])
    assert result["status"] == "completed" and result["tool_calls"] == 2
    assert "4608" in json.dumps(model.inputs[1])
    assert len([m for m in model.inputs[2] if m["role"] == "tool"]) == 2
    assert [row["title"] for row in await rt.db.list("todo", owner="A")] == ["结果4608"]
    follow = await send(rt, client, session, "刚才结果是多少？")
    assert (await terminal(rt, follow["id"]))["status"] == "completed"
    assert "4608" in json.dumps(model.inputs[3])


async def test_conversation_followup_and_session_isolation(harness):
    # 作者：LHF；时间：2026-10-23；作用：两客户端的会话分别保留历史，追问不串会话。
    rt, model, client, first, _ = harness
    other_client = Client(uid(), "A", connected=True)
    rt.clients[other_client.id] = other_client
    second = await rt.create_session("A", "窗口二")
    model.replies = [
        ModelReply(text="已记住"),
        ModelReply(text="已记住"),
        ModelReply(text="blue-whale-731"),
        ModelReply(text="red-fox-862"),
    ]
    steps = [
        (client, first, "记住代号blue-whale-731"),
        (other_client, second, "记住代号red-fox-862"),
        (client, first, "刚才代号是什么？"),
        (other_client, second, "刚才代号是什么？"),
    ]
    for actor, session, content in steps:
        run = await send(rt, actor, session, content)
        assert (await terminal(rt, run["id"]))["status"] == "completed"
    first_input, second_input = json.dumps(model.inputs[2]), json.dumps(model.inputs[3])
    assert "blue-whale-731" in first_input and "red-fox-862" not in first_input
    assert "red-fox-862" in second_input and "blue-whale-731" not in second_input


async def test_model_round_limit_stops_tool_loop(harness):
    # 作者：LHF；时间：2026-10-23；作用：连续工具请求达到模型轮次上限后停止，不执行剩余回复。
    rt, model, client, session, _ = harness
    settings = (await rt.settings()).model_copy(update={"max_model_calls": 2})
    await rt.db.put("settings", {"id": "runtime-settings", **settings.model_dump()})
    model.replies = [
        ModelReply(calls=[ToolCall(id=f"c{i}", name="calculator", arguments='{"expression":"1+1"}')])
        for i in range(3)
    ]
    run = await send(rt, client, session)
    result = await terminal(rt, run["id"])
    assert result["status"] == "limited" and result["model_calls"] == 2
    assert result["tool_calls"] == 2 and len(model.inputs) == 2 and len(model.replies) == 1
    assert len([e for e in await rt.db.history_events("A") if e["type"] == "tool.started"]) == 2


async def test_model_failure_is_not_success(harness):
    # 作者：LHF；时间：2026-10-23；作用：不可重试模型错误落为失败，不保存虚假成功回答。
    rt, model, client, session, waits = harness
    model.replies = [ModelFailure("离线模拟连接失败")]
    run = await send(rt, client, session)
    result = await terminal(rt, run["id"])
    assert result["status"] == "failed" and "连接失败" in result["reason"]
    assert result["model_calls"] == 1 and waits == []


@pytest.mark.parametrize(
    "name,arguments,code",
    [
        ("unknown", "{}", "unknown_tool"),
        ("calculator", '{"expression":"1/0"}', "invalid_expression"),
        ("todo", '{"action":"add"}', "validation_error"),
    ],
)
async def test_tool_error_returns_to_model(harness, name, arguments, code):
    # 作者：LHF；时间：2026-10-23；作用：未知工具、执行错误及非法参数以明确结果回传模型。
    rt, model, client, session, _ = harness
    model.replies = [
        ModelReply(calls=[ToolCall(id="bad", name=name, arguments=arguments)]),
        ModelReply(text="工具失败，未完成操作"),
    ]
    run = await send(rt, client, session)
    assert (await terminal(rt, run["id"]))["status"] == "completed"
    message = next(m for m in model.inputs[1] if m["role"] == "tool")
    outcome = json.loads(message["content"])
    assert outcome["ok"] is False and outcome["error"]["code"] == code
    assert await rt.db.list("todo", owner="A") == []


async def test_blank_answer_fails(harness):
    # 作者：LHF；时间：2026-10-23；作用：没有工具调用的空白回答不能误报任务成功。
    rt, model, client, session, _ = harness
    model.replies = [ModelReply(text="   ")]
    run = await send(rt, client, session)
    assert (await terminal(rt, run["id"]))["status"] == "failed"


async def test_trace_records_tools_and_redacts_credentials(harness):
    # 作者：LHF；时间：2026-10-23；作用：验证模型、工具和任务事件可配对并排除密钥。
    rt, model, client, session, _ = harness
    model.replies = [
        ModelReply(calls=[ToolCall(id="trace-calc", name="calculator", arguments='{"expression":"6*7"}')]),
        ModelReply(text="42"),
    ]
    run = await send(rt, client, session)
    await terminal(rt, run["id"])
    events = [
        event for event in await rt.db.history_events("A", session["id"]) if event["run_id"] == run["id"]
    ]
    assert any(event["type"] == "model.started" for event in events)
    started = next(event["data"] for event in events if event["type"] == "tool.started")
    finished = next(event["data"] for event in events if event["type"] == "tool.finished")
    assert started["call_id"] == finished["call_id"] == "trace-calc"
    assert started["name"] == "calculator" and json.loads(started["arguments"])["expression"] == "6*7"
    assert finished["ok"] is True and finished["result"]["result"] == "42"
    assert [event for event in events if event["type"] == "run.updated"][-1]["data"]["status"] == "completed"
    assert "test-secret-not-for-events" not in json.dumps(events)


async def test_partial_output_failure_is_not_retried(harness):
    # 作用：验证已输出部分正文后失败不重试，部分内容仍保存。
    rt, model, client, session, waits = harness

    async def partial(messages, on_text):
        # 作用：输出一段正文后抛出可重试错误，用于检查部分输出不重试。
        await on_text("部分输出")
        raise ModelFailure("流失败", True)

    model.replies = [partial, ModelReply(text="不应重试")]
    run = await send(rt, client, session)
    assert (await terminal(rt, run["id"]))["status"] == "failed"
    assert waits == []
    rows = await rt.db.list("message", parent=session["id"])
    assert "部分输出" in rows[-1]["message"]["content"]


async def test_truncated_tool_response_is_never_executed(harness):
    # 作用：验证被截断的工具参数不会产生写入或其他工具执行。
    rt, model, client, session, _ = harness
    model.replies = [
        ModelReply(
            finish_reason="length",
            calls=[ToolCall(id="cut", name="todo", arguments='{"action":"add","title":"不应该创建"}')],
        ),
        ModelReply(text="请重试"),
    ]
    run = await send(rt, client, session)
    result = await terminal(rt, run["id"])
    assert result["status"] == "failed" and "length" in result["reason"]
    assert result["model_calls"] == 1 and len(model.replies) == 1
    assert await rt.db.list("todo", owner="A") == []
    rows = await rt.db.list("message", parent=session["id"])
    tool_groups([r["message"] for r in rows])


async def test_tool_budget_blocks_entire_batch(harness):
    # 作用：验证工具预算不足时整批拒绝执行，不部分执行后超额。
    rt, model, client, session, _ = harness
    settings = (await rt.settings()).model_copy(update={"max_tool_calls": 1})
    await rt.db.put("settings", {"id": "runtime-settings", **settings.model_dump()})
    model.replies = [
        ModelReply(
            calls=[
                ToolCall(id="a", name="calculator", arguments='{"expression":"1+1"}'),
                ToolCall(id="b", name="todo", arguments='{"action":"add","title":"不要创建"}'),
            ]
        )
    ]
    run = await send(rt, client, session)
    assert (await terminal(rt, run["id"]))["status"] == "limited"
    assert await rt.db.list("todo", owner="A") == []

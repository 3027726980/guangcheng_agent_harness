# 作者：LHF。
# 时间：2026-10-20。
# 作用：以假 HTTP 传输复现 DeepSeek 思考模式的 400 约束，不调用真实供应商。
import json

import httpx
import pytest

from app.llm import ModelFailure, OpenAIModel
from app.schemas import MessageRequest
from app.storage import uid
from app.tools import ToolRegistry
from tests.test_runtime import send, terminal

PROFILE = {"base_url": "https://api.deepseek.com/v1", "model": "deepseek-flash",
           "reasoning_effort": "max", "api_key": "fixture-key"}


@pytest.mark.parametrize("effort", [None, "max", "none"])
async def test_deepseek_tools_keep_thinking_and_use_auto_choice(effort):
    """有无思考均自动选择并保留所有工具，不注入强制调用指令。"""
    def respond(request):
        """验证实际 SDK 发出的 JSON，模拟供应商在首轮拒绝强制工具的行为。"""
        body = json.loads(request.content)
        assert body["tool_choice"] == "auto"
        assert {t["function"]["name"] for t in body["tools"]} == {"calculator", "search", "todo"}
        assert body["messages"] == [{"role": "user", "content": "计算"}]
        if effort != "none":
            if body.get("tool_choice") != "auto":
                return httpx.Response(400, json={"error": {
                    "message": "Thinking mode does not support this tool_choice",
                    "type": "invalid_request_error", "param": "tool_choice",
                }})
            assert body["thinking"] == {"type": "enabled"}
        else:
            assert body["thinking"] == {"type": "disabled"}
        assert "reasoning_effort" not in body
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"},
                                                     "finish_reason": "stop"}]})

    result = await OpenAIModel(httpx.MockTransport(respond)).complete(
        {**PROFILE, "reasoning_effort": effort}, [{"role": "user", "content": "计算"}],
        ToolRegistry().schemas(), None, 5,
    )
    assert result.text == "OK"


async def test_deepseek_native_reasoning_survives_tool_loop_and_next_user_turn(harness):
    """完整循环必须回传原始思考，且不能混入从正文标签中提取的展示文本。"""
    rt, _, client, session, _ = harness
    profile = await rt.db.get("profile")
    await rt.db.put("profile", {**profile, **PROFILE})
    requests = []

    def respond(request):
        """模拟两轮工具请求及一次用户追问，缺少思考字段即返回 400。"""
        body = json.loads(request.content)
        requests.append(body)
        assistants = [m for m in body["messages"] if m["role"] == "assistant"]
        if any("reasoning_content" not in message for message in assistants):
            return httpx.Response(400, json={"error": {"message": "reasoning_content must be passed back"}})
        if len(requests) == 1:
            if body.get("tool_choice") != "auto":
                return httpx.Response(400, json={"error": {"message": "Thinking mode does not support this tool_choice"}})
            delta = {"reasoning_content": "原始协议思考", "content": "<think>展示标签</think>",
                     "tool_calls": [{"index": 0, "id": "calc1", "type": "function",
                                     "function": {"name": "calculator", "arguments": '{"expression":"6*7"}'}}]}
            finish = "tool_calls"
        else:
            assert assistants[0]["reasoning_content"] == "原始协议思考"
            if len(requests) == 3:
                assert assistants[1]["reasoning_content"] == "回答思考"
            delta = {"reasoning_content": "回答思考", "content": "42"}
            finish = "stop"
        chunk = {"choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
        return httpx.Response(200, text="data: " + json.dumps(chunk) + "\n\ndata: [DONE]\n\n",
                              headers={"content-type": "text/event-stream"})

    rt.model = OpenAIModel(httpx.MockTransport(respond))
    run = await rt.submit(session["id"], "A", MessageRequest(
        client_id=client.id, request_id=uid(), content="@calculator 计算6*7", tool_names=["calculator"],
    ))
    assert (await terminal(rt, run["id"]))["status"] == "completed"
    rows = await rt.db.list("message", parent=session["id"])
    assert rows[1]["reasoning"] == "原始协议思考展示标签"
    assert rows[1]["message"]["reasoning_content"] == "原始协议思考"
    followup = await send(rt, client, session, "刚才结果是多少")
    assert (await terminal(rt, followup["id"]))["status"] == "completed"
    assert len(requests) == 3


async def test_old_saved_reasoning_is_replayed_without_mutating_legacy_records(harness):
    """兼容此前仅保存展示思考的会话，回放时补字段但不改写旧数据库记录。"""
    rt, model, client, session, _ = harness
    profile = await rt.db.get("profile")
    await rt.db.put("profile", {**profile, **PROFILE})
    legacy = {"id": uid(), "run_id": "old", "reasoning": "旧记录思考",
              "message": {"role": "assistant", "content": "旧回答"}}
    await rt.db.put("message", legacy, owner="A", parent=session["id"])

    from app.schemas import ModelReply

    model.replies = [ModelReply(text="继续回答")]
    run = await send(rt, client, session)
    assert (await terminal(rt, run["id"]))["status"] == "completed"
    assert model.inputs[0][1]["reasoning_content"] == "旧记录思考"
    assert "reasoning_content" not in (await rt.db.get(legacy["id"]))["message"]


@pytest.mark.parametrize("field", ["tool_choice", "reasoning_content"])
async def test_known_400_has_actionable_hint_without_raw_provider_secrets(field):
    """识别已知参数错误，但不泄漏供应商响应中可能出现的密钥。"""
    def respond(request):
        """返回包含伪密钥的错误正文以检查固定提示的脱敏边界。"""
        return httpx.Response(400, json={"error": {
            "message": f"Invalid {field}; credential=fixture-secret-must-not-appear",
            "type": "invalid_request_error",
        }})

    with pytest.raises(ModelFailure) as caught:
        await OpenAIModel(httpx.MockTransport(respond)).complete(PROFILE, [], None, None, 5)
    assert field in str(caught.value)
    assert "fixture-secret" not in str(caught.value)
    assert not caught.value.retryable


@pytest.mark.parametrize("content", ["", "原始思考"])
async def test_nonstream_native_reasoning_is_not_replaced_by_display_tags(content):
    """非流式也区分空协议字段与缺失，不将标签内容混入原生回传字段。"""
    def respond(request):
        """以最小响应验证协议文本与展示文本各自的内容。"""
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
            "content": "<think>仅用于展示</think>答案", "reasoning_content": content,
        }}]})

    reply = await OpenAIModel(httpx.MockTransport(respond)).complete(PROFILE, [], None, None, 5)
    assert reply.reasoning_content == content
    assert reply.reasoning == content + "仅用于展示"
    assert reply.text == "答案"


def test_compatibility_check_does_not_match_a_similar_untrusted_host():
    """供应商适配仅匹配真实域名，不匹配同名模型或相似 URL。"""
    from app.model_protocol import deepseek_thinking

    assert not deepseek_thinking({**PROFILE, "base_url": "https://api.deepseek.com.example.invalid"})

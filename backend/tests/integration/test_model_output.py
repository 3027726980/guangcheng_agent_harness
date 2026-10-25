# 作者：LHF；时间：2026-10-23；作用：验证 SDK 响应解析与 Runtime 思考保存。

import json

import httpx
import pytest

from app.llm import OpenAIModel
from app.schemas import ModelReply
from tests.support.runtime import send, terminal

PROFILE = {"base_url": "https://fixture.invalid/v1", "model": "fixture"}


@pytest.mark.parametrize("field", ["reasoning_content", "reasoning"])
async def test_native_reasoning_nonstreaming_is_separate_from_answer(field):
    # 作用：验证非流式响应的独立思考字段与答案分离。
    def respond(request):
        # 作用：构造假 HTTP 响应并检查请求参数，用于非流式响应的独立思考字段与答案分离。
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": "<think>标签思考</think>答案", field: "独立思考"},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

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
            {"reasoning_content": "先算"},
            {"content": "<thi"},
            {"content": "nk>再核对</th"},
            {
                "content": "ink>开始计算",
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "calculator", "arguments": '{"expression":'},
                    }
                ],
            },
            {"tool_calls": [{"index": 0, "function": {"arguments": '"1+1"}'}}]},
        ]
        chunks = [
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": delta,
                        "finish_reason": "tool_calls" if index == len(deltas) - 1 else None,
                    }
                ]
            }
            for index, delta in enumerate(deltas)
        ]
        return httpx.Response(
            200,
            text="".join("data: " + json.dumps(c) + "\n\n" for c in chunks) + "data: [DONE]\n\n",
            headers={"content-type": "text/event-stream"},
        )

    text, reasoning = [], []

    async def on_text(value):
        # 作用：收集模型输出的正文片段，供测试检查拼接结果。
        text.append(value)

    async def on_reasoning(value):
        # 作用：收集模型输出的思考片段，供测试检查独立展示。
        reasoning.append(value)

    reply = await OpenAIModel(httpx.MockTransport(respond)).complete(
        PROFILE,
        [],
        [{"type": "function", "function": {"name": "calculator", "parameters": {}}}],
        None,
        5,
        on_text,
        on_reasoning=on_reasoning,
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

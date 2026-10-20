# 作者：LHF。
# 时间：2026-10-20。
# 作用：验证 test_llm 所覆盖的行为与边界，使用离线数据及临时资源。
import json

import httpx
import pytest

from app.llm import ModelFailure, OpenAIModel

PROFILE = {"base_url": "https://fixture.invalid/v1", "api_key": "fake-only", "model": "fixture"}


async def test_actual_sdk_streaming_arguments_and_text():
    # 作用：验证实际 SDK 能拼接流式工具参数，并分别交付回答文本。
    def respond(request):
        # 作用：构造假 HTTP 响应并检查请求参数，用于实际 SDK 能拼接流式工具参数，并分别交付回答文本。
        payload = json.loads(request.content)
        assert payload["model"] == "fixture" and payload["stream"] is True
        chunks = [
            {
                "id": "x",
                "object": "chat.completion.chunk",
                "created": 0,
                "model": "fixture",
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "content": "计算",
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call1",
                                    "type": "function",
                                    "function": {"name": "calculator", "arguments": '{"expression":'},
                                }
                            ],
                        },
                        "finish_reason": None,
                    }
                ],
            },
            {
                "id": "x",
                "object": "chat.completion.chunk",
                "created": 0,
                "model": "fixture",
                "choices": [
                    {
                        "index": 0,
                        "delta": {"tool_calls": [{"index": 0, "function": {"arguments": '"1+1"}'}}]},
                        "finish_reason": "tool_calls",
                    }
                ],
            },
        ]
        body = (
            "".join("data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n" for chunk in chunks)
            + "data: [DONE]\n\n"
        )
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    output = []

    async def on_text(text):
        # 作用：收集模型输出的正文片段，供测试检查拼接结果。
        output.append(text)

    reply = await OpenAIModel(httpx.MockTransport(respond)).complete(
        PROFILE, [{"role": "user", "content": "计算"}], [], 100, 5, on_text
    )
    assert reply.calls[0].arguments == '{"expression":"1+1"}'
    assert reply.calls[0].id == "call1"
    assert reply.text == "计算" and output == ["计算"]


async def test_sdk_rate_limit_classified_without_hidden_retries():
    # 作用：验证 429 被标记可重试且遵循 Retry-After，SDK 不自行额外重试。
    requests = []

    def respond(request):
        # 作用：构造假 HTTP 响应并检查请求参数，用于 429 被标记可重试且遵循 Retry-After，SDK 不自行额外重试。
        requests.append(request)
        return httpx.Response(
            429,
            json={"error": {"message": "limited", "type": "rate_limit_error"}},
            headers={"retry-after": "45"},
        )

    with pytest.raises(ModelFailure) as caught:
        await OpenAIModel(httpx.MockTransport(respond)).complete(
            PROFILE, [{"role": "user", "content": "x"}], None, 20, 5
        )
    assert caught.value.retryable and caught.value.retry_after == 45
    assert len(requests) == 1


async def test_stream_without_finish_marker_fails():
    # 作用：验证流缺少完成标记时明确失败，避免执行不完整输出。
    def respond(request):
        # 作用：构造假 HTTP 响应并检查请求参数，用于流缺少完成标记时明确失败，避免执行不完整输出。
        return httpx.Response(200, text="data: [DONE]\n\n", headers={"content-type": "text/event-stream"})

    async def output(text):
        # 作用：接收模拟输出，供测试观察事件发送或流错误。
        pass

    with pytest.raises(ModelFailure):
        await OpenAIModel(httpx.MockTransport(respond)).complete(
            PROFILE, [{"role": "user", "content": "x"}], None, 20, 5, output
        )


async def test_completion_token_parameter_and_reasoning_configuration():
    # 作用：验证输出上限参数名及思考开关按配置发送，不再传递思考强度。
    def respond(request):
        # 作用：构造假 HTTP 响应并检查实际请求中的思考开关和输出参数。
        payload = json.loads(request.content)
        assert payload["max_completion_tokens"] == 64
        assert "max_tokens" not in payload
        assert payload["thinking"] == {"type": "enabled"}
        assert "reasoning_effort" not in payload
        return httpx.Response(
            200,
            json={
                "id": "test",
                "object": "chat.completion",
                "created": 0,
                "model": "fixture",
                "choices": [
                    {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "OK"}}
                ],
            },
        )

    profile = {**PROFILE, "output_token_parameter": "max_completion_tokens", "thinking_enabled": True}
    reply = await OpenAIModel(httpx.MockTransport(respond)).complete(
        profile, [{"role": "user", "content": "x"}], None, 64, 5
    )
    assert reply.text == "OK"


async def test_answer_can_use_provider_default_output_and_report_actual_usage():
    # 作用：验证不指定固定输出上限时仍能取得供应商实际用量。
    def respond(request):
        # 作用：构造假 HTTP 响应并检查请求参数，用于不指定固定输出上限时仍能取得供应商实际用量。
        payload = json.loads(request.content)
        assert "max_tokens" not in payload
        assert "max_completion_tokens" not in payload
        return httpx.Response(
            200,
            json={
                "id": "test",
                "object": "chat.completion",
                "created": 0,
                "model": "fixture",
                "choices": [
                    {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "OK"}}
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 7, "total_tokens": 27},
            },
        )

    reply = await OpenAIModel(httpx.MockTransport(respond)).complete(
        PROFILE, [{"role": "user", "content": "x"}], None, None, 5
    )
    assert reply.usage["completion_tokens"] == 7


@pytest.mark.parametrize("capacity,source", [(8192, "provider:context_length"), (None, "default:256K")])
async def test_profile_probe_reads_capacity_or_falls_back(capacity, source):
    # 作用：验证连接探测读取供应商容量，缺失时采用带来源标记的默认容量。
    def respond(request):
        # 作用：构造假 HTTP 响应并检查请求参数，用于连接探测读取供应商容量，缺失时采用带来源标记的默认容量。
        if request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "id": "test",
                    "object": "chat.completion",
                    "created": 0,
                    "model": "fixture",
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": "OK"},
                        }
                    ],
                },
            )
        data = {"id": "fixture"}
        if capacity:
            data["context_length"] = capacity
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [data]})
        return httpx.Response(200, json=data)

    result = await OpenAIModel(httpx.MockTransport(respond)).probe(PROFILE)
    assert result["context_capacity"] == (capacity or 262144)
    assert result["capacity_source"] == source

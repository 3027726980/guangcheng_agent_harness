import json

import httpx
import pytest

from app.llm import ModelFailure, OpenAIModel

PROFILE = {"base_url": "https://fixture.invalid/v1", "api_key": "fake-only", "model": "fixture"}


async def test_actual_sdk_streaming_arguments_and_text():
    def respond(request):
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
        output.append(text)

    reply = await OpenAIModel(httpx.MockTransport(respond)).complete(
        PROFILE, [{"role": "user", "content": "计算"}], [], 100, 5, on_text
    )
    assert reply.calls[0].arguments == '{"expression":"1+1"}'
    assert reply.calls[0].id == "call1"
    assert reply.text == "计算" and output == ["计算"]


async def test_sdk_rate_limit_classified_without_hidden_retries():
    requests = []

    def respond(request):
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
    def respond(request):
        return httpx.Response(200, text="data: [DONE]\n\n", headers={"content-type": "text/event-stream"})

    async def output(text):
        pass

    with pytest.raises(ModelFailure):
        await OpenAIModel(httpx.MockTransport(respond)).complete(
            PROFILE, [{"role": "user", "content": "x"}], None, 20, 5, output
        )


async def test_completion_token_parameter_and_reasoning_configuration():
    def respond(request):
        payload = json.loads(request.content)
        assert payload["max_completion_tokens"] == 64
        assert "max_tokens" not in payload
        assert payload["reasoning_effort"] == "low"
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

    profile = {**PROFILE, "output_token_parameter": "max_completion_tokens", "reasoning_effort": "low"}
    reply = await OpenAIModel(httpx.MockTransport(respond)).complete(
        profile, [{"role": "user", "content": "x"}], None, 64, 5
    )
    assert reply.text == "OK"


async def test_answer_can_use_provider_default_output_and_report_actual_usage():
    def respond(request):
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
    def respond(request):
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

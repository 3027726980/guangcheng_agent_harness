# 作者：LHF；时间：2026-10-23；作用：验证真实 SDK 的假 HTTP 异常传输。

import httpx
import pytest

from app.llm import ModelFailure, OpenAIModel

PROFILE = {"base_url": "https://fixture.invalid/v1", "api_key": "fake-only", "model": "fixture"}


async def test_nonstream_missing_finish_reason_is_rejected():
    # 作者：LHF；时间：2026-10-22；作用：通过 SDK 假传输确认缺失结束原因不会被补成 stop。
    def respond(request):
        # 作者：LHF；时间：2026-10-22；作用：构造缺少结束原因的供应商响应，不发送网络请求。
        return httpx.Response(
            200,
            json={
                "id": "missing-finish",
                "object": "chat.completion",
                "created": 0,
                "model": "fixture",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "回答"}}],
            },
        )

    with pytest.raises(ModelFailure, match="缺少结束原因"):
        await OpenAIModel(httpx.MockTransport(respond)).complete(
            PROFILE, [{"role": "user", "content": "问题"}], None, 20, 5
        )


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

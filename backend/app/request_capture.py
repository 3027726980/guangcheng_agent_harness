# 作者：LHF；时间：2026-10-22；作用：在模型传输边界捕获实际请求体。
"""Task-local capture callback, shared by real and offline model transports."""

from contextvars import ContextVar
from copy import deepcopy

from app.model_protocol import thinking_options

request_recorder = ContextVar("request_recorder", default=None)


def request_body(profile, messages, tools, max_tokens, streaming):
    # 作用：统一构建 SDK 参数，使离线测试与真实传输使用同一份请求规则。
    body = {"model": profile["model"], "messages": messages, "stream": streaming}
    if tools:
        body.update(tools=tools, tool_choice="auto")
    if max_tokens is not None:
        body[profile.get("output_token_parameter", "max_tokens")] = max_tokens
    options = thinking_options(profile)
    if options:
        body["extra_body"] = options
    return body


async def capture_request(body):
    # 作用：发送前等待快照持久化，异常直接阻止这次发送。
    recorder = request_recorder.get()
    if recorder is not None:
        payload = deepcopy(body)
        payload.update(payload.pop("extra_body", {}))
        await recorder(payload)

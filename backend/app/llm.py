# 作者：LHF。
# 注释维护时间：2026-10-20。
# 文件作用：兼容模型接口的传输、流式拼装、连接与容量探测。
"""OpenAI-compatible transport only. Runtime owns tools, history and retries."""

# 此层只负责协议转换与传输，工具调度、上下文保存和重试策略均由 Runtime 管理。

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from app.model_protocol import thinking_options
from app.response_parser import ReasoningParser, native_reasoning, protocol_reasoning
from app.schemas import ModelReply, ToolCall


class ModelFailure(Exception):
    # 保留可重试标记与供应商要求的等待时间，不向上层透传可能包含密钥的原始响应。
    def __init__(self, message, retryable=False, retry_after=0.0):
        # 作用：记录安全错误提示、可重试标记和供应商要求的等待时间。
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after


class OpenAIModel:
    def __init__(self, transport=None):
        # 作用：保存可选 HTTP 传输，允许离线测试替换网络请求。
        self.transport = transport

    async def complete(
        self,
        profile: dict,
        messages: list[dict],
        tools: list[dict] | None,
        max_tokens: int | None,
        timeout: float,
        on_text: Callable[[str], Awaitable[None]] | None = None,
        on_reasoning: Callable[[str], Awaitable[None]] | None = None,
    ) -> ModelReply:
        """发送兼容协议请求，解析回答、原生思考和工具调用，并适配已知供应商限制。"""
        # 有 on_text 时使用流式回答；摘要与连接测试使用非流式响应。
        try:
            async with AsyncOpenAI(
                api_key=profile.get("api_key") or "local-no-key",
                base_url=profile["base_url"],
                max_retries=0,
                timeout=timeout,
                **({"http_client": httpx.AsyncClient(transport=self.transport)} if self.transport else {}),
            ) as client:
                kwargs = {
                    "model": profile["model"],
                    "messages": messages,
                    "stream": on_text is not None,
                }
                if tools:
                    kwargs["tools"] = tools
                    # 所有工具保持可用，让模型根据上下文偏好自行决定是否调用。
                    kwargs["tool_choice"] = "auto"
                if max_tokens is not None:
                    # 仅调用方明确指定时发送输出限制；普通回答和摘要默认不发送。
                    kwargs[profile.get("output_token_parameter", "max_tokens")] = max_tokens
                options = thinking_options(profile)
                if options:
                    # 仅发送模式开关，强度使用供应商默认值；不再携带 reasoning_effort。
                    kwargs["extra_body"] = options
                response = await client.chat.completions.create(**kwargs)
                if on_text is None:
                    choice = response.choices[0]
                    parser = ReasoningParser()
                    parts = parser.push(choice.message.content or "") + parser.finish()
                    return ModelReply(
                        text="".join(value for kind, value in parts if kind == "text"),
                        reasoning=native_reasoning(choice.message)
                        + "".join(value for kind, value in parts if kind == "reasoning"),
                        reasoning_content=protocol_reasoning(choice.message),
                        finish_reason=choice.finish_reason or "stop",
                        calls=[
                            ToolCall(id=call.id, name=call.function.name, arguments=call.function.arguments)
                            for call in choice.message.tool_calls or []
                        ],
                        usage=response.usage.model_dump() if response.usage else {},
                    )
                text, reasoning, pending, finish, usage = "", "", {}, "", {}
                reasoning_content = None
                parser = ReasoningParser()

                async def publish(parts):
                    """分别累积展示文本和思考，并发送对应的流式事件。"""
                    nonlocal text, reasoning
                    for kind, value in parts:
                        if kind == "reasoning":
                            reasoning += value
                            if on_reasoning:
                                await on_reasoning(value)
                        else:
                            text += value
                            await on_text(value)

                async for chunk in response:
                    if chunk.usage:
                        usage = chunk.usage.model_dump()
                    if not chunk.choices:
                        continue
                    choice = chunk.choices[0]
                    finish = choice.finish_reason or finish
                    delta = choice.delta
                    native = native_reasoning(delta)
                    raw = protocol_reasoning(delta)
                    if raw is not None:
                        reasoning_content = (reasoning_content or "") + raw
                    await publish([("reasoning", native)] if native else [])
                    if delta.content:
                        await publish(parser.push(delta.content))
                    for call in delta.tool_calls or []:
                        # 工具名和 JSON 参数都可能分片到达，按调用 index 累积后统一校验。
                        entry = pending.setdefault(call.index, {"id": "", "name": "", "arguments": ""})
                        if call.id:
                            entry["id"] = call.id
                        if call.function:
                            if call.function.name:
                                entry["name"] += call.function.name
                            if call.function.arguments:
                                entry["arguments"] += call.function.arguments
                await publish(parser.finish())
                if not finish:
                    # 网络流结束不等于模型正常结束，缺少结束标记不能执行残缺工具请求。
                    raise ModelFailure("模型流意外结束，未收到完整结束标记")
                calls = []
                for index in sorted(pending):
                    item = pending[index]
                    if not item["id"] or not item["name"]:
                        raise ModelFailure("工具调用流不完整，未执行工具")
                    calls.append(ToolCall(**item))
                return ModelReply(text=text, reasoning=reasoning, reasoning_content=reasoning_content,
                                  calls=calls, finish_reason=finish, usage=usage)
        except (APIConnectionError, APITimeoutError) as error:
            raise ModelFailure("模型连接失败或请求超时", retryable=True) from error
        except APIStatusError as error:
            # Retry-After 兼容秒数和 HTTP 日期；是否真正重试仍由 Runtime 判断预算。
            try:
                retry_after = max(0.0, float(error.response.headers.get("retry-after", 0)))
            except ValueError:
                try:
                    retry_after = max(
                        0.0,
                        parsedate_to_datetime(error.response.headers["retry-after"]).timestamp()
                        - time.time(),
                    )
                except (ValueError, KeyError, TypeError, OverflowError):
                    retry_after = 0.0
            # 只映射已知协议错误到固定提示，不把供应商原始消息及其中的凭据写入事件。
            hint = ""
            if error.status_code == 400:
                body = error.body if isinstance(error.body, dict) else {}
                detail = body.get("error", body)
                message = str(detail.get("message", "")) if isinstance(detail, dict) else ""
                if "tool_choice" in message:
                    hint = "：供应商不支持当前工具选择方式，请检查思考模式与 tool_choice 的兼容性"
                elif "reasoning_content" in message:
                    hint = "：供应商要求回传历史 reasoning_content，请检查思考字段的保存与回放"
            raise ModelFailure(
                f"模型接口返回 HTTP {error.status_code}{hint}",
                retryable=error.status_code in {408, 429} or error.status_code >= 500,
                retry_after=retry_after,
            ) from error
        except (ValueError, IndexError, TypeError, AttributeError) as error:
            raise ModelFailure("模型响应不符合兼容协议，未执行工具") from error

    async def probe(self, profile, timeout=15.0):
        # 会真实发送一次短对话请求；成功仅证明聊天连接可用，不代表工具能力已验证。
        reply = await self.complete(
            profile,
            [{"role": "user", "content": "Reply OK."}],
            None,
            32,
            timeout,
        )
        capacity, source = await self.capacity(profile, timeout)
        return {
            "connected": True,
            "context_capacity": capacity,
            "capacity_source": source,
            "reply_received": bool(reply.text),
            "capabilities": "chat_only_tested",
        }

    async def capacity(self, profile, timeout=15.0):
        # 优先查询指定模型，再尝试模型列表；读取失败时使用 256K，并记录来源为默认值。
        headers = {"Authorization": f"Bearer {profile.get('api_key') or 'local-no-key'}"}
        paths = [f"/models/{quote(profile['model'], safe='')}", "/models"]
        async with httpx.AsyncClient(timeout=timeout, transport=self.transport) as client:
            for path in paths:
                try:
                    response = await client.get(profile["base_url"].rstrip("/") + path, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    if path == "/models":
                        data = next(
                            (item for item in data.get("data", []) if item.get("id") == profile["model"]), {}
                        )
                    candidates = [data, data.get("top_provider") or {}]
                    for candidate in candidates:
                        for name in ("context_length", "context_window", "max_model_len"):
                            value = candidate.get(name)
                            if type(value) is int and value > 0:
                                return value, f"provider:{name}"
                except (httpx.HTTPError, ValueError, TypeError, AttributeError):
                    continue
        return 262144, "default:256K"


class ScriptedModel:
    """Explicit offline fixture for tests. Never selected by production config."""

    def __init__(self, replies):
        # 作用：准备离线响应队列，并初始化输入和工具选择的记录。
        self.replies = list(replies)
        self.inputs = []

    async def complete(self, profile, messages, tools, max_tokens, timeout, on_text=None,
                       on_reasoning=None):
        # 离线测试按顺序消费预设响应，并深拷贝输入，防止后续修改影响断言证据。
        self.inputs.append(json.loads(json.dumps(messages)))
        if not self.replies:
            raise ModelFailure("测试模型响应已耗尽")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if callable(reply):
            reply = await reply(messages, on_text)
        if on_reasoning and reply.reasoning:
            await on_reasoning(reply.reasoning)
        if on_text and reply.text:
            await on_text(reply.text)
        await asyncio.sleep(0)
        return reply

"""OpenAI-compatible transport only. Runtime owns tools, history and retries."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from urllib.parse import quote

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from app.schemas import ModelReply, ToolCall


class ModelFailure(Exception):
    def __init__(self, message, retryable=False, retry_after=0.0):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after


class OpenAIModel:
    def __init__(self, transport=None):
        self.transport = transport

    async def complete(
        self,
        profile: dict,
        messages: list[dict],
        tools: list[dict] | None,
        max_tokens: int,
        timeout: float,
        on_text: Callable[[str], Awaitable[None]] | None = None,
    ) -> ModelReply:
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
                    "max_tokens": max_tokens,
                    "stream": on_text is not None,
                }
                if tools:
                    kwargs["tools"] = tools
                response = await client.chat.completions.create(**kwargs)
                if on_text is None:
                    choice = response.choices[0]
                    return ModelReply(
                        text=choice.message.content or "",
                        finish_reason=choice.finish_reason or "stop",
                        calls=[
                            ToolCall(id=call.id, name=call.function.name, arguments=call.function.arguments)
                            for call in choice.message.tool_calls or []
                        ],
                        usage=response.usage.model_dump() if response.usage else {},
                    )
                text, pending, finish, usage = "", {}, "", {}
                async for chunk in response:
                    if chunk.usage:
                        usage = chunk.usage.model_dump()
                    if not chunk.choices:
                        continue
                    choice = chunk.choices[0]
                    finish = choice.finish_reason or finish
                    delta = choice.delta
                    if delta.content:
                        text += delta.content
                        await on_text(delta.content)
                    for call in delta.tool_calls or []:
                        entry = pending.setdefault(call.index, {"id": "", "name": "", "arguments": ""})
                        if call.id:
                            entry["id"] = call.id
                        if call.function:
                            if call.function.name:
                                entry["name"] += call.function.name
                            if call.function.arguments:
                                entry["arguments"] += call.function.arguments
                if not finish:
                    raise ModelFailure("模型流意外结束，未收到完整结束标记")
                calls = []
                for index in sorted(pending):
                    item = pending[index]
                    if not item["id"] or not item["name"]:
                        raise ModelFailure("工具调用流不完整，未执行工具")
                    calls.append(ToolCall(**item))
                return ModelReply(text=text, calls=calls, finish_reason=finish, usage=usage)
        except (APIConnectionError, APITimeoutError) as error:
            raise ModelFailure("模型连接失败或请求超时", retryable=True) from error
        except APIStatusError as error:
            try:
                retry_after = max(0.0, float(error.response.headers.get("retry-after", 0)))
            except ValueError:
                retry_after = 0.0
            raise ModelFailure(
                f"模型接口返回 HTTP {error.status_code}",
                retryable=error.status_code in {408, 429} or error.status_code >= 500,
                retry_after=retry_after,
            ) from error
        except (ValueError, IndexError, TypeError, AttributeError) as error:
            raise ModelFailure("模型响应不符合兼容协议，未执行工具") from error

    async def probe(self, profile, timeout=15.0):
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
        headers = {"Authorization": f"Bearer {profile.get('api_key') or 'local-no-key'}"}
        paths = [f"/models/{quote(profile['model'], safe='')}", "/models"]
        async with httpx.AsyncClient(timeout=timeout) as client:
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
        self.replies = list(replies)
        self.inputs = []

    async def complete(self, profile, messages, tools, max_tokens, timeout, on_text=None):
        self.inputs.append(json.loads(json.dumps(messages)))
        if not self.replies:
            raise ModelFailure("测试模型响应已耗尽")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if callable(reply):
            reply = await reply(messages, on_text)
        if on_text and reply.text:
            await on_text(reply.text)
        await asyncio.sleep(0)
        return reply

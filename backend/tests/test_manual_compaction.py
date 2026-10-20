# 作者：LHF。
# 时间：2026-10-20。
# 作用：验证 test_manual_compaction 所覆盖的行为与边界，使用离线数据及临时资源。
import asyncio
import json

import httpx
import pytest

from app.llm import ModelFailure, OpenAIModel
from app.runtime import DomainError
from app.schemas import CompactionRequest, ModelReply
from app.storage import uid
from tests.test_runtime import terminal


async def history(rt, session):
    # 作用：创建可压缩的会话历史，供手动压缩场景复用。
    for index in range(3):
        for role in ("user", "assistant"):
            await rt.db.put(
                "message",
                {
                    "id": uid(),
                    "run_id": "old",
                    "message": {"role": role, "content": f"{role}第{index}轮：保留用户约束"},
                },
                parent=session["id"],
            )
    return await rt.db.list("message", parent=session["id"])


async def compact(rt, client, session, request_id=None, user="A"):
    # 作用：使用当前客户端提交手动压缩任务，允许指定请求 ID 和用户。
    return await rt.submit(
        session["id"],
        user,
        CompactionRequest(
            client_id=client.id,
            request_id=request_id or uid(),
        ),
        purpose="context_compaction",
    )


async def test_manual_compaction_below_threshold_preserves_last_turn_and_history(harness):
    # 作用：验证手动压缩可在阈值以下执行，并保留最近一轮和全部原历史。
    rt, model, client, session, _ = harness
    original = await history(rt, session)
    model.replies = [ModelReply(text="用户约束摘要")]
    run = await compact(rt, client, session, "manual-request-123")
    duplicate = await compact(rt, client, session, "manual-request-123")
    assert duplicate["id"] == run["id"]
    result = await terminal(rt, run["id"])
    assert result["status"] == "completed" and result["compaction_result"] == "compacted"
    assert result["model_calls"] == 1 and result["tool_calls"] == 0
    assert await rt.db.list("message", parent=session["id"]) == original
    summary = await rt.db.get("summary:" + session["id"])
    assert set(summary["covered"]) == {row["id"] for row in original[:-2]}
    assert len(model.inputs) == 1  # No additional answer / tool call.
    with pytest.raises(DomainError):
        await compact(rt, client, session, user="B")


async def test_empty_manual_compaction_skips_model(harness):
    # 作用：验证没有历史可压缩时跳过模型调用。
    rt, model, client, session, _ = harness
    run = await compact(rt, client, session)
    result = await terminal(rt, run["id"])
    assert result["status"] == "completed" and result["compaction_result"] == "skipped"
    assert model.inputs == []
    assert await rt.db.list("message", parent=session["id"]) == []


async def test_longer_summary_is_not_committed(harness):
    # 作用：验证摘要使上下文变长时不覆盖已有摘要。
    rt, model, client, session, _ = harness
    original = await history(rt, session)
    model.replies = [ModelReply(text="过长摘要" * 500)]
    run = await compact(rt, client, session)
    result = await terminal(rt, run["id"])
    assert result["compaction_result"] == "skipped"
    assert "未减少" in result["compaction_message"]
    assert await rt.db.get("summary:" + session["id"]) is None
    assert await rt.db.list("message", parent=session["id"]) == original


async def test_reasoning_summary_uses_provider_default_instead_of_text_target_cap(harness):
    # 作用：验证摘要请求使用供应商默认输出长度，不设置固定正文上限。
    rt, _, client, session, _ = harness
    original = await history(rt, session)
    payloads = []

    def respond(request):
        # 作用：构造假 HTTP 响应并检查请求参数，用于摘要请求使用供应商默认输出长度，不设置固定正文上限。
        payload = json.loads(request.content)
        payloads.append(payload)
        capped = "max_tokens" in payload or "max_completion_tokens" in payload
        # Reproduce a reasoning model spending the small cap before producing text.
        return httpx.Response(
            200,
            json={
                "id": "summary",
                "object": "chat.completion",
                "created": 0,
                "model": "offline",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "length" if capped else "stop",
                        "message": {"role": "assistant", "content": "" if capped else "用户约束摘要"},
                    }
                ],
                "usage": {
                    "prompt_tokens": 500,
                    "completion_tokens": 5000,
                    "total_tokens": 5500,
                    "completion_tokens_details": {"reasoning_tokens": 4900},
                },
            },
        )

    rt.model = OpenAIModel(httpx.MockTransport(respond))
    run = await compact(rt, client, session)
    result = await terminal(rt, run["id"])
    assert result["status"] == "completed" and result["compaction_result"] == "compacted"
    assert "tokens" not in payloads[0]["messages"][0]["content"]
    assert "正文目标" not in payloads[0]["messages"][0]["content"]
    assert "max_tokens" not in payloads[0] and "max_completion_tokens" not in payloads[0]
    assert len(payloads) == 1
    assert await rt.db.list("message", parent=session["id"]) == original


async def test_provider_truncated_summary_reports_reason_and_keeps_prior_summary(harness):
    # 作用：验证供应商截断摘要时明确失败并保留旧摘要。
    rt, model, client, session, _ = harness
    original = await history(rt, session)
    prior = {"id": "summary:" + session["id"], "text": "原摘要", "covered": [original[0]["id"]]}
    await rt.db.put("summary", prior, parent=session["id"])
    model.replies = [ModelReply(finish_reason="length", usage={"completion_tokens": 1114})]
    run = await compact(rt, client, session)
    result = await terminal(rt, run["id"])
    assert result["status"] == "failed" and "输出上限截断" in result["reason"]
    assert await rt.db.get(prior["id"]) == prior
    assert (await rt.db.list("message", parent=session["id"]))[: len(original)] == original


@pytest.mark.parametrize("cancel", [False, True])
async def test_manual_compaction_exclusion_failure_and_cancel_preserve_coverage(harness, cancel):
    # 作用：验证压缩任务互斥，失败或取消不会修改原覆盖范围。
    rt, model, client, session, _ = harness
    original = await history(rt, session)
    entered, release = asyncio.Event(), asyncio.Event()

    async def summary(messages, on_text):
        # 作用：模拟摘要返回、失败或等待，用于压缩任务互斥，失败或取消不会修改原覆盖范围。
        entered.set()
        await release.wait()
        raise ModelFailure("模拟摘要失败")

    model.replies = [summary]
    run = await compact(rt, client, session)
    await asyncio.wait_for(entered.wait(), 2)
    with pytest.raises(DomainError) as busy:
        await compact(rt, client, session)
    assert busy.value.status == 409
    if cancel:
        await rt.cancel(run["id"], "A")
    else:
        release.set()
    result = await terminal(rt, run["id"])
    assert result["status"] == ("cancelled" if cancel else "failed")
    assert await rt.db.get("summary:" + session["id"]) is None
    saved = await rt.db.list("message", parent=session["id"])
    assert saved[: len(original)] == original

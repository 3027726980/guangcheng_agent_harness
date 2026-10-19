import asyncio

import pytest

from app.llm import ModelFailure
from app.runtime import DomainError
from app.schemas import CompactionRequest, ModelReply
from app.storage import uid
from tests.test_runtime import terminal


async def history(rt, session):
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
    rt, model, client, session, _ = harness
    run = await compact(rt, client, session)
    result = await terminal(rt, run["id"])
    assert result["status"] == "completed" and result["compaction_result"] == "skipped"
    assert model.inputs == []
    assert await rt.db.list("message", parent=session["id"]) == []


async def test_longer_summary_is_not_committed(harness):
    rt, model, client, session, _ = harness
    original = await history(rt, session)
    model.replies = [ModelReply(text="过长摘要" * 500)]
    run = await compact(rt, client, session)
    result = await terminal(rt, run["id"])
    assert result["compaction_result"] == "skipped"
    assert "未减少" in result["compaction_message"]
    assert await rt.db.get("summary:" + session["id"]) is None
    assert await rt.db.list("message", parent=session["id"]) == original


@pytest.mark.parametrize("cancel", [False, True])
async def test_manual_compaction_exclusion_failure_and_cancel_preserve_coverage(harness, cancel):
    rt, model, client, session, _ = harness
    original = await history(rt, session)
    entered, release = asyncio.Event(), asyncio.Event()

    async def summary(messages, on_text):
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

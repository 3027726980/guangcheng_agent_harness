import pytest

from app.context import ContextFailure, ContextManager, tool_groups
from app.llm import ModelFailure
from app.schemas import ModelReply, RuntimeSettings
from app.storage import Database, uid


async def setup(db):
    await db.initialize()
    for index in range(12):
        await db.put(
            "message",
            {
                "id": uid(),
                "run_id": "old",
                "message": {"role": "user" if index % 2 == 0 else "assistant", "content": "历史材料" * 60},
            },
            parent="s",
        )
    request_id = uid()
    await db.put(
        "message",
        {
            "id": request_id,
            "run_id": "current",
            "input_kind": "request",
            "message": {"role": "user", "content": "每天最多30分钟，不要丢失这个要求"},
        },
        parent="s",
    )


async def test_compaction_coverage_and_pinned_request(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    try:
        await setup(db)
        events = []

        async def emit(kind, data):
            events.append((kind, data))

        async def summary(profile, messages, max_tokens):
            return ModelReply(text="历史目标：学习计划；操作均未写入待办。")

        settings = RuntimeSettings(max_output_tokens=64, summary_tokens=64)
        result = await ContextManager(db).build(
            "s",
            "current",
            settings,
            {"model": "test", "context_capacity": 6000},
            {"model": "summary", "context_capacity": 16000},
            [],
            "系统",
            summary,
            emit,
        )
        assert "每天最多30分钟" in result[-1]["content"]
        assert any(kind == "context.compacted" for kind, _ in events)
        saved = await db.get("summary:s")
        assert saved["covered"]
        assert len(await db.list("message", parent="s")) == 13
    finally:
        await db.close()


async def test_summary_failure_keeps_original_and_stops_when_over_limit(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    try:
        await setup(db)

        async def emit(kind, data):
            pass

        async def summary(profile, messages, max_tokens):
            raise ModelFailure("摘要故障")

        with pytest.raises(ContextFailure):
            await ContextManager(db).build(
                "s",
                "current",
                RuntimeSettings(max_output_tokens=64, summary_tokens=64),
                {"model": "x", "context_capacity": 6000},
                {"model": "x", "context_capacity": 16000},
                [],
                "系统",
                summary,
                emit,
            )
        assert await db.get("summary:s") is None
        assert len(await db.list("message", parent="s")) == 13
    finally:
        await db.close()


def test_incomplete_tool_pair_is_rejected():
    with pytest.raises(ContextFailure):
        tool_groups([{"role": "assistant", "tool_calls": [{"id": "a"}]}])
    with pytest.raises(ContextFailure):
        tool_groups([{"role": "tool", "tool_call_id": "orphan"}])

# 作者：LHF；时间：2026-10-23；作用：验证基础上下文压缩与失败保留。

import pytest

from app.context import ContextFailure, ContextManager, tool_groups
from app.llm import ModelFailure
from app.schemas import ModelReply, RuntimeSettings
from app.storage import Database
from tests.support.context import setup


async def test_compaction_coverage_and_pinned_request(tmp_path):
    # 作用：验证摘要覆盖范围正确，且当前任务原请求在压缩后仍保留。
    db = Database(str(tmp_path / "test.db"))
    try:
        await setup(db)
        original = await db.list("message", parent="s")
        events = []

        async def emit(kind, data):
            # 作用：收集上下文事件，供测试检查压缩状态与覆盖范围。
            events.append((kind, data))

        async def summary(profile, messages, max_tokens):
            # 作用：模拟摘要返回、失败或等待，用于摘要覆盖范围正确，且当前任务原请求在压缩后仍保留。
            return ModelReply(text="历史目标：学习计划；操作均未写入待办。")

        settings = RuntimeSettings()
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
        assert {"history-0", "history-1"} <= set(saved["covered"])
        tool_groups(result)
        assert await db.list("message", parent="s") == original
    finally:
        await db.close()


async def test_summary_failure_keeps_original_and_stops_when_over_limit(tmp_path):
    # 作用：验证摘要失败保留原历史，容量确实不足时终止执行。
    db = Database(str(tmp_path / "test.db"))
    try:
        await setup(db)
        original = await db.list("message", parent="s")

        async def emit(kind, data):
            # 作用：收集上下文事件，供测试检查压缩状态与覆盖范围。
            pass

        async def summary(profile, messages, max_tokens):
            # 作用：模拟摘要返回、失败或等待，用于摘要失败保留原历史，容量确实不足时终止执行。
            raise ModelFailure("摘要故障")

        with pytest.raises(ContextFailure):
            await ContextManager(db).build(
                "s",
                "current",
                RuntimeSettings(),
                {"model": "x", "context_capacity": 6000},
                {"model": "x", "context_capacity": 16000},
                [],
                "系统",
                summary,
                emit,
            )
        assert await db.get("summary:s") is None
        assert await db.list("message", parent="s") == original
    finally:
        await db.close()

# 作者：LHF。
# 时间：2026-10-20。
# 作用：验证 test_context 所覆盖的行为与边界，使用离线数据及临时资源。
import asyncio

import pytest

from app.context import ContextFailure, ContextManager, tokens, tool_groups
from app.llm import ModelFailure
from app.schemas import ModelReply, RuntimeSettings
from app.storage import Database, uid


async def setup(db):
    # 作用：构造多轮历史消息和受保护的当前请求，用于压缩测试。
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
    # 作用：验证摘要覆盖范围正确，且当前任务原请求在压缩后仍保留。
    db = Database(str(tmp_path / "test.db"))
    try:
        await setup(db)
        request = (await db.list("message", parent="s"))[-1]
        await db.put("message", {**request, "tool_names": ["todo"]}, parent="s")
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
        assert "工具：todo。" in result[-1]["content"]
        assert "不强制调用" in result[-1]["content"]
        assert any(kind == "context.compacted" for kind, _ in events)
        saved = await db.get("summary:s")
        assert saved["covered"]
        assert len(await db.list("message", parent="s")) == 13
    finally:
        await db.close()


async def test_summary_failure_keeps_original_and_stops_when_over_limit(tmp_path):
    # 作用：验证摘要失败保留原历史，容量确实不足时终止执行。
    db = Database(str(tmp_path / "test.db"))
    try:
        await setup(db)

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
        assert len(await db.list("message", parent="s")) == 13
    finally:
        await db.close()


def test_incomplete_tool_pair_is_rejected():
    # 作用：验证孤立工具结果和缺失结果的工具声明被拒绝。
    with pytest.raises(ContextFailure):
        tool_groups([{"role": "assistant", "tool_calls": [{"id": "a"}]}])
    with pytest.raises(ContextFailure):
        tool_groups([{"role": "tool", "tool_call_id": "orphan"}])


async def test_smaller_summary_model_preserves_still_fitting_original(tmp_path):
    # 作用：验证摘要模型容量不足时仍保留可容纳的原上下文。
    db = Database(str(tmp_path / "fallback.db"))
    try:
        await setup(db)
        messages = [row["message"] for row in await db.list("message", parent="s")]
        initial = tokens([{"role": "system", "content": "系统"}] + messages) + tokens([])
        capacity = int(initial / (0.85 * 0.9)) + 256
        events = []

        async def emit(kind, data):
            # 作用：收集上下文事件，供测试检查压缩状态与覆盖范围。
            events.append(kind)

        async def summary(*args):
            # 作用：模拟摘要返回、失败或等待，用于摘要模型容量不足时仍保留可容纳的原上下文。
            pytest.fail("不能向过小摘要模型发送超限输入")

        result = await ContextManager(db).build(
            "s",
            "current",
            RuntimeSettings(),
            {"model": "unknown", "context_capacity": capacity},
            {"model": "unknown", "context_capacity": 2000},
            [],
            "系统",
            summary,
            emit,
        )
        assert result[1:] == messages
        assert "context.compaction_failed" in events
        assert await db.get("summary:s") is None
    finally:
        await db.close()


async def test_cancelled_summary_does_not_update_coverage(tmp_path):
    # 作用：验证取消摘要不会提交新的覆盖范围。
    db = Database(str(tmp_path / "cancel.db"))
    try:
        await setup(db)

        async def emit(kind, data):
            # 作用：收集上下文事件，供测试检查压缩状态与覆盖范围。
            pass

        async def summary(*args):
            # 作用：模拟摘要返回、失败或等待，用于取消摘要不会提交新的覆盖范围。
            raise asyncio.CancelledError

        with pytest.raises(asyncio.CancelledError):
            await ContextManager(db).build(
                "s",
                "current",
                RuntimeSettings(),
                {"model": "unknown", "context_capacity": 6000},
                {"model": "unknown", "context_capacity": 16000},
                [],
                "系统",
                summary,
                emit,
            )
        assert await db.get("summary:s") is None
        assert len(await db.list("message", parent="s")) == 13
    finally:
        await db.close()

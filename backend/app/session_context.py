# 作者：LHF；时间：2026-10-22；作用：从数据库恢复并增量维护每会话模型可见历史。
"""Database-backed visible history, independent of the diagnostic event log."""

import asyncio
from copy import deepcopy
from dataclasses import dataclass, field


@dataclass
class SessionContext:
    version: int = 0
    summary: dict | None = None
    rows: list[dict] = field(default_factory=list)
    # 会话所有已记录的工具调用 ID，包含已经被上下文压缩移除的消息中的调用。
    tool_call_ids: set[str] = field(default_factory=set)

    def record(self, session_id):
        # 作用：持久化可见节点清单，原始正文继续由 message 记录保存。
        return {
            "id": f"context:{session_id}",
            "version": self.version,
            "summary": self.summary,
            "message_ids": [row["id"] for row in self.rows],
            "tool_call_ids": sorted(self.tool_call_ids),
        }


class ContextState:
    def __init__(self, db):
        # 作用：绑定仓储，每会话独立缓存和短时锁。
        self.db, self.sessions, self.locks = db, {}, {}

    def lock(self, session_id):
        # 作用：让不同会话独立更新，不占用 Runtime.control 等待模型。
        return self.locks.setdefault(session_id, asyncio.Lock())

    async def _load(self, session_id):
        # 作用：有清单时只按可见 ID 恢复，旧会话首次初始化才扫描完整历史。
        if session_id in self.sessions:
            return self.sessions[session_id]
        saved = await self.db.get(f"context:{session_id}")
        if saved:
            rows = await self.db.get_many(saved["message_ids"])
            if len(rows) != len(saved["message_ids"]):
                raise ValueError("上下文清单引用了不存在的消息")
            state = SessionContext(saved["version"], saved.get("summary"), rows)
            if "tool_call_ids" in saved:
                state.tool_call_ids = set(saved["tool_call_ids"])
        else:
            history = await self.db.list("message", parent=session_id)
            summary = await self.db.get(f"summary:{session_id}")
            covered = set(summary.get("covered", [])) if summary else set()
            state = SessionContext(0, summary, [row for row in history if row["id"] not in covered])
        if not saved or "tool_call_ids" not in saved:
            # 旧清单缺少 ID 集合时扫描一次完整历史，不能只看压缩后仍可见的消息。
            if saved:
                history = await self.db.list("message", parent=session_id)
            for row in history:
                for call in row["message"].get("tool_calls", []):
                    state.tool_call_ids.add(call["id"])
            await self.db.put("context", state.record(session_id), parent=session_id)
        self.sessions[session_id] = state
        return state

    async def ensure_loaded(self, session_id):
        # 作用：打开会话时恢复缓存，重复访问直接复用内存状态。
        async with self.lock(session_id):
            await self._load(session_id)

    async def has_tool_calls(self, session_id, call_ids):
        # 作用：直接检查会话 ID 集合，不扫描历史消息或复制上下文。
        async with self.lock(session_id):
            current = await self._load(session_id)
            return not current.tool_call_ids.isdisjoint(call_ids)

    async def snapshot(self, session_id):
        # 作用：返回独立副本，协议转换和提示词注入不会污染共享上下文。
        async with self.lock(session_id):
            return deepcopy(await self._load(session_id))

    async def append(self, session_id, row, owner):
        # 作用：正文和可见清单同事务写入，提交成功才发布内存状态。
        async with self.lock(session_id):
            current = await self._load(session_id)
            updated = deepcopy(current)
            updated.rows.append(deepcopy(row))
            # 与消息同事务保存；提交失败不提前登记 ID，普通消息不会增加调用 ID。
            for call in row["message"].get("tool_calls", []):
                updated.tool_call_ids.add(call["id"])
            updated.version += 1
            await self._commit(session_id, updated, "message", row, owner)

    async def compact(self, session_id, expected_version, removed_ids, summary):
        # 作用：只替换已验证的旧连续前缀；并发追加时拒绝提交过时摘要。
        async with self.lock(session_id):
            current = await self._load(session_id)
            if current.version != expected_version:
                return False
            count = len(removed_ids)
            if [row["id"] for row in current.rows[:count]] != removed_ids:
                raise ValueError("压缩范围不是当前可见历史的连续前缀")
            updated = SessionContext(
                current.version + 1,
                deepcopy(summary),
                deepcopy(current.rows[count:]),
                # 压缩只缩减模型可见消息，不释放已使用的调用 ID。
                set(current.tool_call_ids),
            )
            await self._commit(session_id, updated, "summary", summary)
            return True

    async def _commit(self, session_id, updated, kind, record, owner=""):
        # 作用：提交和内存发布作为一次收尾；取消也须等到事务结果确定才释放会话锁。
        async def commit():
            # 作用：避免 SQLite 已提交但取消导致缓存仍停留在旧版本。
            async with self.db.transaction() as connection:
                await self.db.put(kind, record, owner=owner, parent=session_id, connection=connection)
                await self.db.put(
                    "context", updated.record(session_id), parent=session_id, connection=connection
                )
            self.sessions[session_id] = updated

        task = asyncio.create_task(commit())
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            await task
            raise

    def evict(self, session_id):
        # 作用：会话删除后释放正文缓存，历史数据库记录保持不变。
        self.sessions.pop(session_id, None)
        self.locks.pop(session_id, None)

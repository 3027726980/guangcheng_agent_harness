# 作者：LHF。
# 注释维护时间：2026-10-20。
# 文件作用：SQLite 记录与事件存储、事务和查询。
"""Small SQLite repository with atomic multi-record transactions."""

import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from sqlalchemy import JSON, Column, Float, Integer, MetaData, String, Table, delete, insert, select, update
from sqlalchemy.ext.asyncio import create_async_engine

metadata = MetaData()
# 通用记录表：kind 区分会话、消息、任务等，owner/parent 支持按用户和父对象查询。
records = Table(
    "records",
    metadata,
    Column("id", String, primary_key=True),
    Column("kind", String, index=True),
    Column("owner", String, index=True),
    Column("parent", String, index=True),
    Column("created", Float),
    Column("data", JSON),
)
# 事件单独保存，使用递增 ID 排序，供 SSE 通知和历史链路查看使用。
events = Table(
    "events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("owner", String, index=True),
    Column("session_id", String, index=True),
    Column("run_id", String, index=True),
    Column("type", String),
    Column("timestamp", Float),
    Column("data", JSON),
)


def uid():
    # 作用：生成不含连字符的随机 ID，用作记录、请求和工具操作标识。
    return uuid4().hex


class Database:
    # connection 参数允许多个仓储操作复用同一事务，实现跨记录的原子提交。
    def __init__(self, path: str):
        # 作用：确保数据库目录存在，建立异步 SQLite 引擎及进程内写锁。
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{path}", connect_args={"timeout": 10})
        self.lock = asyncio.Lock()

    async def initialize(self):
        # WAL 改善读写并发；写锁冲突时最多等待 10 秒，再创建尚不存在的表。
        async with self.engine.begin() as connection:
            await connection.exec_driver_sql("PRAGMA journal_mode=WAL")
            await connection.exec_driver_sql("PRAGMA busy_timeout=10000")
            await connection.run_sync(metadata.create_all)

    @asynccontextmanager
    async def transaction(self):
        # 进程内串行写入，正常退出自动提交，异常退出自动回滚。
        async with self.lock:
            async with self.engine.begin() as connection:
                yield connection

    async def get(self, key: str, connection=None):
        # 作用：按唯一 ID 读取记录，必要时复用调用方传入的事务连接。
        if connection is None:
            async with self.engine.connect() as connection:
                return await self.get(key, connection)
        row = (await connection.execute(select(records.c.data).where(records.c.id == key))).first()
        return dict(row[0]) if row else None

    async def put(self, kind: str, data: dict, owner="", parent="", connection=None):
        # 新记录写入索引字段；更新仅替换 JSON 数据，保留最初的归属、父级和创建顺序。
        if connection is None:
            async with self.transaction() as connection:
                return await self.put(kind, data, owner, parent, connection)
        key = data["id"]
        existing = await self.get(key, connection)
        if existing is None:
            await connection.execute(
                insert(records).values(
                    id=key,
                    kind=kind,
                    owner=owner,
                    parent=parent,
                    created=time.time(),
                    data=data,
                )
            )
        else:
            await connection.execute(update(records).where(records.c.id == key).values(data=data))
        return data

    async def list(self, kind: str, owner=None, parent=None, connection=None):
        # 按创建顺序返回，Runtime 依赖此顺序消费队列和还原完整消息历史。
        if connection is None:
            async with self.engine.connect() as connection:
                return await self.list(kind, owner, parent, connection)
        query = select(records.c.data).where(records.c.kind == kind).order_by(records.c.created)
        if owner is not None:
            query = query.where(records.c.owner == owner)
        if parent is not None:
            query = query.where(records.c.parent == parent)
        return [dict(row[0]) for row in (await connection.execute(query)).all()]

    async def remove(self, key):
        # 作用：在写事务内按 ID 物理移除记录。
        async with self.transaction() as connection:
            await connection.execute(delete(records).where(records.c.id == key))

    async def append_event(self, kind, data, owner=None, session_id=None, run_id=None):
        # 事务提交后才返回事件，避免向前端广播实际上未持久化的数据。
        timestamp = time.time()
        async with self.transaction() as connection:
            result = await connection.execute(
                insert(events).values(
                    owner=owner,
                    session_id=session_id,
                    run_id=run_id,
                    type=kind,
                    timestamp=timestamp,
                    data=data,
                )
            )
            key = result.inserted_primary_key[0]
        return {
            "id": key,
            "user_id": owner,
            "session_id": session_id,
            "run_id": run_id,
            "type": kind,
            "timestamp": timestamp,
            "data": data,
        }

    async def history_events(self, owner, session_id=None, after=0, limit=2000):
        # 用户可以读取自己的事件及全局事件；先取最新 limit 条，再转为时间正序。
        query = select(events).where(events.c.id > after)
        if owner is not None:
            query = query.where((events.c.owner == owner) | events.c.owner.is_(None))
        if session_id:
            query = query.where(events.c.session_id == session_id)
        query = query.order_by(events.c.id.desc()).limit(limit)
        async with self.engine.connect() as connection:
            rows = (await connection.execute(query)).mappings().all()
        return [
            {
                "id": r["id"],
                "user_id": r["owner"],
                "session_id": r["session_id"],
                "run_id": r["run_id"],
                "type": r["type"],
                "timestamp": r["timestamp"],
                "data": r["data"],
            }
            for r in reversed(rows)
        ]

    async def close(self):
        # 作用：释放数据库连接池及异步引擎资源。
        await self.engine.dispose()

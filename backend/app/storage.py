"""Small SQLite repository with atomic multi-record transactions."""

import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from sqlalchemy import JSON, Column, Float, Integer, MetaData, String, Table, delete, insert, select, update
from sqlalchemy.ext.asyncio import create_async_engine

metadata = MetaData()
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
    return uuid4().hex


class Database:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{path}", connect_args={"timeout": 10})
        self.lock = asyncio.Lock()

    async def initialize(self):
        async with self.engine.begin() as connection:
            await connection.exec_driver_sql("PRAGMA journal_mode=WAL")
            await connection.exec_driver_sql("PRAGMA busy_timeout=10000")
            await connection.run_sync(metadata.create_all)

    @asynccontextmanager
    async def transaction(self):
        async with self.lock:
            async with self.engine.begin() as connection:
                yield connection

    async def get(self, key: str, connection=None):
        if connection is None:
            async with self.engine.connect() as connection:
                return await self.get(key, connection)
        row = (await connection.execute(select(records.c.data).where(records.c.id == key))).first()
        return dict(row[0]) if row else None

    async def put(self, kind: str, data: dict, owner="", parent="", connection=None):
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
        async with self.transaction() as connection:
            await connection.execute(delete(records).where(records.c.id == key))

    async def append_event(self, kind, data, owner=None, session_id=None, run_id=None):
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
        await self.engine.dispose()

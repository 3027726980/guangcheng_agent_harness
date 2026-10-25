# 作者：LHF；时间：2026-10-23；作用：离线 Runtime 夹具、提交与终态等待。

import asyncio

import pytest_asyncio

from app.llm import ScriptedModel
from app.runtime import Client, Runtime
from app.schemas import MessageRequest, RuntimeSettings
from app.storage import Database, uid


async def wait_until(predicate, timeout=4):
    # 作用：在超时范围内轮询异步条件，等待后台任务达到可断言的状态。
    async with asyncio.timeout(timeout):
        while not await predicate():
            await asyncio.sleep(0.005)


async def terminal(rt, key):
    # 作用：等待数据库终态和执行协程收尾，确保最终 Trace 已写入。
    async def check():
        # 作用：读取任务状态，判断其是否已经进入终态。
        return (await rt.db.get(key))["status"] in {"completed", "cancelled", "failed", "limited"}

    await wait_until(check)
    task = rt.executions.get(key)
    if task is not None:
        await asyncio.wait_for(asyncio.shield(task), timeout=4)
    return await rt.db.get(key)


@pytest_asyncio.fixture
async def harness(tmp_path):
    # 作用：创建离线 Runtime、演示用户、模型配置和已连接客户端，并在结束时释放资源。
    model = ScriptedModel([])
    waits = []

    async def sleep(delay):
        # 作用：记录重试等待时长并让出事件循环，不进行真实长时间等待。
        waits.append(delay)
        await asyncio.sleep(0)

    rt = Runtime(Database(str(tmp_path / "test.db")), model=model, sleep=sleep)
    await rt.initialize()
    profile = {
        "id": "profile",
        "kind": "profile",
        "name": "offline",
        "base_url": "http://offline.invalid/v1",
        "api_key": "test-secret-not-for-events",
        "model": "offline",
        "context_capacity": 262144,
        "capacity_source": "fixture",
        "test_status": "connected",
    }
    await rt.db.put("profile", profile)
    settings = RuntimeSettings(default_profile_id="profile").model_dump()
    await rt.db.put("settings", {"id": "runtime-settings", **settings})
    client = Client(uid(), "A", connected=True)
    rt.clients[client.id] = client
    session = await rt.create_session("A", "测试")
    yield rt, model, client, session, waits
    await rt.close()


async def send(rt, client, session, content="你好", request_id=None):
    # 作用：使用当前测试客户端提交聊天任务，缺省时生成唯一请求 ID。
    return await rt.submit(
        session["id"],
        "A",
        MessageRequest(client_id=client.id, request_id=request_id or uid(), content=content),
    )

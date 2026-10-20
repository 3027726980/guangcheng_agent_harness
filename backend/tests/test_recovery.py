# 作者：LHF。
# 时间：2026-10-20。
# 作用：验证 test_recovery 所覆盖的行为与边界，使用离线数据及临时资源。
import asyncio
import json

from app.runtime import Runtime
from app.schemas import ModelReply, ToolCall
from app.storage import Database, uid
from tests.test_runtime import send, terminal


async def test_tool_parallel_limit_and_result_order(harness):
    # 作用：验证并行工具受并发限制，结果仍按声明顺序回填。
    rt, model, client, session, _ = harness
    settings = (await rt.settings()).model_copy(update={"tool_concurrency": 2})
    await rt.db.put("settings", {"id": "runtime-settings", **settings.model_dump()})
    active, peak = 0, 0
    two_started = asyncio.Event()

    async def execute(call, db, owner, operation):
        # 作用：模拟工具执行及其并发或提交时机，用于并行工具受并发限制，结果仍按声明顺序回填。
        nonlocal active, peak
        active += 1
        peak = max(active, peak)
        if active == 2:
            two_started.set()
        await asyncio.wait_for(two_started.wait(), 2)
        active -= 1
        return {"value": call.id}

    rt.registry.execute = execute
    model.replies = [
        ModelReply(
            calls=[
                ToolCall(id=name, name="calculator", arguments='{"expression":"1"}')
                for name in ("a", "b", "c")
            ]
        ),
        ModelReply(text="完成"),
    ]
    run = await send(rt, client, session)
    assert (await terminal(rt, run["id"]))["status"] == "completed"
    assert peak == 2
    rows = await rt.db.list("message", parent=session["id"])
    assert [row["message"]["tool_call_id"] for row in rows if row["message"]["role"] == "tool"] == [
        "a",
        "b",
        "c",
    ]


async def test_batch_with_todo_is_sequential(harness):
    # 作用：验证包含待办的整批工具按顺序执行。
    rt, model, client, session, _ = harness
    active, peak = 0, 0

    async def execute(call, db, owner, operation):
        # 作用：模拟工具执行及其并发或提交时机，用于包含待办的整批工具按顺序执行。
        nonlocal active, peak
        active += 1
        peak = max(active, peak)
        await asyncio.sleep(0.005)
        active -= 1
        return {"value": call.id}

    rt.registry.execute = execute
    model.replies = [
        ModelReply(
            calls=[
                ToolCall(id="a", name="search", arguments="{}"),
                ToolCall(id="b", name="todo", arguments="{}"),
            ]
        ),
        ModelReply(text="完成"),
    ]
    run = await send(rt, client, session)
    assert (await terminal(rt, run["id"]))["status"] == "completed"
    assert peak == 1


async def test_cancel_during_committed_write_preserves_result(harness):
    # 作用：验证取消期间已提交的写操作结果被保留，不误报未执行。
    rt, model, client, session, _ = harness
    original = rt.registry.execute
    committed, release = asyncio.Event(), asyncio.Event()

    async def execute(call, db, owner, operation):
        # 作用：模拟工具执行及其并发或提交时机，用于取消期间已提交的写操作结果被保留，不误报未执行。
        result = await original(call, db, owner, operation)
        committed.set()
        await release.wait()
        return result

    rt.registry.execute = execute
    model.replies = [
        ModelReply(calls=[ToolCall(id="write", name="todo", arguments='{"action":"add","title":"必须保留"}')])
    ]
    run = await send(rt, client, session)
    await committed.wait()
    await rt.cancel(run["id"], "A")
    release.set()
    result = await terminal(rt, run["id"])
    assert result["status"] == "cancelled"
    assert len(await rt.db.list("todo", owner="A")) == 1
    rows = await rt.db.list("message", parent=session["id"])
    tool_result = next(
        json.loads(row["message"]["content"]) for row in rows if row["message"]["role"] == "tool"
    )
    assert tool_result["ok"] and tool_result["stop_requested"]


async def test_total_timeout_is_terminal(harness):
    # 作用：验证执行超过总时长后进入终态并完成收尾。
    rt, model, client, session, _ = harness
    settings = (await rt.settings()).model_copy(update={"max_seconds": 0.08})
    await rt.db.put("settings", {"id": "runtime-settings", **settings.model_dump()})

    async def block(messages, on_text):
        # 作用：阻塞模拟模型直至测试释放或取消，用于执行超过总时长后进入终态并完成收尾。
        await asyncio.Event().wait()

    model.replies = [block]
    run = await send(rt, client, session)
    assert (await terminal(rt, run["id"]))["status"] == "limited"


async def test_restart_marks_runs_and_recovers_committed_tool_result(tmp_path):
    # 作用：验证重启修复未结束任务，并从操作凭据恢复已提交工具结果。
    path = str(tmp_path / "restart.db")
    db = Database(path)
    await db.initialize()
    run = {"id": "oldrun", "session_id": "s", "user_id": "A", "client_id": "oldclient", "status": "running"}
    await db.put("run", run, owner="A", parent="s")
    await db.put("run", {**run, "id": "queued", "status": "queued"}, owner="A", parent="s")
    await db.put(
        "message",
        {
            "id": uid(),
            "run_id": "oldrun",
            "message": {
                "role": "assistant",
                "tool_calls": [
                    {"id": "call", "type": "function", "function": {"name": "todo", "arguments": "{}"}}
                ],
            },
        },
        parent="s",
    )
    await db.put("operation", {"id": "op:oldrun:call", "owner": "A", "result": {"item": {"id": "saved"}}})
    await db.close()
    rt = Runtime(Database(path))
    try:
        await rt.initialize()
        assert (await rt.db.get("oldrun"))["status"] == "interrupted"
        assert (await rt.db.get("queued"))["status"] == "cancelled"
        rows = await rt.db.list("message", parent="s")
        recovered = json.loads(rows[1]["message"]["content"])
        assert recovered["ok"] and recovered["recovered"]
        assert rt.executions == {}
    finally:
        await rt.close()

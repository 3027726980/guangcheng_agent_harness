import asyncio
import json

import pytest
import pytest_asyncio

from app.context import tool_groups
from app.llm import ModelFailure, ScriptedModel
from app.runtime import Client, DomainError, Runtime
from app.schemas import MessageRequest, ModelReply, RuntimeSettings, SteeringRequest, ToolCall
from app.storage import Database, uid


async def wait_until(predicate, timeout=4):
    async with asyncio.timeout(timeout):
        while not await predicate():
            await asyncio.sleep(0.005)


async def terminal(rt, key):
    async def check():
        return (await rt.db.get(key))["status"] in {"completed", "cancelled", "failed", "limited"}

    await wait_until(check)
    return await rt.db.get(key)


@pytest_asyncio.fixture
async def harness(tmp_path):
    model = ScriptedModel([])
    waits = []

    async def sleep(delay):
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
    return await rt.submit(
        session["id"],
        "A",
        MessageRequest(client_id=client.id, request_id=request_id or uid(), content=content),
    )


async def test_direct_reply_and_request_deduplication(harness):
    rt, model, client, session, _ = harness
    model.replies = [ModelReply(text="你好")]
    run = await send(rt, client, session, request_id="request-1234")
    duplicate = await send(rt, client, session, request_id="request-1234")
    assert duplicate["id"] == run["id"]
    result = await terminal(rt, run["id"])
    assert result["status"] == "completed"
    assert result["model_calls"] == 1
    events = await rt.db.history_events("A")
    assert "test-secret" not in json.dumps(events)


async def test_tool_loop_followup_and_session_isolation(harness):
    rt, model, client, session, _ = harness
    model.replies = [
        ModelReply(calls=[ToolCall(id="calc1", name="calculator", arguments='{"expression":"128*36"}')]),
        ModelReply(
            calls=[ToolCall(id="todo1", name="todo", arguments='{"action":"add","title":"结果4608"}')]
        ),
        ModelReply(text="已计算并记下"),
        ModelReply(text="刚才结果是4608"),
        ModelReply(text="其他会话"),
    ]
    run = await send(rt, client, session)
    assert (await terminal(rt, run["id"]))["status"] == "completed"
    assert "4608" in json.dumps(model.inputs[1])
    follow = await send(rt, client, session, "刚才结果是多少")
    assert (await terminal(rt, follow["id"]))["status"] == "completed"
    assert "4608" in json.dumps(model.inputs[3])
    other = await rt.create_session("A", "独立")
    second = await send(rt, client, other)
    await terminal(rt, second["id"])
    assert "4608" not in json.dumps(model.inputs[4])
    assert len(await rt.db.list("todo", owner="A")) == 1


async def test_three_retries_and_model_budget(harness):
    rt, model, client, session, waits = harness
    model.replies = [ModelFailure("网络失败", True) for _ in range(3)] + [ModelReply(text="恢复")]
    run = await send(rt, client, session)
    result = await terminal(rt, run["id"])
    assert result["status"] == "completed"
    assert result["model_calls"] == 4
    assert waits == [30.0, 30.0, 30.0]
    settings = (await rt.settings()).model_copy(update={"max_model_calls": 1})
    await rt.db.put("settings", {"id": "runtime-settings", **settings.model_dump()})
    model.replies = [ModelFailure("故障", True), ModelReply(text="不应调用")]
    second = await send(rt, client, session)
    result = await terminal(rt, second["id"])
    assert result["status"] == "limited"
    assert len(model.replies) == 1


async def test_partial_output_failure_is_not_retried(harness):
    rt, model, client, session, waits = harness

    async def partial(messages, on_text):
        await on_text("部分输出")
        raise ModelFailure("流失败", True)

    model.replies = [partial, ModelReply(text="不应重试")]
    run = await send(rt, client, session)
    assert (await terminal(rt, run["id"]))["status"] == "failed"
    assert waits == []
    rows = await rt.db.list("message", parent=session["id"])
    assert "部分输出" in rows[-1]["message"]["content"]


async def test_final_answer_steering_remains_in_current_task(harness):
    rt, model, client, session, _ = harness
    entered, release = asyncio.Event(), asyncio.Event()

    async def answer(messages, on_text):
        entered.set()
        await release.wait()
        return ModelReply(text="初稿")

    model.replies = [answer, ModelReply(text="按新要求修正")]
    run = await send(rt, client, session)
    await entered.wait()
    await rt.steer(run["id"], "A", SteeringRequest(content="只要免费资源", request_id="steer-123"))
    release.set()
    result = await terminal(rt, run["id"])
    assert result["status"] == "completed" and result["model_calls"] == 2
    assert "只要免费资源" in json.dumps(model.inputs[1], ensure_ascii=False)
    assert (await rt.db.list("steering", parent=run["id"]))[0]["status"] == "applied"


async def test_manual_stop_advances_queue_but_disconnect_cancels_it(harness):
    rt, model, client, session, _ = harness
    entered = asyncio.Event()

    async def block(messages, on_text):
        await on_text("正在输出")
        entered.set()
        await asyncio.Event().wait()

    model.replies = [block, ModelReply(text="下一条已执行")]
    first = await send(rt, client, session)
    await entered.wait()
    second = await send(rt, client, session)
    await rt.cancel(first["id"], "A")
    assert (await terminal(rt, first["id"]))["reason"] == "user_stop"
    assert (await terminal(rt, second["id"]))["status"] == "completed"
    entered.clear()
    model.replies = [block, ModelReply(text="不应执行")]
    third = await send(rt, client, session)
    await entered.wait()
    fourth = await send(rt, client, session)
    await rt.disconnect(client.id)
    assert (await terminal(rt, third["id"]))["reason"] == "client_disconnect"
    assert (await terminal(rt, fourth["id"]))["status"] == "cancelled"
    assert len(model.replies) == 1


async def test_truncated_tool_response_is_never_executed(harness):
    rt, model, client, session, _ = harness
    model.replies = [
        ModelReply(
            finish_reason="length",
            calls=[ToolCall(id="cut", name="todo", arguments='{"action":"add","title":"不应该创建"}')],
        ),
        ModelReply(text="请重试"),
    ]
    run = await send(rt, client, session)
    await terminal(rt, run["id"])
    assert await rt.db.list("todo", owner="A") == []
    rows = await rt.db.list("message", parent=session["id"])
    tool_groups([r["message"] for r in rows])


async def test_tool_budget_blocks_entire_batch(harness):
    rt, model, client, session, _ = harness
    settings = (await rt.settings()).model_copy(update={"max_tool_calls": 1})
    await rt.db.put("settings", {"id": "runtime-settings", **settings.model_dump()})
    model.replies = [
        ModelReply(
            calls=[
                ToolCall(id="a", name="calculator", arguments='{"expression":"1+1"}'),
                ToolCall(id="b", name="todo", arguments='{"action":"add","title":"不要创建"}'),
            ]
        )
    ]
    run = await send(rt, client, session)
    assert (await terminal(rt, run["id"]))["status"] == "limited"
    assert await rt.db.list("todo", owner="A") == []


async def test_settings_snapshot_and_two_window_isolation(harness):
    rt, model, client, session, _ = harness
    entered, release = asyncio.Event(), asyncio.Event()

    async def block(messages, on_text):
        entered.set()
        await release.wait()
        return ModelReply(text="窗口一")

    model.replies = [block, ModelReply(text="窗口二")]
    first = await send(rt, client, session)
    await entered.wait()
    other_client = Client(uid(), "A", connected=True)
    rt.clients[other_client.id] = other_client
    other_session = await rt.create_session("A", "窗口二")
    settings = (await rt.settings()).model_copy(update={"max_model_calls": 7})
    await rt.db.put("settings", {"id": "runtime-settings", **settings.model_dump()})
    second = await send(rt, other_client, other_session)
    result = await terminal(rt, second["id"])
    assert result["settings"]["max_model_calls"] == 7
    await rt.disconnect(client.id)
    assert (await terminal(rt, first["id"]))["status"] == "cancelled"
    assert (await rt.db.get(first["id"]))["settings"]["max_model_calls"] == 20
    assert (await rt.db.get(second["id"]))["status"] == "completed"


@pytest.mark.parametrize("problem", ["missing", "failed", "summary_missing", "capacity"])
async def test_invalid_configuration_rejected_before_queueing(harness, problem):
    rt, model, client, session, _ = harness
    settings = (await rt.settings()).model_dump()
    if problem == "missing":
        settings["default_profile_id"] = None
    elif problem == "summary_missing":
        settings["summary_profile_id"] = "not-present"
    else:
        profile = await rt.db.get("profile")
        profile.update({"test_status": "failed"} if problem == "failed" else {"context_capacity": 2048})
        await rt.db.put("profile", profile)
    await rt.db.put("settings", {"id": "runtime-settings", **settings})
    with pytest.raises(DomainError) as error:
        await send(rt, client, session)
    assert error.value.status == 409
    assert await rt.db.list("run", parent=session["id"]) == []
    assert model.inputs == []


async def test_deletion_rejects_busy_session_then_hides_history(harness):
    rt, model, client, session, _ = harness
    entered = asyncio.Event()

    async def block(messages, on_text):
        entered.set()
        await asyncio.Event().wait()

    model.replies = [block]
    run = await send(rt, client, session)
    await asyncio.wait_for(entered.wait(), 2)
    queued = await send(rt, client, session)
    with pytest.raises(DomainError) as busy:
        await rt.delete_session(session["id"], "A")
    assert busy.value.status == 409
    await rt.cancel(queued["id"], "A")
    await rt.cancel(run["id"], "A")
    await terminal(rt, run["id"])
    with pytest.raises(DomainError) as forbidden:
        await rt.delete_session(session["id"], "B")
    assert forbidden.value.status == 404
    await rt.delete_session(session["id"], "A")
    with pytest.raises(DomainError):
        await send(rt, client, session)
    assert await rt.db.list("message", parent=session["id"])
    assert (await rt.db.history_events("A"))[-1]["type"] == "session.deleted"

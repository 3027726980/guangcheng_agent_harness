# 作者：LHF。
# 时间：2026-10-20。
# 作用：验证 test_api 所覆盖的行为与边界，使用离线数据及临时资源。
import asyncio

from fastapi.testclient import TestClient

from app.llm import ScriptedModel
from app.main import create_app
from app.runtime import Client
from app.schemas import ModelReply
from app.storage import uid
from tests.test_runtime import send, terminal


class ProbeModel(ScriptedModel):
    async def probe(self, profile):
        # 作用：返回固定的离线连接探测结果，避免测试发起真实请求。
        return {
            "connected": True,
            "context_capacity": 262144,
            "capacity_source": "default:256K",
            "capabilities": "offline_fixture",
        }


def test_manual_todos_use_the_same_tool_registry(tmp_path):
    # 作者：LHF；时间：2026-10-20；作用：验证手动读写待办也经过统一工具注册表。
    app = create_app(str(tmp_path / "registry.db"), ProbeModel([]))
    registry = app.state.runtime.registry
    original = registry.execute
    calls = []

    async def execute(call, db, user_id, operation_id):
        # 作用：记录入口并委托真实工具，检查身份、参数和幂等键没有改变。
        calls.append((call, user_id, operation_id))
        return await original(call, db, user_id, operation_id)

    registry.execute = execute
    with TestClient(app) as client:
        assert client.post("/api/todos", headers={"Idempotency-Key": "registry-1"},
                           json={"action": "add", "title": "统一调用"}).status_code == 200
        assert len(client.get("/api/todos").json()["items"]) == 1
    assert [call.name for call, _, _ in calls] == ["todo", "todo"]
    assert [owner for _, owner, _ in calls] == ["A", "A"]
    assert calls[0][2] == "manual:A:registry-1"
    assert calls[1][2].startswith("read:")


def test_api_identity_models_settings_and_shared_todos(tmp_path):
    # 作用：验证演示身份隔离、模型配置、运行设置、共享待办与会话删除接口。
    app = create_app(str(tmp_path / "api.db"), ProbeModel([ModelReply(text="OK")]))
    with TestClient(app) as client:
        profile = client.post(
            "/api/models",
            json={
                "name": "test",
                "base_url": "http://offline.invalid/v1",
                "api_key": "sensitive-example",
                "model": "test",
            },
        ).json()
        assert profile["test_status"] == "connected"
        assert profile["context_capacity"] == 262144
        assert "sensitive-example" not in client.get("/api/models").text
        settings = client.get("/api/settings").json()
        settings["default_profile_id"] = profile["id"]
        assert client.put("/api/settings", json=settings).status_code == 200
        session = client.post("/api/sessions", json={"title": "A"}).json()
        assert client.get(f"/api/sessions/{session['id']}", headers={"X-Demo-User": "B"}).status_code == 404
        assert client.get("/api/sessions", headers={"X-Demo-User": "B"}).json() == []
        assert client.post("/api/runs/not-present/steer-queued").status_code == 404
        assert (
            client.post(
                "/api/sessions/not-present/compact",
                json={
                    "client_id": "client-missing-123",
                    "request_id": "compact-missing-123",
                },
            ).status_code
            == 404
        )
        response = client.post(
            "/api/todos",
            headers={"Idempotency-Key": "manual-1"},
            json={"action": "add", "title": "跨会话共享"},
        )
        assert response.status_code == 200
        duplicate = client.post(
            "/api/todos",
            headers={"Idempotency-Key": "manual-1"},
            json={"action": "add", "title": "跨会话共享"},
        )
        assert duplicate.json() == response.json()
        assert len(client.get("/api/todos").json()["items"]) == 1
        assert client.get("/api/todos", headers={"X-Demo-User": "B"}).json()["items"] == []
        settings["context_target"] = 0.9
        assert client.put("/api/settings", json=settings).status_code == 422
        assert (
            client.delete(f"/api/sessions/{session['id']}", headers={"X-Demo-User": "B"}).status_code == 404
        )
        assert client.delete(f"/api/sessions/{session['id']}").status_code == 200
        assert client.get("/api/sessions").json() == []
        assert client.get(f"/api/sessions/{session['id']}").status_code == 404
        assert len(client.get("/api/todos").json()["items"]) == 1


async def test_sse_disconnect_cancels_owned_active_and_queued_runs(harness, tmp_path):
    # 作用：验证 SSE 断开后只取消该客户端的运行任务和排队任务。
    fixture_rt, _, _, _, _ = harness
    entered, ready, disconnected = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def block(messages, on_text):
        # 作用：阻塞模拟模型直至测试释放或取消，用于 SSE 断开后只取消该客户端的运行任务和排队任务。
        entered.set()
        await asyncio.Event().wait()

    app = create_app(str(tmp_path / "sse.db"), ScriptedModel([block]))
    first_request = True

    async def receive():
        # 作用：模拟 ASGI 接收客户端请求与断开通知。
        nonlocal first_request
        if first_request:
            first_request = False
            return {"type": "http.request", "body": b"", "more_body": False}
        await disconnected.wait()
        return {"type": "http.disconnect"}

    async def output(message):
        # 作用：接收模拟输出，供测试观察事件发送或流错误。
        if message["type"] == "http.response.body" and b"event: ready" in message.get("body", b""):
            ready.set()

    async with app.router.lifespan_context(app):
        rt = app.state.runtime
        await rt.db.put("profile", await fixture_rt.db.get("profile"))
        await rt.db.put("settings", await fixture_rt.db.get("runtime-settings"))
        client = Client(uid(), "A", connected=True)
        rt.clients[client.id] = client
        session = await rt.create_session("A", "断线测试")
        active = await send(rt, client, session)
        await asyncio.wait_for(entered.wait(), 2)
        queued = await send(rt, client, session)
        client.connected = False
        # Real ASGI request and StreamingResponse, without starting a server.
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/events",
            "headers": [],
            "query_string": f"client_id={client.id}".encode(),
            "asgi": {"spec_version": "2.3"},
            "http_version": "1.1",
            "scheme": "http",
        }
        task = asyncio.create_task(app(scope, receive, output))
        await asyncio.wait_for(ready.wait(), 2)
        disconnected.set()
        await asyncio.wait_for(task, 2)
        assert (await terminal(rt, active["id"]))["status"] == "cancelled"
        assert (await terminal(rt, queued["id"]))["status"] == "cancelled"
        assert client.closed


def test_session_list_reports_only_owned_pending_runs(tmp_path):
    # 作用：验证会话列表只返回当前用户的会话及未结束任务概要。
    app = create_app(str(tmp_path / "activity.db"), ProbeModel([]))
    with TestClient(app) as client:
        first = client.post("/api/sessions", json={"title": "窗口一"}).json()
        second = client.post("/api/sessions", json={"title": "窗口二"}).json()
        other = client.post("/api/sessions", json={"title": "B"}, headers={"X-Demo-User": "B"}).json()
        for index, status in enumerate(
            ("queued", "running", "cancelling", "completed", "failed", "cancelled", "limited", "interrupted")
        ):
            client.portal.call(
                app.state.runtime.db.put,
                "run",
                {
                    "id": f"run-{index}",
                    "session_id": first["id"],
                    "status": status,
                    "private_payload": "must-not-appear",
                },
                "A",
                first["id"],
            )
        client.portal.call(
            app.state.runtime.db.put,
            "run",
            {
                "id": "run-b",
                "session_id": other["id"],
                "status": "running",
            },
            "B",
            other["id"],
        )
        listed = client.get("/api/sessions").json()
        assert listed[0]["active_runs"] == [
            {"id": "run-0", "status": "queued"},
            {"id": "run-1", "status": "running"},
            {"id": "run-2", "status": "cancelling"},
        ]
        assert listed[1]["id"] == second["id"] and listed[1]["active_runs"] == []
        assert "private_payload" not in str(listed) and "run-b" not in str(listed)
        assert client.get("/api/sessions", headers={"X-Demo-User": "B"}).json()[0]["active_runs"] == [
            {"id": "run-b", "status": "running"}
        ]

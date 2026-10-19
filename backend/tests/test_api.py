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
        return {
            "connected": True,
            "context_capacity": 262144,
            "capacity_source": "default:256K",
            "capabilities": "offline_fixture",
        }


def test_api_identity_models_settings_and_shared_todos(tmp_path):
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
    fixture_rt, _, _, _, _ = harness
    entered, ready, disconnected = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def block(messages, on_text):
        entered.set()
        await asyncio.Event().wait()

    app = create_app(str(tmp_path / "sse.db"), ScriptedModel([block]))
    first_request = True

    async def receive():
        nonlocal first_request
        if first_request:
            first_request = False
            return {"type": "http.request", "body": b"", "more_body": False}
        await disconnected.wait()
        return {"type": "http.disconnect"}

    async def output(message):
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

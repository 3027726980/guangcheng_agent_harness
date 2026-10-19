from fastapi.testclient import TestClient

from app.llm import ScriptedModel
from app.main import create_app
from app.schemas import ModelReply


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

# 作者：LHF；时间：2026-10-23；作用：在进程内验证工具目录及会话创建读取入口。
from fastapi.testclient import TestClient

from app.llm import ScriptedModel
from app.main import create_app


def test_api_tools_and_independent_sessions(tmp_path):
    # 作用：公开目录来自三个注册工具，两个会话有独立身份和历史容器。
    app = create_app(str(tmp_path / "api.db"), ScriptedModel([]))
    with TestClient(app) as client:
        tools = client.get("/api/tools")
        assert tools.status_code == 200
        assert {tool["name"] for tool in tools.json()} == {"calculator", "search", "todo"}
        first = client.post("/api/sessions", json={"title": "窗口一"})
        second = client.post("/api/sessions", json={"title": "窗口二"})
        assert first.status_code == second.status_code == 200
        assert first.json()["id"] != second.json()["id"]
        for session in [first.json(), second.json()]:
            response = client.get(f"/api/sessions/{session['id']}")
            assert response.status_code == 200
            assert response.json()["messages"] == []

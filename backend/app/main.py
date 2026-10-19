"""FastAPI shell: demo identity, CRUD, task submission and SSE, not an agent framework."""

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

from app.llm import ModelFailure
from app.runtime import Client, DomainError, Runtime
from app.schemas import (
    MessageRequest,
    ModelProfile,
    RuntimeSettings,
    SessionCreate,
    SteeringRequest,
    TodoArgs,
)
from app.storage import Database, uid
from app.tools import ToolError, todo


def public_profile(profile):
    return {key: value for key, value in profile.items() if key != "api_key"} | {
        "has_api_key": bool(profile.get("api_key")),
        "api_key": "",
    }


def create_app(database_path=None, model=None):
    path = database_path or os.environ.get(
        "HARNESS_DB", str(Path(__file__).resolve().parents[1] / ".data/harness.db")
    )
    runtime = Runtime(Database(path), model=model)

    @asynccontextmanager
    async def lifespan(app):
        await runtime.initialize()
        yield
        await runtime.close()

    app = FastAPI(title="Agent Harness", version="0.1.0", lifespan=lifespan)
    app.state.runtime = runtime

    @app.exception_handler(DomainError)
    async def domain_error(request, error):
        return JSONResponse({"detail": str(error)}, status_code=error.status)

    @app.exception_handler(ToolError)
    async def tool_error(request, error):
        return JSONResponse(
            {"detail": str(error), "code": error.code},
            status_code=409 if error.code == "version_conflict" else 400,
        )

    @app.exception_handler(ModelFailure)
    async def model_error(request, error):
        return JSONResponse({"detail": str(error)}, status_code=502)

    @app.exception_handler(ValidationError)
    async def validation_error(request, error):
        return JSONResponse({"detail": str(error)}, status_code=422)

    async def user(x_demo_user: str = Header(default="A")):
        if x_demo_user not in {"A", "B"}:
            raise HTTPException(400, "演示用户仅支持 A / B")
        return x_demo_user

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "runtime": "self_implemented", "identity": "demo_only"}

    @app.get("/api/users")
    async def users():
        return await runtime.db.list("user")

    @app.post("/api/clients")
    async def register_client(owner=Depends(user)):
        client = Client(uid(), owner)
        runtime.clients[client.id] = client
        return {"client_id": client.id}

    @app.get("/api/events")
    async def subscribe(request: Request, client_id: str, owner=Depends(user)):
        client = runtime.clients.get(client_id)
        if not client or client.closed or client.user_id != owner or client.connected:
            raise DomainError("客户端连接不存在、已关闭或重复连接", 409)
        client.connected = True

        async def stream():
            try:
                yield "event: ready\ndata: {}\n\n"
                while not client.closed:
                    if await request.is_disconnected():
                        break
                    try:
                        event = await asyncio.wait_for(client.queue.get(), 1)
                    except TimeoutError:
                        yield ": heartbeat\n\n"
                        continue
                    if event is None:
                        break
                    yield f"id: {event['id']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
            finally:
                await asyncio.shield(runtime.disconnect(client.id))

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/clients/{client_id}/disconnect")
    async def disconnect(client_id: str, owner=Depends(user)):
        client = runtime.clients.get(client_id)
        if not client or client.user_id != owner:
            raise DomainError("客户端不存在", 404)
        await runtime.disconnect(client_id)
        return {"disconnected": True}

    @app.get("/api/sessions")
    async def sessions(owner=Depends(user)):
        items = [item for item in await runtime.db.list("session", owner=owner) if not item.get("deleted")]
        active = {item["id"]: [] for item in items}
        for run in await runtime.db.list("run", owner=owner):
            if run["session_id"] in active and run["status"] in {"queued", "running", "cancelling"}:
                active[run["session_id"]].append({"id": run["id"], "status": run["status"]})
        return [{**item, "active_runs": active[item["id"]]} for item in items]

    @app.post("/api/sessions")
    async def create_session(body: SessionCreate, owner=Depends(user)):
        return await runtime.create_session(owner, body.title)

    @app.delete("/api/sessions/{session_id}")
    async def delete_session(session_id: str, owner=Depends(user)):
        return await runtime.delete_session(session_id, owner)

    @app.get("/api/sessions/{session_id}")
    async def session_detail(session_id: str, owner=Depends(user)):
        session = await runtime.session(session_id, owner)
        return {
            "session": session,
            "messages": await runtime.db.list("message", parent=session_id),
            "runs": await runtime.db.list("run", parent=session_id),
            "summary": await runtime.db.get("summary:" + session_id),
            "events": await runtime.db.history_events(owner, session_id),
        }

    @app.post("/api/sessions/{session_id}/messages")
    async def send_message(session_id: str, body: MessageRequest, owner=Depends(user)):
        return runtime.public_run(await runtime.submit(session_id, owner, body))

    @app.post("/api/runs/{run_id}/steering")
    async def steer(run_id: str, body: SteeringRequest, owner=Depends(user)):
        return await runtime.steer(run_id, owner, body)

    @app.post("/api/runs/{run_id}/cancel")
    async def cancel(run_id: str, owner=Depends(user)):
        return await runtime.cancel(run_id, owner)

    @app.get("/api/todos")
    async def todos(owner=Depends(user)):
        return await todo(runtime.db, owner, TodoArgs(action="list"), "read:" + uid())

    @app.post("/api/todos")
    async def change_todo(body: TodoArgs, request: Request, owner=Depends(user)):
        operation = request.headers.get("Idempotency-Key")
        if not operation or len(operation) > 100:
            raise DomainError("写入需要不超过100字符的 Idempotency-Key")
        result = await todo(runtime.db, owner, body, f"manual:{owner}:{operation}")
        await runtime.emit("todo.changed", {}, user_id=owner)
        return result

    @app.get("/api/settings")
    async def settings(owner=Depends(user)):
        return (await runtime.settings()).model_dump()

    @app.put("/api/settings")
    async def save_settings(body: RuntimeSettings, owner=Depends(user)):
        for key in (body.default_profile_id, body.summary_profile_id):
            if key:
                profile = await runtime.db.get(key)
                if not profile or profile.get("kind") != "profile":
                    raise DomainError("所选模型配置不存在")
                if profile.get("test_status") != "connected":
                    raise DomainError("请先完成所选模型的连接测试")
        await runtime.db.put("settings", {"id": "runtime-settings", **body.model_dump()})
        await runtime.emit("settings.changed", {})
        return body

    @app.get("/api/models")
    async def profiles(owner=Depends(user)):
        return [public_profile(item) for item in await runtime.db.list("profile")]

    async def save_profile(body, key=None):
        old = await runtime.db.get(key) if key else None
        if key and (not old or old.get("kind") != "profile"):
            raise DomainError("模型配置不存在", 404)
        data = body.model_dump()
        if old and not data["api_key"]:
            data["api_key"] = old.get("api_key", "")
        profile = {
            "id": key or uid(),
            "kind": "profile",
            **data,
            "context_capacity": 262144,
            "capacity_source": "default:256K",
            "tested_at": time.time(),
        }
        try:
            test = await runtime.model.probe(profile)
            profile.update(test, test_status="connected")
        except (ModelFailure, httpx.HTTPError) as error:
            # Never store raw SDK errors, request objects, or credentials in diagnostics.
            profile.update(test_status="failed", test_error=type(error).__name__)
        await runtime.db.put("profile", profile)
        await runtime.emit("models.changed", {})
        return public_profile(profile)

    @app.post("/api/models")
    async def add_profile(body: ModelProfile, owner=Depends(user)):
        return await save_profile(body)

    @app.put("/api/models/{profile_id}")
    async def update_profile(profile_id: str, body: ModelProfile, owner=Depends(user)):
        return await save_profile(body, profile_id)

    @app.post("/api/models/{profile_id}/test")
    async def test_profile(profile_id: str, owner=Depends(user)):
        profile = await runtime.db.get(profile_id)
        if not profile or profile.get("kind") != "profile":
            raise DomainError("模型配置不存在", 404)
        body = ModelProfile.model_validate({k: profile[k] for k in ModelProfile.model_fields if k in profile})
        return await save_profile(body, profile_id)

    @app.delete("/api/models/{profile_id}")
    async def delete_profile(profile_id: str, owner=Depends(user)):
        settings = await runtime.settings()
        if profile_id in {settings.default_profile_id, settings.summary_profile_id}:
            raise DomainError("请先取消使用该模型再删除", 409)
        profile = await runtime.db.get(profile_id)
        if not profile or profile.get("kind") != "profile":
            raise DomainError("模型配置不存在", 404)
        await runtime.db.remove(profile_id)
        await runtime.emit("models.changed", {})
        return {"deleted": True}

    return app


app = create_app()

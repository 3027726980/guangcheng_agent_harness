# 作者：LHF。
# 注释维护时间：2026-10-20。
# 文件作用：FastAPI 接口、应用生命周期与 SSE 事件订阅。
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
from app.model_protocol import thinking_enabled
from app.runtime import Client, DomainError, Runtime
from app.schemas import (
    CompactionRequest,
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
    # 返回连接配置时隐藏真实密钥，使用 has_api_key 告知前端是否已经保存。
    return {key: value for key, value in profile.items() if key not in {"api_key", "reasoning_effort"}} | {
        "has_api_key": bool(profile.get("api_key")),
        "api_key": "",
        "thinking_enabled": thinking_enabled(profile),
    }


def create_app(database_path=None, model=None):
    # 应用工厂允许离线测试注入临时数据库和假模型；正常启动使用环境变量或默认路径。
    path = database_path or os.environ.get(
        "HARNESS_DB", str(Path(__file__).resolve().parents[1] / ".data/harness.db")
    )
    runtime = Runtime(Database(path), model=model)

    @asynccontextmanager
    async def lifespan(app):
        # 初始化与退出跟随 ASGI 生命周期，模块导入本身不启动调度任务。
        await runtime.initialize()
        yield
        await runtime.close()

    app = FastAPI(title="Agent Harness", version="0.1.0", lifespan=lifespan)
    app.state.runtime = runtime

    @app.exception_handler(DomainError)
    async def domain_error(request, error):
        # 作用：将业务校验异常转成对应 HTTP 状态与 detail 提示。
        return JSONResponse({"detail": str(error)}, status_code=error.status)

    @app.exception_handler(ToolError)
    async def tool_error(request, error):
        # 作用：将工具错误转成结构化响应，版本冲突返回 409。
        return JSONResponse(
            {"detail": str(error), "code": error.code},
            status_code=409 if error.code == "version_conflict" else 400,
        )

    @app.exception_handler(ModelFailure)
    async def model_error(request, error):
        # 作用：将模型适配层异常转成 502 响应，避免泄漏原始供应商请求。
        return JSONResponse({"detail": str(error)}, status_code=502)

    @app.exception_handler(ValidationError)
    async def validation_error(request, error):
        # 作用：将运行期间出现的数据校验错误转成 422 响应。
        return JSONResponse({"detail": str(error)}, status_code=422)

    async def user(x_demo_user: str = Header(default="A")):
        # 演示身份来自请求头，只用于样例用户隔离，不是生产环境认证机制。
        if x_demo_user not in {"A", "B"}:
            raise HTTPException(400, "演示用户仅支持 A / B")
        return x_demo_user

    @app.get("/api/health")
    async def health():
        # 接口 GET /api/health：返回进程健康状态和当前运行方式，不调用模型。
        return {"status": "ok", "runtime": "self_implemented", "identity": "demo_only"}

    @app.get("/api/users")
    async def users():
        # 接口 GET /api/users：列出演示用户，供界面切换身份。
        return await runtime.db.list("user")

    @app.get("/api/tools")
    async def available_tools(owner=Depends(user)):
        # 接口 GET /api/tools：前端 @ 菜单直接读取注册表，新增工具时不需要另维护一份可调用名称。
        return [{"name": tool.name, "description": tool.description}
                for tool in runtime.registry.tools.values()]

    @app.post("/api/clients")
    async def register_client(owner=Depends(user)):
        # 接口 POST /api/clients：注册后还需成功订阅 SSE；Runtime 只接受已建立事件连接的客户端提交任务。
        client = Client(uid(), owner)
        runtime.clients[client.id] = client
        return {"client_id": client.id}

    @app.get("/api/events")
    async def subscribe(request: Request, client_id: str, owner=Depends(user)):
        # 接口 GET /api/events：一个 client_id 只能建立一条有效事件连接，归属必须与演示用户一致。
        client = runtime.clients.get(client_id)
        if not client or client.closed or client.user_id != owner or client.connected:
            raise DomainError("客户端连接不存在、已关闭或重复连接", 409)
        client.connected = True

        async def stream():
            # ready 通知前端可以提交任务；心跳注释维持连接，不作为业务事件处理。
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
                # 即使流被取消，也要执行断连收尾，取消此客户端的运行及排队任务。
                await asyncio.shield(runtime.disconnect(client.id))

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/clients/{client_id}/disconnect")
    async def disconnect(client_id: str, owner=Depends(user)):
        # 接口 POST /api/clients/{client_id}/disconnect：核对客户端归属后断开事件连接，并取消该客户端的任务。
        client = runtime.clients.get(client_id)
        if not client or client.user_id != owner:
            raise DomainError("客户端不存在", 404)
        await runtime.disconnect(client_id)
        return {"disconnected": True}

    @app.get("/api/sessions")
    async def sessions(owner=Depends(user)):
        # 接口 GET /api/sessions：列表附带各会话的活跃任务，侧栏无需逐个加载会话详情即可展示执行状态。
        items = [item for item in await runtime.db.list("session", owner=owner) if not item.get("deleted")]
        active = {item["id"]: [] for item in items}
        for run in await runtime.db.list("run", owner=owner):
            if run["session_id"] in active and run["status"] in {"queued", "running", "cancelling"}:
                active[run["session_id"]].append({"id": run["id"], "status": run["status"]})
        return [{**item, "active_runs": active[item["id"]]} for item in items]

    @app.post("/api/sessions")
    async def create_session(body: SessionCreate, owner=Depends(user)):
        # 接口 POST /api/sessions：为当前演示用户创建独立聊天会话。
        return await runtime.create_session(owner, body.title)

    @app.delete("/api/sessions/{session_id}")
    async def delete_session(session_id: str, owner=Depends(user)):
        # 接口 DELETE /api/sessions/{session_id}：检查任务已结束后软删除当前用户的会话。
        return await runtime.delete_session(session_id, owner)

    @app.get("/api/sessions/{session_id}")
    async def session_detail(session_id: str, owner=Depends(user)):
        # 接口 GET /api/sessions/{session_id}：重连和切换会话时一次返回消息、任务、摘要及事件，恢复页面的持久化视图。
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
        # 接口 POST /api/sessions/{session_id}/messages：立即返回排队任务，后续输出通过事件流到达，不阻塞本次 HTTP 请求。
        return runtime.public_run(await runtime.submit(session_id, owner, body))

    @app.post("/api/sessions/{session_id}/compact")
    async def compact_context(session_id: str, body: CompactionRequest, owner=Depends(user)):
        # 接口 POST /api/sessions/{session_id}/compact：压缩作为独立任务提交，沿用预算、取消和运行状态通知。
        return runtime.public_run(await runtime.submit(session_id, owner, body, purpose="context_compaction"))

    @app.post("/api/runs/{run_id}/steering")
    async def steer(run_id: str, body: SteeringRequest, owner=Depends(user)):
        # 接口 POST /api/runs/{run_id}/steering：将补充要求登记为正在运行任务的待生效引导。
        return await runtime.steer(run_id, owner, body)

    @app.post("/api/runs/{run_id}/cancel")
    async def cancel(run_id: str, owner=Depends(user)):
        # 接口 POST /api/runs/{run_id}/cancel：请求取消指定任务，并返回当前取消进度。
        return await runtime.cancel(run_id, owner)

    @app.post("/api/runs/{run_id}/steer-queued")
    async def steer_queued(run_id: str, owner=Depends(user)):
        # 接口 POST /api/runs/{run_id}/steer-queued：把排队消息转成运行任务的引导，并取消原排队项。
        return await runtime.steer_queued(run_id, owner)

    @app.get("/api/todos")
    async def todos(owner=Depends(user)):
        # 接口 GET /api/todos：查询当前用户跨会话共享且未删除的待办。
        return await todo(runtime.db, owner, TodoArgs(action="list"), "read:" + uid())

    @app.post("/api/todos")
    async def change_todo(body: TodoArgs, request: Request, owner=Depends(user)):
        # 接口 POST /api/todos：手动操作也必须提供幂等键，和 Agent 工具共用同一待办事务实现。
        operation = request.headers.get("Idempotency-Key")
        if not operation or len(operation) > 100:
            raise DomainError("写入需要不超过100字符的 Idempotency-Key")
        result = await todo(runtime.db, owner, body, f"manual:{owner}:{operation}")
        await runtime.emit("todo.changed", {}, user_id=owner)
        return result

    @app.get("/api/settings")
    async def settings(owner=Depends(user)):
        # 接口 GET /api/settings：返回全局运行预算、压缩阈值和模型选择。
        return (await runtime.settings()).model_dump()

    @app.put("/api/settings")
    async def save_settings(body: RuntimeSettings, owner=Depends(user)):
        # 接口 PUT /api/settings：全局配置只允许引用测试通过的模型；已开始执行的任务使用自己的配置快照。
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
        # 接口 GET /api/models：列出模型连接配置，使用公开视图隐藏密钥明文。
        return [public_profile(item) for item in await runtime.db.list("profile")]

    async def save_profile(body, key=None):
        # 保存时真实测试连接并读取容量；失败配置仍保留，便于用户修正后重试。
        old = await runtime.db.get(key) if key else None
        if key and (not old or old.get("kind") != "profile"):
            raise DomainError("模型配置不存在", 404)
        data = body.model_dump()
        if old and not data["api_key"]:
            # 前端不回显密钥，编辑时留空表示沿用数据库中已保存的密钥。
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
            # 只保存异常类型，不记录可能携带密钥的 SDK 原始错误或请求对象。
            profile.update(test_status="failed", test_error=type(error).__name__)
        await runtime.db.put("profile", profile)
        await runtime.emit("models.changed", {})
        return public_profile(profile)

    @app.post("/api/models")
    async def add_profile(body: ModelProfile, owner=Depends(user)):
        # 接口 POST /api/models：新增模型连接，测试可用性并保存探测结果。
        return await save_profile(body)

    @app.put("/api/models/{profile_id}")
    async def update_profile(profile_id: str, body: ModelProfile, owner=Depends(user)):
        # 接口 PUT /api/models/{profile_id}：更新已有模型连接并重新测试，密钥留空时保留原值。
        return await save_profile(body, profile_id)

    @app.post("/api/models/{profile_id}/test")
    async def test_profile(profile_id: str, owner=Depends(user)):
        # 接口 POST /api/models/{profile_id}/test：使用数据库中已保存的连接配置重新测试模型。
        profile = await runtime.db.get(profile_id)
        if not profile or profile.get("kind") != "profile":
            raise DomainError("模型配置不存在", 404)
        # 重测旧记录时保留原启用状态，只迁移为布尔开关，不重新保存旧强度字段。
        body = ModelProfile.model_validate({
            **{k: profile[k] for k in ModelProfile.model_fields if k in profile},
            "thinking_enabled": thinking_enabled(profile),
        })
        return await save_profile(body, profile_id)

    @app.delete("/api/models/{profile_id}")
    async def delete_profile(profile_id: str, owner=Depends(user)):
        # 接口 DELETE /api/models/{profile_id}：拒绝删除仍被全局设置引用的模型连接，其他连接可移除。
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


# ASGI 入口：从 backend 目录运行 python -m uvicorn app.main:app。
app = create_app()

# 作者：LHF。
# 注释维护时间：2026-10-21。
# 文件作用：基于 Run 数据模型的会话调度、Agent 循环、预算控制、取消与恢复。
"""Own Agent Loop and session scheduler; all mutation boundaries are explicit."""

# 核心执行链：submit 入队 → _lane 按会话调度 → _execute 循环调用模型与工具。
# 消息、任务、事件均落库；内存中的 Task 和客户端队列只负责本次进程内的执行。

import asyncio
import json
import time
import traceback
from copy import deepcopy
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.context import ContextFailure, ContextManager
from app.diagnostics import Diagnostics
from app.llm import ModelFailure, OpenAIModel, ScriptedModel
from app.prompts import PromptError
from app.request_capture import capture_request, request_body, request_recorder
from app.run import ModelSnapshot, Run
from app.schemas import RuntimeSettings
from app.storage import Database, uid
from app.tool.base import ToolError
from app.tool.registry import ToolRegistry

# 终态任务不再被调度；cancelling 仍需等待工具收尾，不能提前视为已取消。
TERMINAL = {"completed", "cancelled", "failed", "interrupted", "limited"}


class BudgetExceeded(Exception):
    pass


def validate_finish_reason(reply):
    # 作者：LHF；时间：2026-10-22；作用：校验对话响应的结束状态与内容，异常输出不得进入工具执行。
    failures = {
        "length": "模型输出因上下文或输出长度限制被截断（length），未执行工具",
        "content_filter": "模型输出被过滤（content_filter），未执行工具",
        "insufficient_system_resource": "模型推理资源不足（insufficient_system_resource），未执行工具",
        "aborted": "模型生成被中断（aborted），未执行工具",
    }
    reason = reply.finish_reason
    if reason in failures:
        # 供应商中断不等于用户取消；默认结束当前 Run，不自动重试或继续执行残缺调用。
        raise ModelFailure(failures[reason])
    if reply.calls:
        if reason != "tool_calls":
            raise ModelFailure(f"工具调用结束原因异常（{reason or '缺失'}），未执行工具")
    elif reason == "tool_calls":
        raise ModelFailure("模型以 tool_calls 结束但没有返回工具调用")
    elif reason not in {"stop", "end_turn"}:
        # end_turn 是现有普通回答兼容值；未知值和缺失值均不能视为正常完成。
        raise ModelFailure(f"模型输出结束原因异常（{reason or '缺失'}）")


class DomainError(Exception):
    def __init__(self, message, status=400):
        # 作用：保存业务错误提示和供接口层返回的 HTTP 状态码。
        self.status = status
        super().__init__(message)


@dataclass
class Client:
    # 一个浏览器连接对应一个客户端；有界队列防止慢消费者无限堆积事件。
    id: str
    user_id: str
    # 作用：为每个客户端独立创建有界事件队列，不在实例之间共享队列。
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=2000))
    connected: bool = False
    closed: bool = False


class Runtime:
    def __init__(self, db: Database, model=None, sleep=asyncio.sleep):
        # 作用：装配数据库、模型、工具与上下文模块，并建立客户端和会话调度状态。
        self.db = db
        self.model = model or OpenAIModel()
        self.registry = ToolRegistry()
        self.context = ContextManager(db)
        self.diagnostics = Diagnostics()
        self.logging_error = None
        self.sleep = sleep
        self.clients: dict[str, Client] = {}
        # 每个会话一条调度通道，因此同会话串行、不同会话可以并行。
        self.lanes: dict[str, asyncio.Task] = {}
        # executions 保存可取消的执行任务，active 保存正在变化的运行状态。
        self.executions: dict[str, asyncio.Task] = {}
        self.active: dict[str, Run] = {}
        # 提交、取消、引导和任务完成共用此锁，避免状态检查后被其他协程抢先改变。
        self.control = asyncio.Lock()
        self.shutting_down = False

    async def initialize(self):
        # 服务重启后仅修复历史状态，不自动重放可能已经产生副作用的任务。
        await self.db.initialize()
        await self.diagnostics.write("app", {"type": "startup", "timestamp": time.time()})
        if not await self.db.get("runtime-settings"):
            await self.db.put("settings", {"id": "runtime-settings", **RuntimeSettings().model_dump()})
        for user in ("A", "B"):
            await self.db.put("user", {"id": user, "name": f"演示用户 {user}"})
        for run in await self.list_runs():
            if run.status not in TERMINAL:
                queued = run.status == "queued"
                run.status = "cancelled" if queued else "interrupted"
                run.reason = "server_restart"
                run.ended_at = time.time()
                await self.db.put("run", run.to_record())
                await self.repair_calls(run)
                await self.emit("run.updated", self.public_run(run), run)

    async def settings(self):
        # 数据库记录的 id 不属于配置字段，先去掉再做严格校验。
        data = await self.db.get("runtime-settings")
        return RuntimeSettings.model_validate({key: value for key, value in data.items() if key != "id"})

    async def emit(self, kind, data, run: Run | None = None, user_id=None, session_id=None):
        # 先持久化再广播；owner=None 表示全局事件，否则仅发送给对应演示用户。
        owner = run.user_id if run else user_id
        event = await self.db.append_event(
            kind, data, owner, run.session_id if run else session_id, run.id if run else None
        )
        await self.diagnostics.event(event)
        self._broadcast(event)
        await self.report_logging_status()
        return event

    def _broadcast(self, event):
        # 作者：LHF；时间：2026-10-22；作用：仅向当前用户有效连接分发事件。
        owner = event["user_id"]
        for client in tuple(self.clients.values()):
            if not client.closed and client.connected and (owner is None or client.user_id == owner):
                if client.queue.full():
                    # 队列满时断开连接，由前端重连后重新读取历史快照。
                    asyncio.create_task(self.disconnect(client.id))
                    continue
                client.queue.put_nowait(event)

    async def report_logging_status(self):
        # 作者：LHF；时间：2026-10-22；作用：日志故障仅通知一次，不递归写故障日志。
        error = self.diagnostics.error
        if error and error != self.logging_error:
            self.logging_error = dict(error)
            notice = await self.db.append_event("logging.status", error)
            self._broadcast(notice)

    @staticmethod
    def public_run(run: Run | dict) -> dict:
        # 作用：在统一模型上序列化任务；模型字段定义负责排除密钥和流式临时文本。
        return Run.model_validate(run).to_record()

    async def get_run(self, run_id: str) -> Run | None:
        # 作用：按 ID 读取并校验任务，其他类型的记录不作为 Run 返回。
        data = await self.db.get(run_id)
        if not data or not {"session_id", "user_id", "client_id"} <= data.keys():
            return None
        return Run.model_validate(data)

    async def list_runs(self, owner=None, parent=None) -> list[Run]:
        # 作用：将数据库任务列表转换为明确的数据模型，保留原有入队顺序。
        return [Run.model_validate(data) for data in await self.db.list("run", owner=owner, parent=parent)]

    async def session(self, session_id, user_id):
        # 统一检查记录类型、归属和软删除状态，避免仅凭 ID 读取其他用户会话。
        session = await self.db.get(session_id)
        if (
            not session
            or session.get("user_id") != user_id
            or session.get("kind") != "session"
            or session.get("deleted")
        ):
            raise DomainError("会话不存在或不属于当前演示用户", 404)
        await self.context.state.ensure_loaded(session_id)
        return session

    async def delete_session(self, session_id, user_id):
        # 仅标记删除，保留历史记录；存在未结束任务时拒绝删除。
        async with self.control:
            session = await self.session(session_id, user_id)
            runs = await self.list_runs(parent=session_id)
            if any(run.status not in TERMINAL for run in runs):
                raise DomainError("请先停止当前任务并取消排队消息，再删除对话", 409)
            session.update(deleted=True, deleted_at=time.time())
            await self.db.put("session", session)
            self.context.state.evict(session_id)
            await self.emit("session.deleted", {"id": session_id}, user_id=user_id, session_id=session_id)
            return {"deleted": True, "id": session_id}

    async def configured_models(self, settings):
        # 作者：LHF；时间：2026-10-21；作用：校验模型配置和连接状态，实际输入容量由 ContextManager 检查。
        profiles = []
        for label, key in (
            ("对话", settings.default_profile_id),
            ("摘要", settings.summary_profile_id or settings.default_profile_id),
        ):
            profile = await self.db.get(key) if key else None
            if not profile or profile.get("kind") != "profile":
                raise DomainError(f"请先在全局设置中配置并选择{label}模型", 409)
            if profile.get("test_status") != "connected":
                raise DomainError(f"{label}模型连接测试未通过，请在全局设置中重新测试", 409)
            self.diagnostics.remember_secret(profile.get("api_key"))
            profiles.append(profile)
        return profiles

    async def create_session(self, user_id, title):
        # 会话只绑定当前用户；共享待办另按用户存储，不挂在会话下面。
        session = {
            "id": uid(),
            "kind": "session",
            "user_id": user_id,
            "title": title,
            "created_at": time.time(),
        }
        await self.db.put("session", session, owner=user_id)
        await self.emit("session.created", session, user_id=user_id, session_id=session["id"])
        return session

    async def submit(self, session_id, user_id, request, purpose="chat"):
        # HTTP 仅创建排队任务；执行与结果通知交由调度通道和 SSE 完成。
        async with self.control:
            await self.session(session_id, user_id)
            client = self.clients.get(request.client_id)
            if not client or not client.connected or client.closed or client.user_id != user_id:
                raise DomainError("事件连接尚未就绪，请等待连接成功后发送", 409)
            request_key = f"request:{user_id}:{request.client_id}:{request.request_id}"
            # 相同客户端重复提交同一请求时返回原任务，防止网络重试导致重复执行。
            previous = await self.db.get(request_key)
            if previous:
                return self.public_run(await self.get_run(previous["run_id"]))
            tool_names = self.validate_tools(getattr(request, "tool_names", []))
            if purpose == "context_compaction" and any(
                run.status not in TERMINAL for run in await self.list_runs(parent=session_id)
            ):
                raise DomainError("请等待当前任务和排队消息完成后再手动压缩", 409)
            await self.configured_models(await self.settings())
            run = Run(
                id=uid(),
                session_id=session_id,
                user_id=user_id,
                client_id=request.client_id,
                content="手动压缩上下文" if purpose == "context_compaction" else request.content,
                purpose=purpose,
                status="queued",
                created_at=time.time(),
                model_calls=0,
                tool_calls=0,
                reason=None,
                tool_names=tool_names,
            )
            async with self.db.transaction() as connection:
                # 任务和请求索引一起提交，不能出现已入队却无法识别重复请求的半成品。
                await self.db.put(
                    "run", run.to_record(), owner=user_id, parent=session_id, connection=connection
                )
                await self.db.put("request", {"id": request_key, "run_id": run.id}, connection=connection)
            await self.emit("run.updated", self.public_run(run), run)
            if session_id not in self.lanes or self.lanes[session_id].done():
                self.lanes[session_id] = asyncio.create_task(self._lane(session_id))
            return self.public_run(run)

    def validate_tools(self, names):
        # 作者：LHF；时间：2026-10-21；作用：校验用户工具偏好，拒绝未知及仅供模型调用的工具。
        unknown = set(names) - self.registry.user_tools().keys()
        if unknown:
            raise DomainError("未知或不可由用户选择的工具：" + "、".join(sorted(unknown)))
        return list(dict.fromkeys(names))

    async def steer(self, run_id, user_id, request):
        # 引导先以 pending 保存，在循环边界再作为用户消息加入上下文。
        async with self.control:
            run = await self.get_run(run_id)
            if not run or run.user_id != user_id:
                raise DomainError("任务不存在", 404)
            if run.status != "running":
                raise DomainError("当前任务已不在运行，请作为新消息发送", 409)
            if run.purpose == "context_compaction":
                raise DomainError("正在压缩上下文，请将补充内容作为新消息排队", 409)
            key = f"steer:{run_id}:{request.request_id}"
            item = await self.db.get(key)
            if item is None:
                item = {
                    "id": key,
                    "content": request.content,
                    "status": "pending",
                    "run_id": run_id,
                    "tool_names": self.validate_tools(request.tool_names),
                }
                await self.db.put("steering", item, owner=user_id, parent=run_id)
                await self.emit("steering.updated", item, run)
            return item

    async def cancel(self, run_id, user_id, reason="user_stop"):
        # 这里只发起取消；运行中的任务可能还需确认写入结果才会进入终态。
        async with self.control:
            run = await self.get_run(run_id)
            if not run or run.user_id != user_id:
                raise DomainError("任务不存在", 404)
            await self._cancel_locked(run, reason)
            return self.public_run(await self.get_run(run_id))

    async def steer_queued(self, queued_id, user_id):
        # 将排队消息原子地转成当前任务的引导，原排队任务随之取消，避免重复执行。
        async with self.control:
            queued = await self.get_run(queued_id)
            if not queued or queued.user_id != user_id:
                raise DomainError("排队任务不存在", 404)
            await self.session(queued.session_id, user_id)
            if queued.reason == "converted_to_steering":
                return await self.db.get(queued.steering_id)
            if queued.status != "queued":
                raise DomainError("该消息已不在队列中，不能转为引导", 409)
            target = next(
                (
                    run
                    for run in self.active.values()
                    if run.session_id == queued.session_id
                    and run.status == "running"
                    and not run.reason
                    and run.purpose != "context_compaction"
                ),
                None,
            )
            if not target:
                raise DomainError("当前没有可引导的运行任务，原消息仍保留在队列中", 409)
            item = {
                "id": f"steer:queued:{queued_id}",
                "content": queued.content,
                "status": "pending",
                "run_id": target.id,
                "source_run_id": queued_id,
                "tool_names": queued.tool_names,
            }
            queued.status = "cancelled"
            queued.reason = "converted_to_steering"
            queued.ended_at = time.time()
            queued.steering_id = item["id"]
            queued.steering_run_id = target.id
            async with self.db.transaction() as connection:
                await self.db.put("steering", item, owner=user_id, parent=target.id, connection=connection)
                await self.db.put("run", queued.to_record(), connection=connection)
            await self.emit("run.updated", self.public_run(queued), queued)
            await self.emit("steering.updated", item, target)
            return item

    async def _cancel_locked(self, run: Run, reason):
        # 调用方必须持有 control 锁；排队任务可直接取消，执行任务先标记 cancelling。
        if run.status in TERMINAL:
            return
        current = self.active.get(run.id, run)
        current.reason = reason
        current.status = "cancelled" if run.status == "queued" else "cancelling"
        await self.db.put("run", self.public_run(current))
        await self.emit("run.updated", self.public_run(current), current)
        task = self.executions.get(run.id)
        if task and not task.done():
            task.cancel()

    async def disconnect(self, client_id):
        # 断开连接只取消由该客户端提交的任务，不影响同用户其他窗口的任务。
        async with self.control:
            client = self.clients.get(client_id)
            if not client or client.closed:
                return
            client.closed = True
            client.connected = False
            runs = [
                r
                for r in await self.list_runs(owner=client.user_id)
                if r.client_id == client_id and r.status not in TERMINAL
            ]
            # 先取消排队项，避免运行任务退出后调度通道立即启动下一项。
            # 作用：排序键将排队任务放在前面，防止运行任务结束后启动尚未取消的队列项。
            for run in sorted(runs, key=lambda r: r.status != "queued"):
                await self._cancel_locked(run, "client_disconnect")
            if not client.queue.full():
                client.queue.put_nowait(None)

    async def _lane(self, session_id):
        # 按入库顺序逐个取任务；等待当前执行及其收尾完成后才取下一个。
        while not self.shutting_down:
            async with self.control:
                queued = [r for r in await self.list_runs(parent=session_id) if r.status == "queued"]
                if not queued:
                    self.lanes.pop(session_id, None)
                    return
                run = queued[0]
                client = self.clients.get(run.client_id)
                if not client or client.closed or not client.connected:
                    await self._cancel_locked(run, "client_disconnect")
                    continue
                run.status = "running"
                run.started_at = time.time()
                self.active[run.id] = run
                await self.db.put("run", run.to_record())
                # 创建执行任务
                task = asyncio.create_task(self._execute(run))
                self.executions[run.id] = task
            try:
                # 等待执行任务完成
                await task
            except asyncio.CancelledError:
                # Task 可能尚未进入 _execute 就被取消，因此此处也要补写终态。
                if run.status not in TERMINAL:
                    run.status = "cancelled"
                    run.ended_at = time.time()
                    await self.db.put("run", self.public_run(run))
                    await self.emit("run.updated", self.public_run(run), run)
            finally:
                self.executions.pop(run.id, None)
                self.active.pop(run.id, None)

    async def append(self, run: Run, message, input_kind=None, reasoning="", tool_names=None):
        # 保存完整协议消息后发出事件；input_kind 区分原请求、引导和中断说明。
        message = deepcopy(message)
        names = list(dict.fromkeys(tool_names or []))
        user_metadata = {}
        if message["role"] == "user" and input_kind in {"request", "steering"}:
            # 作者：LHF；时间：2026-10-22；作用：正式应用消息时固定模型正文，原文单独保留供界面展示。
            original_content = message.get("content") or ""
            user_metadata["original_content"] = original_content
            if names:
                bundle = self.context.prompts.load()
                preference = bundle.render("tool_preference", tools="、".join(names))
                message["content"] = original_content + "\n\n" + preference
                # 保存实际使用的偏好模板版本；后续模板变化不改写这条历史消息。
                user_metadata["tool_preference_version"] = bundle.versions["tool_preference"]
        row = {
            "id": uid(),
            "run_id": run.id,
            "session_id": run.session_id,
            "message": message,
            "input_kind": input_kind,
            "timestamp": time.time(),
            # 思考作为展示元数据持久化，不混入回答正文或冒充新的用户指令。
            "reasoning": reasoning,
            # 元数据保留所选工具，模型正文中的偏好已在上面一次性渲染。
            "tool_names": names,
            **user_metadata,
        }
        await self.context.state.append(run.session_id, row, run.user_id)
        await self.emit("message.created", row, run)
        return row

    async def _apply_steering(self, run: Run):
        # 只消费 pending 引导，标记 applied 后下一轮不会重复加入历史。
        async with self.control:
            pending = [s for s in await self.db.list("steering", parent=run.id) if s["status"] == "pending"]
            for item in pending:
                await self.append(
                    run,
                    {"role": "user", "content": item["content"]},
                    "steering",
                    tool_names=item.get("tool_names", []),
                )
                item["status"] = "applied"
                await self.db.put("steering", item)
                await self.emit("steering.updated", item, run)
            return bool(pending)

    async def _invoke(self, run: Run, settings, profile, messages, tools, max_tokens, streaming):
        # 对话、摘要和重试统一走此入口，共享模型调用次数及任务总时长预算。
        messages = deepcopy(messages)
        tools = deepcopy(tools)
        for attempt in range(settings.retries + 1):
            if run.reason:
                raise asyncio.CancelledError
            if run.model_calls >= settings.max_model_calls:
                raise BudgetExceeded("已达到模型调用上限")
            run.model_calls += 1
            call_id = uid()
            run.partial = ""
            run.partial_reasoning = ""
            await self.db.put("run", self.public_run(run))
            started_event = await self.emit(
                "model.started",
                {
                    "call_id": call_id,
                    "purpose": "answer" if streaming else "summary",
                    "model": profile["model"],
                    "attempt": attempt + 1,
                },
                run,
            )

            async def on_text(text):
                # 临时文本同时保存在内存和事件流中，中断时可据此保留已输出部分。
                if run.reason:
                    raise asyncio.CancelledError
                run.partial += text
                await self.emit("model.delta", {"call_id": call_id, "text": text}, run)

            async def on_reasoning(text):
                # 作用：累积已返回的思考片段并广播独立事件，支持中断后保留。
                if run.reason:
                    raise asyncio.CancelledError
                run.partial_reasoning += text
                await self.emit("model.reasoning.delta", {"call_id": call_id, "text": text}, run)

            call_record = None

            # 捕获请求快照
            async def record_request(body):
                # 作用：实际传输前持久化独立、脱敏的调用快照。
                nonlocal call_record
                call_record = self.diagnostics.safe(
                    {
                        "id": f"model-call:{call_id}",
                        "call_id": call_id,
                        "sequence": started_event["id"],
                        "timestamp": started_event["timestamp"],
                        "session_id": run.session_id,
                        "run_id": run.id,
                        "user_id": run.user_id,
                        "purpose": "answer" if streaming else "summary",
                        "attempt": attempt + 1,
                        "model": profile["model"],
                        "status": "sending",
                        "request": body,
                        "prompt_versions": getattr(messages, "prompt_versions", {}),
                        "context_version": getattr(messages, "context_version", None),
                    }
                )
                await self.db.put("model_call", call_record, owner=run.user_id, parent=run.session_id)
                if not await self.diagnostics.call(call_record):
                    await self.report_logging_status()
                    raise ContextFailure("调用输入快照无法写入本地文件，未发送模型请求")
                await self.emit("model.context", {"call_id": call_id, "purpose": call_record["purpose"]}, run)

            capture_token = request_recorder.set(record_request)
            retry_delay = None
            try:
                async with asyncio.timeout(settings.model_timeout):
                    # 捕获请求快照
                    if not isinstance(self.model, (OpenAIModel, ScriptedModel)):
                        await capture_request(request_body(profile, messages, tools, max_tokens, streaming))
                    # 调用模型生成回复
                    reply = await self.model.complete(
                        profile,
                        messages,
                        tools,
                        max_tokens,
                        settings.model_timeout,
                        on_text if streaming else None,
                        on_reasoning=on_reasoning if streaming else None,
                    )
                if call_record is not None:
                    call_record.update(
                        status="completed", response=reply.model_dump(mode="json"), ended_at=time.time()
                    )
                await self.emit(
                    "model.finished",
                    {"call_id": call_id, "finish_reason": reply.finish_reason, "usage": reply.usage},
                    run,
                )
                if not streaming:
                    run.partial = ""
                    run.partial_reasoning = ""
                return reply
            except asyncio.CancelledError:
                if call_record is not None:
                    call_record.update(status="cancelled", ended_at=time.time())
                raise
            except ContextFailure as error:
                if call_record is not None:
                    call_record.update(status="failed", error=str(error), ended_at=time.time())
                raise
            except (ModelFailure, TimeoutError) as error:
                if call_record is not None:
                    call_record.update(status="failed", error=str(error), ended_at=time.time())
                partial = bool(run.partial or run.partial_reasoning)
                failure = error if isinstance(error, ModelFailure) else ModelFailure("模型请求超时", True)
                await self.emit(
                    "model.failed",
                    {
                        "call_id": call_id,
                        "error": str(failure),
                        "retryable": failure.retryable,
                        "partial": partial,
                    },
                    run,
                )
                if partial or not failure.retryable or attempt >= settings.retries:
                    # 已向用户输出部分内容后不重试，避免重复生成或混合两次回答。
                    raise failure
                if run.model_calls >= settings.max_model_calls:
                    raise BudgetExceeded("模型调用预算不足，未继续重试") from None
                delay = max(settings.retry_seconds, failure.retry_after)
                remaining = run.started_at + settings.max_seconds - time.time()
                if delay >= remaining:
                    raise BudgetExceeded("剩余总时长不足以等待重试") from None
                await self.emit(
                    "model.retry",
                    {
                        "retry": attempt + 1,
                        "max_retries": settings.retries,
                        "delay_seconds": delay,
                        "reason": str(failure),
                    },
                    run,
                )
                retry_delay = delay
            finally:
                request_recorder.reset(capture_token)
                if call_record is not None:
                    if call_record["status"] == "sending":
                        call_record.update(
                            status="cancelled" if run.reason else "failed", ended_at=time.time()
                        )
                    if call_record["status"] != "completed":
                        call_record["partial_response"] = {
                            "text": run.partial,
                            "reasoning": run.partial_reasoning,
                        }
                    call_record = self.diagnostics.safe(call_record)
                    await self.db.put("model_call", call_record, owner=run.user_id, parent=run.session_id)
                    await self.diagnostics.call(call_record)
                    await self.report_logging_status()
            # 先发布本次失败终态再等待重试，查看调用时不会一直显示“准备发送”。
            if retry_delay is not None:
                await self.sleep(retry_delay)

    async def _compact_manually(self, run: Run, settings, profile, summary_profile):
        # 手动压缩沿用任务预算和取消机制，但不追加新的用户聊天消息。
        outcome = "skipped"

        async def summarize(p, messages, max_tokens):
            # 作用：通过统一模型入口生成历史摘要，计入当前任务预算。
            return await self._invoke(run, settings, p, messages, None, max_tokens, False)

        async def emit(kind, data):
            # 作用：转发手动压缩事件，并记录压缩结果或将失败转成异常。
            nonlocal outcome
            await self.emit(kind, data, run)
            if kind == "context.compaction_failed":
                raise ContextFailure(f"{data.get('reason') or '手动压缩失败'}，已保留原摘要与完整历史")
            if kind == "context.compacted":
                outcome = "compacted"
            if kind == "context.compaction_skipped":
                run.compaction_message = data["reason"]

        async with asyncio.timeout(settings.max_seconds):
            await self.context.build(
                run.session_id,
                run.id,
                settings,
                profile,
                summary_profile,
                self.registry.schemas(),
                None,
                summarize,
                emit,
                force=True,
            )
        run.status = "completed"
        run.compaction_result = outcome

    async def _execute(self, run: Run):
        # 主循环：应用引导 → 构建上下文 → 调用模型 → 执行工具 → 再次调用模型。
        try:
            settings = await self.settings()
            run.settings = settings
            # 启动时固定配置快照，运行期间修改全局设置不会改变本任务的执行参数。
            profile, summary_profile = await self.configured_models(settings)
            run.profile = dict(profile)
            run.summary_profile = dict(summary_profile)
            # 保存模型快照
            run.model_snapshot = ModelSnapshot(
                id=profile["id"],
                model=profile["model"],
                context_capacity=profile["context_capacity"],
                capacity_source=profile["capacity_source"],
            )
            # 判断是否是手动压缩任务
            if run.purpose != "context_compaction":
                # 添加用户消息
                await self.append(
                    run, {"role": "user", "content": run.content}, "request", tool_names=run.tool_names
                )
            # 更新任务状态
            await self.emit("run.updated", self.public_run(run), run)
            # 如果是手动压缩任务，直接进入压缩流程
            if run.purpose == "context_compaction":
                await self._compact_manually(run, settings, profile, summary_profile)
                return

            # 回调在当前 Run 内复用，无需在每轮循环中重新定义。
            async def summarize(p, messages, max_tokens):
                # 作用：通过统一模型入口生成历史摘要，计入当前任务预算。
                return await self._invoke(run, settings, p, messages, None, max_tokens, False)

            async def context_event(kind, data):
                # 作用：为上下文事件补充当前任务归属后持久化并广播。
                await self.emit(kind, data, run)

            # 总时限覆盖整个多轮循环；工具执行完后仍可能继续请求模型。
            async with asyncio.timeout(settings.max_seconds):
                while True:
                    # 应用引导
                    await self._apply_steering(run)

                    # 每轮按最新历史重建上下文，必要时压缩，并纳入上一轮工具结果。
                    messages = await self.context.build(
                        run.session_id,
                        run.id,
                        settings,
                        profile,
                        summary_profile,
                        self.registry.schemas(),
                        None,
                        summarize,
                        context_event,
                    )
                    # 压缩期间也可能收到引导；若有新增内容，重新构建并计算用量后再调用模型。
                    if await self._apply_steering(run):
                        continue
                    reply = await self._invoke(
                        run,
                        settings,
                        profile,
                        messages,
                        self.registry.schemas(),
                        None,
                        True,
                    )
                    if run.reason:
                        raise asyncio.CancelledError
                    # 先确认供应商正常结束且响应类型匹配，再保存调用、登记 ID 和执行工具。
                    validate_finish_reason(reply)
                    ids = [call.id for call in reply.calls]
                    # ID 来自供应商响应：检查本批重复，再查询会话缓存集合，不遍历历史消息。
                    # 工具结果按 ID 关联、保存；有重复就拒绝整批，避免结果覆盖或归属歧义。
                    if len(ids) != len(set(ids)) or await self.context.state.has_tool_calls(
                        run.session_id, ids
                    ):
                        raise ModelFailure("模型返回重复工具调用ID，未执行该批工具")
                    message = {"role": "assistant", "content": reply.text or None}
                    if reply.reasoning_content is not None:
                        # 工具追问必须保留供应商原生思考，不使用混合标签后的展示文本替代。
                        message["reasoning_content"] = reply.reasoning_content
                    if reply.calls:
                        message["tool_calls"] = [
                            {
                                "id": c.id,
                                "type": "function",
                                "function": {"name": c.name, "arguments": c.arguments},
                            }
                            for c in reply.calls
                        ]
                    # 先保存模型发起的调用，再执行工具，确保结果有对应的原始调用记录。
                    # append 同时将新调用 ID 加入会话集合；ID 已记录不代表工具执行成功。
                    await self.append(run, message, reasoning=reply.reasoning)
                    run.partial = ""
                    run.partial_reasoning = ""
                    if reply.calls:
                        # 执行并记录工具结果，随后回到循环，让模型结合结果决定下一步。
                        await self._batch(run, settings, reply.calls)
                        continue
                    # 结束原因已统一校验；普通回答还须非空，才能进入完成流程。
                    if not reply.text.strip():
                        raise ModelFailure("模型没有返回可用回答或工具调用")
                    # 与 steer 共用锁：完成前再次检查引导，确保已接受的引导不会被遗漏。
                    async with self.control:
                        pending = [
                            s
                            for s in await self.db.list("steering", parent=run.id)
                            if s["status"] == "pending"
                        ]
                        if pending:
                            continue
                        if run.reason:
                            raise asyncio.CancelledError
                        run.status = "completed"
                        await self.db.put("run", self.public_run(run))
                        break
        except asyncio.CancelledError:
            run.status = "cancelled"
            run.reason = run.reason or "user_stop"
            await self._save_interruption(
                run, "用户手动停止" if run.reason == "user_stop" else "连接断开，执行已停止"
            )
        except (BudgetExceeded, TimeoutError) as error:
            run.status = "limited"
            run.reason = str(error) or "执行总时长已达到上限"
            await self._save_interruption(run, run.reason)
        except (DomainError, ModelFailure, ContextFailure, PromptError, ToolError) as error:
            run.status = "failed"
            run.reason = str(error)
            await self._save_interruption(run, str(error))
        except Exception as error:
            run.status = "failed"
            run.reason = f"内部错误：{type(error).__name__}"
            await self.diagnostics.write(
                "app",
                {
                    "type": "run.error",
                    "run_id": run.id,
                    "session_id": run.session_id,
                    "timestamp": time.time(),
                    "error": type(error).__name__,
                    "frames": [
                        {"file": frame.filename, "line": frame.lineno, "function": frame.name}
                        for frame in traceback.extract_tb(error.__traceback__)
                    ],
                },
            )
            await self._save_interruption(run, run.reason)
        finally:
            await self.repair_calls(run)
            # 无论成功、取消或异常，都明确标记未消费引导，并持久化最终任务状态。
            for item in await self.db.list("steering", parent=run.id):
                if item["status"] == "pending":
                    item["status"] = "unprocessed"
                    await self.db.put("steering", item)
                    await self.emit("steering.updated", item, run)
            run.ended_at = time.time()
            await self.db.put("run", self.public_run(run))
            await self.emit("run.updated", self.public_run(run), run)

    async def _save_interruption(self, run: Run, reason):
        # 先补齐工具结果，再保存部分回答及中断原因，保持历史协议完整。
        await self.repair_calls(run)
        text = run.partial
        run.partial = ""
        reasoning = run.partial_reasoning
        run.partial_reasoning = ""
        await self.append(
            run,
            {
                "role": "assistant",
                "content": (text + "\n\n" if text else "") + f"[执行状态：{reason}。已确认的工具结果保留。]",
            },
            "interruption",
            reasoning=reasoning,
        )

    async def _batch(self, run: Run, settings, calls):
        # 结束状态由入口校验；这里整批检查工具预算，拒绝执行时仍为每个调用写入失败结果。
        outcomes = {}
        budget_error = len(calls) > settings.max_tool_calls - run.tool_calls
        if budget_error:
            for call in calls:
                outcomes[call.id] = {
                    "ok": False,
                    "error": {
                        "code": "budget_exceeded",
                        "message": "未执行：工具预算不足",
                    },
                }
        else:
            run.tool_calls += len(calls)
            await self.db.put("run", self.public_run(run))
        # 定义单个工具的执行函数，处理超时、取消并发出执行结果
        semaphore = asyncio.Semaphore(settings.tool_concurrency)

        async def one(call):
            # 作用：在并发限制内执行单个工具，处理超时、取消并发出执行结果。
            async with semaphore:
                if run.reason:
                    return
                await self.emit(
                    "tool.started", {"call_id": call.id, "name": call.name, "arguments": call.arguments}, run
                )
                started = time.monotonic()
                task = asyncio.create_task(
                    self.registry.execute(call, self.db, run.user_id, f"op:{run.id}:{call.id}")
                )
                try:
                    result = await asyncio.wait_for(asyncio.shield(task), settings.tool_timeout)
                    outcomes[call.id] = {"ok": True, "result": result}
                except (asyncio.CancelledError, TimeoutError) as error:
                    # SQLite 写入可能已开始提交；待办工具须等待结果确定后才能推进会话队列。
                    if call.name == "todo":
                        try:
                            result = await asyncio.shield(task)
                            outcomes[call.id] = {"ok": True, "result": result, "stop_requested": True}
                        except (Exception, asyncio.CancelledError):
                            outcomes[call.id] = {
                                "ok": False,
                                "error": {"code": "cancelled", "message": "工具执行已停止"},
                            }
                    else:
                        task.cancel()
                        await asyncio.gather(task, return_exceptions=True)
                        outcomes[call.id] = {
                            "ok": False,
                            "error": {
                                "code": "cancelled"
                                if isinstance(error, asyncio.CancelledError)
                                else "timeout",
                                "message": "工具被停止或超时",
                            },
                        }
                    if isinstance(error, asyncio.CancelledError):
                        raise
                except ValidationError as error:
                    outcomes[call.id] = {
                        "ok": False,
                        "error": {"code": "validation_error", "message": str(error)[:2000]},
                    }
                except ToolError as error:
                    outcomes[call.id] = {"ok": False, "error": {"code": error.code, "message": str(error)}}
                except Exception as error:
                    outcomes[call.id] = {
                        "ok": False,
                        "error": {"code": "tool_failure", "message": type(error).__name__},
                    }
                finally:
                    await self.emit(
                        "tool.finished",
                        {
                            "call_id": call.id,
                            "name": call.name,
                            "elapsed_ms": round((time.monotonic() - started) * 1000),
                            **outcomes.get(call.id, {"ok": False, "cancelled": True}),
                        },
                        run,
                    )

        try:
            if not budget_error:
                if self.registry.is_parallel(calls):
                    # 只有全批工具均声明可并行才并发；包含待办时整批按模型给出的顺序执行。
                    children = [asyncio.create_task(one(call)) for call in calls]
                    try:
                        await asyncio.gather(*children)
                    finally:
                        for child in children:
                            if not child.done():
                                child.cancel()
                        await asyncio.gather(*children, return_exceptions=True)
                else:
                    for call in calls:
                        await one(call)
        finally:
            for call in calls:
                # 按原调用顺序回填结果，取消前未启动的工具也必须有明确的协议响应。
                result = outcomes.get(
                    call.id,
                    {"ok": False, "error": {"code": "cancelled", "message": "未执行：当前任务已停止"}},
                )
                await self.append(
                    run,
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    },
                )
                if call.name == "todo" and result.get("ok"):
                    await self.emit("todo.changed", {}, user_id=run.user_id)
        if budget_error:
            raise BudgetExceeded("工具预算不足，整批未执行")
        return outcomes

    async def repair_calls(self, run: Run):
        # 中断恢复只查询已提交操作，不重跑工具；找不到成功凭据就明确记录未确认成功。
        rows = await self.db.run_messages(run.session_id, run.id)
        for index, row in enumerate(rows):
            completed = set()
            for following in rows[index + 1 :]:
                if following["message"]["role"] != "tool":
                    break
                completed.add(following["message"].get("tool_call_id"))
            for call in row["message"].get("tool_calls", []):
                if call["id"] not in completed:
                    prior = await self.db.get(f"op:{row['run_id']}:{call['id']}")
                    result = (
                        {"ok": True, "result": prior["result"], "recovered": True}
                        if prior
                        else {
                            "ok": False,
                            "error": {
                                "code": "interrupted",
                                "message": "调用已中断，未确认成功，不能自动重放",
                            },
                        }
                    )
                    await self.append(
                        run,
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "content": json.dumps(result, ensure_ascii=False),
                        },
                    )
                    completed.add(call["id"])

    async def close(self):
        # 停止接收新调度，取消客户端任务，等待各会话收尾后再关闭数据库。
        self.shutting_down = True
        for client_id in list(self.clients):
            await self.disconnect(client_id)
        await asyncio.gather(*list(self.lanes.values()), return_exceptions=True)
        await self.diagnostics.write("app", {"type": "shutdown", "timestamp": time.time()})
        await self.diagnostics.close()
        await self.db.close()

# 作者：LHF。
# 注释维护时间：2026-10-23。
# 文件作用：待办参数、工具定义与共享待办事务。

import time
from typing import Literal

from pydantic import Field, model_validator

from app.schemas import StrictModel
from app.storage import Database, uid
from app.tool.base import BaseTool, ToolError


class TodoArgs(StrictModel):
    # 同一参数结构同时用于模型工具和手动接口；写操作需要调用方持有最新版本。
    action: Literal["add", "list", "update", "complete", "delete"]
    todo_id: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=4000)
    expected_version: int | None = Field(default=None, ge=1)
    status: Literal["pending", "completed"] | None = None

    @model_validator(mode="after")
    def required_by_action(self):
        # 作用：字段是否必填取决于 action，跨字段规则在整体校验时检查。
        if self.action == "add" and not self.title:
            raise ValueError("新增待办必须提供标题")
        if self.action in {"update", "complete", "delete"}:
            if not self.todo_id or self.expected_version is None:
                raise ValueError("修改待办必须提供 todo_id 与 expected_version；请先查询")
        if self.action == "update" and self.title is None and self.notes is None and self.status is None:
            raise ValueError("修改内容不能为空")
        return self


class TodoTool(BaseTool[TodoArgs]):
    name = "todo"
    description = "当前用户共享待办：add/list/update/complete/delete。修改前先list取得ID和版本。"
    arguments = TodoArgs
    execution_mode = "sequential"

    async def execute(self, args: TodoArgs, db: Database, user_id: str, operation_id: str):
        # 作用：在事务中执行用户共享待办，保留幂等、归属和版本检查。
        return await _todo(db, user_id, args, operation_id)


async def _todo(db, user_id, args: TodoArgs, operation_id):
    # 作用：手动修改和 Agent 调用共用此入口，待办按用户共享，操作凭据与变更一起提交。
    async with db.transaction() as connection:
        prior = await db.get(operation_id, connection)
        # 相同操作 ID 只返回首次已提交结果，防止重试或恢复时重复写入。
        if prior:
            if prior["owner"] != user_id:
                raise ToolError("not_found", "操作不存在")
            return prior["result"]
        if args.action == "list":
            items = await db.list("todo", owner=user_id, connection=connection)
            return {"items": [item for item in items if not item.get("deleted")]}
        if args.action == "add":
            item = {
                "id": uid(),
                "kind": "todo",
                "user_id": user_id,
                "title": args.title,
                "notes": args.notes or "",
                "status": "pending",
                "version": 1,
                "created_at": time.time(),
                "updated_at": time.time(),
                "deleted": False,
            }
        else:
            item = await db.get(args.todo_id, connection)
            if (
                not item
                or item.get("kind") != "todo"
                or item.get("user_id") != user_id
                or item.get("deleted")
            ):
                raise ToolError("not_found", "待办不存在或不属于当前用户")
            if item["version"] != args.expected_version:
                # 乐观并发检查：旧窗口和模型持有的版本可能过期，必须重新查询后再修改。
                raise ToolError("version_conflict", "待办已被其他窗口修改，请重新查询后再操作")
            item.update(version=item["version"] + 1, updated_at=time.time())
            if args.action == "update":
                for field in ("title", "notes", "status"):
                    if getattr(args, field) is not None:
                        item[field] = getattr(args, field)
            elif args.action == "complete":
                item["status"] = "completed"
            elif args.action == "delete":
                item["deleted"] = True
        result = {"action": args.action, "item": item}
        await db.put("todo", item, owner=user_id, connection=connection)
        # 保存成功凭据，Runtime 中断恢复时可确认此调用确实已完成，而无需重放。
        await db.put(
            "operation",
            {"id": operation_id, "owner": user_id, "result": result},
            owner=user_id,
            connection=connection,
        )
        return result

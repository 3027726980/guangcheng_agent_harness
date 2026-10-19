"""Registered tools and explicit execution policies. No arbitrary eval or framework."""

import ast
import inspect
import operator
import time
from dataclasses import dataclass
from decimal import Decimal, DecimalException, localcontext
from typing import Callable

from pydantic import BaseModel

from app.schemas import CalculatorArgs, SearchArgs, TodoArgs
from app.storage import Database, uid


class ToolError(Exception):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    arguments: type[BaseModel]
    execution_mode: str
    handler: Callable | None = None

    def schema(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.arguments.model_json_schema(),
            },
        }


class ToolRegistry:
    def __init__(self):
        self.tools: dict[str, Tool] = {}
        self.register(
            Tool(
                "calculator",
                "计算受限数学表达式，支持括号、小数、+ - * / %。",
                CalculatorArgs,
                "parallel",
                lambda args, db, owner, operation: calculate(args.expression),
            )
        )
        self.register(
            Tool(
                "search",
                "搜索固定样例资料（MOCK，非联网）。没有匹配返回空结果。",
                SearchArgs,
                "parallel",
                lambda args, db, owner, operation: search(args.query, args.limit),
            )
        )
        self.register(
            Tool(
                "todo",
                "当前用户共享待办：add/list/update/complete/delete。修改前先list取得ID和版本。",
                TodoArgs,
                "sequential",
                lambda args, db, owner, operation: todo(db, owner, args, operation),
            )
        )

    def register(self, tool):
        if tool.name in self.tools:
            raise ValueError(f"工具重复注册：{tool.name}")
        if not callable(tool.handler):
            raise ValueError("工具必须提供执行函数")
        self.tools[tool.name] = tool

    def schemas(self):
        return [tool.schema() for tool in self.tools.values()]

    def is_parallel(self, calls):
        return all(c.name in self.tools and self.tools[c.name].execution_mode == "parallel" for c in calls)

    async def execute(self, call, db: Database, user_id: str, operation_id: str):
        tool = self.tools.get(call.name)
        if not tool:
            raise ToolError("unknown_tool", f"未知工具：{call.name}")
        arguments = tool.arguments.model_validate_json(call.arguments)
        result = tool.handler(arguments, db, user_id, operation_id)
        return await result if inspect.isawaitable(result) else result


def calculate(expression: str):
    operations = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
    }
    try:
        tree = ast.parse(expression, mode="eval")
        if len(list(ast.walk(tree))) > 80:
            raise ToolError("expression_too_large", "表达式过于复杂")

        def evaluate(node):
            if isinstance(node, ast.Expression):
                return evaluate(node.body)
            if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                value = Decimal(ast.get_source_segment(expression, node))
            elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                value = evaluate(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
            elif isinstance(node, ast.BinOp) and type(node.op) in operations:
                value = operations[type(node.op)](evaluate(node.left), evaluate(node.right))
            else:
                raise ToolError("invalid_expression", "只支持数字、括号和 + - * / %")
            if not value.is_finite() or abs(value) > Decimal("1e100"):
                raise ToolError("numeric_limit", "计算结果超出允许范围")
            return value

        with localcontext() as context:
            context.prec = 28
            result = evaluate(tree)
        return {"expression": expression, "result": format(result.normalize(), "f"), "precision": 28}
    except (SyntaxError, DecimalException, ValueError, RecursionError) as error:
        raise ToolError("invalid_expression", "表达式非法、除零或超出计算范围") from error


DOCUMENTS = [
    {
        "id": "sample:python",
        "title": "Python 入门学习样例",
        "keywords": ["python", "编程", "学习", "免费"],
        "snippet": "模拟资料：先学习变量、函数、列表，再通过小项目练习；每天安排30分钟，资料免费。",
    },
    {
        "id": "sample:agent",
        "title": "Agent 工具循环样例",
        "keywords": ["agent", "工具", "runtime", "智能体"],
        "snippet": "模拟资料：模型生成工具请求，程序校验并执行，将结果交回模型；设置循环预算。",
    },
    {
        "id": "sample:context",
        "title": "Context 管理样例",
        "keywords": ["context", "上下文", "记忆", "压缩"],
        "snippet": "模拟资料：保存完整历史，在容量接近阈值时总结旧内容，保留目标和近期完整工具交互。",
    },
    {
        "id": "sample:plan",
        "title": "学习与周报计划样例",
        "keywords": ["计划", "周报", "学习", "待办"],
        "snippet": "模拟资料：列出本周目标、实际完成事项、阻塞和下一步；待办状态以工具查询结果为准。",
    },
]


def search(query, limit):
    query = query.lower()
    scored = [(sum(word in query for word in doc["keywords"]), doc) for doc in DOCUMENTS]
    scored.sort(key=lambda item: item[0], reverse=True)
    return {
        "mock": True,
        "notice": "固定样例资料，非真实联网搜索",
        "query": query,
        "results": [
            {"source": doc["id"], "title": doc["title"], "snippet": doc["snippet"]}
            for score, doc in scored
            if score
        ][:limit],
    }


async def todo(db, user_id, args: TodoArgs, operation_id):
    async with db.transaction() as connection:
        prior = await db.get(operation_id, connection)
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
        await db.put(
            "operation",
            {"id": operation_id, "owner": user_id, "result": result},
            owner=user_id,
            connection=connection,
        )
        return result

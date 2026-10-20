# 作者：LHF。
# 注释维护时间：2026-10-20。
# 文件作用：工具注册、参数校验、计算器、模拟搜索与共享待办。
"""Registered tools and explicit execution policies. No arbitrary eval or framework."""

import ast
import inspect
import operator
import time
from abc import ABC, abstractmethod
from decimal import Decimal, DecimalException, localcontext
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel

from app.schemas import CalculatorArgs, SearchArgs, TodoArgs
from app.storage import Database, uid


class ToolError(Exception):
    def __init__(self, code, message):
        # 作用：保存稳定错误码和用户可读提示，供工具结果及接口复用。
        self.code = code
        super().__init__(message)


Args = TypeVar("Args", bound=BaseModel)


class BaseTool(ABC, Generic[Args]):
    """工具统一契约：子类声明元数据与参数模型，实现异步执行方法。"""

    name: str
    description: str
    arguments: type[Args]
    execution_mode: Literal["parallel", "sequential"]

    def schema(self):
        # 作用：从统一参数模型生成函数声明，与注册表执行前的校验保持一致。
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.arguments.model_json_schema(),
            },
        }

    @abstractmethod
    async def execute(self, args: Args, db: Database, user_id: str, operation_id: str):
        # 作用：由具体工具执行已校验参数，使用可信用户身份及幂等操作 ID。
        raise NotImplementedError


class CalculatorTool(BaseTool[CalculatorArgs]):
    name = "calculator"
    description = "计算受限数学表达式，支持括号、小数、+ - * / %。"
    arguments = CalculatorArgs
    execution_mode = "parallel"

    async def execute(self, args: CalculatorArgs, db: Database, user_id: str, operation_id: str):
        # 作用：使用 AST 白名单和 Decimal 计算已校验的数学表达式。
        return _calculate(args.expression)


class SearchTool(BaseTool[SearchArgs]):
    name = "search"
    description = "搜索固定样例资料（MOCK，非联网）。没有匹配返回空结果。"
    arguments = SearchArgs
    execution_mode = "parallel"

    async def execute(self, args: SearchArgs, db: Database, user_id: str, operation_id: str):
        # 作用：检索固定样例并保留模拟标记，不调用真实网络。
        return _search(args.query, args.limit)


class TodoTool(BaseTool[TodoArgs]):
    name = "todo"
    description = "当前用户共享待办：add/list/update/complete/delete。修改前先list取得ID和版本。"
    arguments = TodoArgs
    execution_mode = "sequential"

    async def execute(self, args: TodoArgs, db: Database, user_id: str, operation_id: str):
        # 作用：在事务中执行用户共享待办，保留幂等、归属和版本检查。
        return await _todo(db, user_id, args, operation_id)


class ToolRegistry:
    # 所有调用方共用注册表；业务实现只通过 BaseTool.execute 分发。
    def __init__(self):
        # 作用：实例化并注册内置工具，使目录、Schema 和执行使用相同对象。
        self.tools: dict[str, BaseTool] = {}
        for tool in (CalculatorTool(), SearchTool(), TodoTool()):
            self.register(tool)

    def register(self, tool: BaseTool):
        # 作用：校验基类契约、元数据及执行策略，拒绝无效工具和重名注册。
        if not isinstance(tool, BaseTool):
            raise TypeError("工具必须继承 BaseTool")
        if not isinstance(getattr(tool, "name", None), str) or not tool.name.strip():
            raise ValueError("工具必须声明非空名称")
        if tool.name in self.tools:
            raise ValueError(f"工具重复注册：{tool.name}")
        if not isinstance(getattr(tool, "description", None), str) or not tool.description.strip():
            raise ValueError("工具必须声明非空描述")
        arguments = getattr(tool, "arguments", None)
        if not isinstance(arguments, type) or not issubclass(arguments, BaseModel):
            raise ValueError("工具必须声明 Pydantic 参数模型")
        if getattr(tool, "execution_mode", None) not in {"parallel", "sequential"}:
            raise ValueError("工具执行策略必须是 parallel 或 sequential")
        if not inspect.iscoroutinefunction(tool.execute):
            raise TypeError("工具必须实现异步 execute 方法")
        self.tools[tool.name] = tool

    def schemas(self):
        # 作用：返回全部已注册工具的函数声明，交给模型自动选择。
        return [tool.schema() for tool in self.tools.values()]

    def is_parallel(self, calls):
        # 作用：仅当整批工具均已注册且允许并行时，准许 Runtime 并发执行。
        return all(c.name in self.tools and self.tools[c.name].execution_mode == "parallel" for c in calls)

    async def execute(self, call, db: Database, user_id: str, operation_id: str):
        # 作用：按名称查找工具，严格校验 JSON 参数后统一调用工具实例。
        tool = self.tools.get(call.name)
        if not tool:
            raise ToolError("unknown_tool", f"未知工具：{call.name}")
        arguments = tool.arguments.model_validate_json(call.arguments)
        return await tool.execute(arguments, db, user_id, operation_id)


def _calculate(expression: str):
    # 仅遍历允许的 AST 节点，不使用 eval；函数调用、属性访问等都会被拒绝。
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
            # 作用：递归计算允许的 AST 节点，并拒绝代码执行及超范围数值。
            if isinstance(node, ast.Expression):
                return evaluate(node.body)
            if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                # 从原表达式读取数字构造 Decimal，避免先转浮点引入精度误差。
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


# 搜索数据为固定样例，不调用网络；结果必须保留模拟标记，不能冒充真实检索。
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


def _search(query, limit):
    # 以命中关键词数量排序，无命中则返回空结果，不补造资料。
    query = query.lower()
    scored = [(sum(word in query for word in doc["keywords"]), doc) for doc in DOCUMENTS]
    # 作用：按关键词命中分数排序，只改变结果顺序，不生成新的资料。
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


async def _todo(db, user_id, args: TodoArgs, operation_id):
    # 手动修改和 Agent 调用共用此入口，待办按用户共享，操作凭据与变更一起提交。
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

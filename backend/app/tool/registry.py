# 作者：LHF。
# 注释维护时间：2026-10-23。
# 文件作用：内置工具注册、契约检查、Schema 生成与执行分发。

import inspect

from pydantic import BaseModel

from app.storage import Database
from app.tool.base import BaseTool, ToolError
from app.tool.calculator import CalculatorTool
from app.tool.search import SearchTool
from app.tool.todo import TodoTool


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

    def user_tools(self) -> dict[str, BaseTool]:
        # 作者：LHF；时间：2026-10-21；作用：统一提供用户菜单与请求校验允许使用的工具。
        return {name: tool for name, tool in self.tools.items() if tool.user_selectable}

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

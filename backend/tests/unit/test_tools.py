# 作者：LHF；时间：2026-10-23；作用：验证三个工具的纯逻辑与注册参数契约。

import asyncio

import pytest
from pydantic import ValidationError

from app.schemas import ToolCall
from app.tool.base import BaseTool, ToolError
from app.tool.calculator import CalculatorArgs, CalculatorTool
from app.tool.registry import ToolRegistry
from app.tool.search import SearchTool
from app.tool.todo import TodoTool
from tests.support.tools import invoke_tool


@pytest.mark.parametrize(
    "expression,result", [("128 * 36", "4608"), ("0.1+0.2", "0.3"), ("-(3+2)/2", "-2.5"), ("10 % 3", "1")]
)
async def test_calculator(expression, result):
    # 作用：验证计算器对允许表达式返回预期的精确结果。
    assert (await invoke_tool("calculator", {"expression": expression}))["result"] == result


@pytest.mark.parametrize("expression", ["1/0", "__import__('os')", "2 ** 999999", "True", "[1,2]", "(1"])
async def test_calculator_rejects_code_and_bad_expressions(expression):
    # 作用：验证计算器拒绝代码调用、非法表达式和超范围计算。
    with pytest.raises(ToolError):
        await invoke_tool("calculator", {"expression": expression})


async def test_search_mock_and_empty():
    # 作用：验证模拟搜索标明资料来源，未匹配时返回空结果。
    assert (await invoke_tool("search", {"query": "Python 学习", "limit": 1}))["results"][0][
        "source"
    ] == "sample:python"
    assert (await invoke_tool("search", {"query": "不存在的zzzz", "limit": 3}))["results"] == []
    assert (await invoke_tool("search", {"query": "context", "limit": 3}))["mock"] is True


async def test_registered_subclass_executes_without_registry_branch_changes():
    # 作用：验证新增工具只需实现 BaseTool 并注册，无须添加按名称分支。
    class EchoTool(BaseTool[CalculatorArgs]):
        name = "echo"
        description = "回显"
        arguments = CalculatorArgs
        execution_mode = "parallel"

        async def execute(self, args, db, user_id, operation_id):
            # 作用：检查注册表传递已校验参数与可信执行上下文。
            assert isinstance(args, CalculatorArgs)
            assert (db, user_id, operation_id) == (None, "A", "operation")
            await asyncio.sleep(0)
            return {"text": args.expression}

    registry = ToolRegistry()
    registry.register(EchoTool())
    result = await registry.execute(
        ToolCall(id="echo1", name="echo", arguments='{"expression":"hello"}'), None, "A", "operation"
    )
    assert result == {"text": "hello"}
    assert registry.schemas()[-1]["function"]["name"] == "echo"


def test_base_tool_contract_and_registration_guards():
    # 作者：LHF；时间：2026-10-20；作用：验证抽象契约、非法注册及内置工具继承关系。
    with pytest.raises(TypeError):
        BaseTool()

    class MissingExecute(BaseTool):
        pass

    with pytest.raises(TypeError):
        MissingExecute()
    registry = ToolRegistry()
    assert {type(tool) for tool in registry.tools.values()} == {CalculatorTool, SearchTool, TodoTool}
    with pytest.raises(TypeError, match="BaseTool"):
        registry.register(object())
    with pytest.raises(ValueError, match="重复注册"):
        registry.register(CalculatorTool())


async def test_registry_rejects_unknown_tool_and_invalid_arguments():
    # 作者：LHF；时间：2026-10-20；作用：验证参数在执行前被严格校验，未知工具使用稳定错误码。
    with pytest.raises(ToolError) as caught:
        await invoke_tool("unknown", {})
    assert caught.value.code == "unknown_tool"
    with pytest.raises(ValidationError):
        await invoke_tool("calculator", {"expression": "1+1", "user_id": "B"})
    with pytest.raises(ValidationError):
        await invoke_tool("todo", {"action": "add"})

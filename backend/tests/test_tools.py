# 作者：LHF。
# 时间：2026-10-20。
# 作用：验证 test_tools 所覆盖的行为与边界，使用离线数据及临时资源。
import asyncio
import json

import pytest
from pydantic import ValidationError

from app.schemas import CalculatorArgs, TodoArgs, ToolCall
from app.storage import Database
from app.tools import BaseTool, CalculatorTool, SearchTool, TodoTool, ToolError, ToolRegistry


async def invoke_tool(name, arguments, db=None, user_id="A", operation_id="test:operation"):
    # 作者：LHF；时间：2026-10-20；作用：所有工具业务测试都通过注册表校验并执行。
    call = ToolCall(id="test-call", name=name, arguments=json.dumps(arguments))
    return await ToolRegistry().execute(call, db, user_id, operation_id)


async def invoke_todo(db, user_id, args, operation_id):
    # 作者：LHF；时间：2026-10-20；作用：通过注册表测试待办事务，不绕过统一执行入口。
    return await invoke_tool("todo", args.model_dump(), db, user_id, operation_id)


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


def test_pydantic_schema_and_validation():
    # 作用：验证工具参数 schema 与严格数据校验规则一致。
    assert CalculatorArgs.model_json_schema()["additionalProperties"] is False
    with pytest.raises(ValidationError):
        CalculatorArgs.model_validate_json('{"expression":"1+1","user_id":"B"}')
    with pytest.raises(ValidationError):
        TodoArgs.model_validate_json('{"action":"complete","todo_id":"x","expected_version":"1"}')
    with pytest.raises(ValidationError):
        TodoArgs(action="update", todo_id="x", expected_version=1)


async def test_search_mock_and_empty():
    # 作用：验证模拟搜索标明资料来源，未匹配时返回空结果。
    assert (await invoke_tool("search", {"query": "Python 学习", "limit": 1}))["results"][0]["source"] == "sample:python"
    assert (await invoke_tool("search", {"query": "不存在的zzzz", "limit": 3}))["results"] == []
    assert (await invoke_tool("search", {"query": "context", "limit": 3}))["mock"] is True


def test_tool_declarations():
    # 作用：验证工具声明符合协议，并正确区分串行和并行策略。
    registry = ToolRegistry()

    def call(name):
        # 作用：创建指定名称的最小工具调用，供执行策略断言使用。
        return ToolCall(id=name, name=name, arguments="{}")

    assert registry.is_parallel([call("search"), call("calculator")])
    assert not registry.is_parallel([call("search"), call("todo")])
    assert not registry.is_parallel([call("unknown")])
    assert len(registry.schemas()) == 3


async def test_todo_transaction_idempotency_user_isolation_and_version(tmp_path):
    # 作用：验证待办事务、重复操作幂等、用户隔离和版本冲突处理。
    db = Database(str(tmp_path / "test.db"))
    await db.initialize()
    try:
        first = await invoke_todo(db, "A", TodoArgs(action="add", title="学习"), "op:1")
        duplicate = await invoke_todo(db, "A", TodoArgs(action="add", title="学习"), "op:1")
        assert first == duplicate
        assert len((await invoke_todo(db, "A", TodoArgs(action="list"), "read"))["items"]) == 1
        assert (await invoke_todo(db, "B", TodoArgs(action="list"), "read"))["items"] == []
        key = first["item"]["id"]
        attempts = await asyncio.gather(
            invoke_todo(db, "A", TodoArgs(action="update", todo_id=key, expected_version=1, title="窗口1"), "op:2"),
            invoke_todo(db, "A", TodoArgs(action="update", todo_id=key, expected_version=1, title="窗口2"), "op:3"),
            return_exceptions=True,
        )
        assert sum(isinstance(item, ToolError) for item in attempts) == 1
        assert next(item for item in attempts if isinstance(item, ToolError)).code == "version_conflict"
        with pytest.raises(ToolError):
            await invoke_todo(db, "B", TodoArgs(action="complete", todo_id=key, expected_version=2), "op:4")
        await invoke_todo(db, "A", TodoArgs(action="delete", todo_id=key, expected_version=2), "op:5")
        assert (await invoke_todo(db, "A", TodoArgs(action="list"), "read"))["items"] == []
        assert (await db.get(key))["deleted"]
    finally:
        await db.close()


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


@pytest.mark.parametrize("field,value", [("name", ""), ("description", ""),
                                        ("arguments", dict), ("execution_mode", "invalid")])
def test_invalid_tool_metadata_is_rejected(field, value):
    # 作者：LHF；时间：2026-10-20；作用：拒绝不完整或错误的工具元数据，防止生成不可调用声明。
    tool = CalculatorTool()
    tool.name = "custom"
    setattr(tool, field, value)
    with pytest.raises(ValueError):
        ToolRegistry().register(tool)


def test_synchronous_tool_override_is_rejected():
    # 作者：LHF；时间：2026-10-20；作用：拒绝同步覆盖，确保工具使用统一异步执行契约。
    class SyncTool(CalculatorTool):
        name = "sync"

        def execute(self, args, db, user_id, operation_id):
            # 作用：构造非法同步实现，验证注册时立即失败。
            return {}

    with pytest.raises(TypeError, match="异步"):
        ToolRegistry().register(SyncTool())


async def test_registry_rejects_unknown_tool_and_invalid_arguments():
    # 作者：LHF；时间：2026-10-20；作用：验证参数在执行前被严格校验，未知工具使用稳定错误码。
    with pytest.raises(ToolError) as caught:
        await invoke_tool("unknown", {})
    assert caught.value.code == "unknown_tool"
    with pytest.raises(ValidationError):
        await invoke_tool("calculator", {"expression": "1+1", "user_id": "B"})
    with pytest.raises(ValidationError):
        await invoke_tool("todo", {"action": "add"})

import asyncio

import pytest
from pydantic import ValidationError

from app.schemas import CalculatorArgs, TodoArgs, ToolCall
from app.storage import Database
from app.tools import Tool, ToolError, ToolRegistry, calculate, search, todo


@pytest.mark.parametrize(
    "expression,result", [("128 * 36", "4608"), ("0.1+0.2", "0.3"), ("-(3+2)/2", "-2.5"), ("10 % 3", "1")]
)
def test_calculator(expression, result):
    assert calculate(expression)["result"] == result


@pytest.mark.parametrize("expression", ["1/0", "__import__('os')", "2 ** 999999", "True", "[1,2]", "(1"])
def test_calculator_rejects_code_and_bad_expressions(expression):
    with pytest.raises(ToolError):
        calculate(expression)


def test_pydantic_schema_and_validation():
    assert CalculatorArgs.model_json_schema()["additionalProperties"] is False
    with pytest.raises(ValidationError):
        CalculatorArgs.model_validate_json('{"expression":"1+1","user_id":"B"}')
    with pytest.raises(ValidationError):
        TodoArgs.model_validate_json('{"action":"complete","todo_id":"x","expected_version":"1"}')
    with pytest.raises(ValidationError):
        TodoArgs(action="update", todo_id="x", expected_version=1)


def test_search_mock_and_empty():
    assert search("Python 学习", 1)["results"][0]["source"] == "sample:python"
    assert search("不存在的zzzz", 3)["results"] == []
    assert search("context", 3)["mock"] is True


def test_tool_declarations():
    registry = ToolRegistry()

    def call(name):
        return ToolCall(id=name, name=name, arguments="{}")

    assert registry.is_parallel([call("search"), call("calculator")])
    assert not registry.is_parallel([call("search"), call("todo")])
    assert not registry.is_parallel([call("unknown")])
    assert len(registry.schemas()) == 3


async def test_todo_transaction_idempotency_user_isolation_and_version(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    await db.initialize()
    try:
        first = await todo(db, "A", TodoArgs(action="add", title="学习"), "op:1")
        duplicate = await todo(db, "A", TodoArgs(action="add", title="学习"), "op:1")
        assert first == duplicate
        assert len((await todo(db, "A", TodoArgs(action="list"), "read"))["items"]) == 1
        assert (await todo(db, "B", TodoArgs(action="list"), "read"))["items"] == []
        key = first["item"]["id"]
        attempts = await asyncio.gather(
            todo(db, "A", TodoArgs(action="update", todo_id=key, expected_version=1, title="窗口1"), "op:2"),
            todo(db, "A", TodoArgs(action="update", todo_id=key, expected_version=1, title="窗口2"), "op:3"),
            return_exceptions=True,
        )
        assert sum(isinstance(item, ToolError) for item in attempts) == 1
        assert next(item for item in attempts if isinstance(item, ToolError)).code == "version_conflict"
        with pytest.raises(ToolError):
            await todo(db, "B", TodoArgs(action="complete", todo_id=key, expected_version=2), "op:4")
        await todo(db, "A", TodoArgs(action="delete", todo_id=key, expected_version=2), "op:5")
        assert (await todo(db, "A", TodoArgs(action="list"), "read"))["items"] == []
        assert (await db.get(key))["deleted"]
    finally:
        await db.close()


async def test_registered_handler_executes_without_registry_branch_changes():
    registry = ToolRegistry()
    registry.register(
        Tool(
            "echo",
            "回显",
            CalculatorArgs,
            "parallel",
            lambda args, db, owner, operation: {"text": args.expression},
        )
    )
    result = await registry.execute(
        ToolCall(id="echo1", name="echo", arguments='{"expression":"hello"}'), None, "A", "operation"
    )
    assert result == {"text": "hello"}

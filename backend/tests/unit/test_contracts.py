# 作者：LHF；时间：2026-10-23；作用：验证请求、工具参数及基础预算的必要边界。
import pytest
from pydantic import ValidationError

from app.run import Run
from app.runtime import validate_finish_reason
from app.schemas import MessageRequest, ModelReply, RuntimeSettings
from app.token_budget import output_reserve
from app.tool.calculator import CalculatorArgs
from app.tool.registry import ToolRegistry
from app.tool.search import SearchArgs
from app.tool.todo import TodoArgs


@pytest.mark.parametrize(
    "args", [{}, {"expression": ""}, {"expression": 1}, {"expression": "1+1", "user_id": "B"}]
)
def test_calculator_args_reject_invalid_input(args):
    # 作用：拒绝缺失、空白、错误类型和额外字段，避免参数进入执行层。
    with pytest.raises(ValidationError):
        CalculatorArgs.model_validate(args)


@pytest.mark.parametrize(
    "args",
    [{"query": ""}, {"query": "x", "limit": 0}, {"query": "x", "limit": 11}, {"query": "x", "limit": "1"}],
)
def test_search_args_reject_invalid_input(args):
    # 作用：验证查询和条数的边界及严格类型。
    with pytest.raises(ValidationError):
        SearchArgs.model_validate(args)


@pytest.mark.parametrize(
    "args",
    [
        {"action": "add"},
        {"action": "add", "title": ""},
        {"action": "complete", "todo_id": "x"},
        {"action": "delete", "expected_version": 1},
        {"action": "update", "todo_id": "x", "expected_version": 1},
        {"action": "complete", "todo_id": "x", "expected_version": "1"},
    ],
)
def test_todo_args_require_action_fields(args):
    # 作用：验证写操作需要标题或最新 ID、版本，且更新必须有实际内容。
    with pytest.raises(ValidationError):
        TodoArgs.model_validate(args)


def test_tool_schemas_describe_all_three_tools():
    # 作用：每个内置工具都具备可供模型决策的名称、描述和严格对象 Schema。
    schemas = ToolRegistry().schemas()
    assert {item["function"]["name"] for item in schemas} == {"calculator", "search", "todo"}
    for item in schemas:
        function = item["function"]
        assert item["type"] == "function" and function["description"]
        assert function["parameters"]["type"] == "object"
        assert function["parameters"]["additionalProperties"] is False


def test_request_and_run_lists_are_not_shared():
    # 作用：不同请求及任务不共享工具列表，任务公开记录排除内部模型密钥。
    values = {"client_id": "client-1234567890", "request_id": "request-123", "content": "你好"}
    first, second = MessageRequest(**values), MessageRequest(**values)
    first.tool_names.append("todo")
    assert second.tool_names == []
    record = {"id": "r", "session_id": "s", "user_id": "A", "client_id": "c"}
    run, other = Run(**record), Run(**record)
    run.tool_names.append("todo")
    run.profile = {"api_key": "private-secret"}
    assert other.tool_names == []
    assert "profile" not in run.to_record()


@pytest.mark.parametrize("capacity,expected", [(0, 64), (640, 64), (8000, 800), (262144, 26214)])
def test_output_reserve_minimum_and_capacity(capacity, expected):
    # 作用：输出预留遵守最小值，并按容量计算；它不代表供应商输出限制。
    assert output_reserve({"context_capacity": capacity}) == expected


def test_context_watermarks_must_allow_compaction():
    # 作用：压缩目标必须低于触发阈值，否则配置应拒绝。
    with pytest.raises(ValidationError):
        RuntimeSettings(context_trigger=0.5, context_target=0.5)


@pytest.mark.parametrize(
    "reason,with_tools",
    [
        ("length", False),
        ("content_filter", True),
        ("", False),
        ("unknown", False),
        ("stop", True),
        ("tool_calls", False),
    ],
)
def test_finish_reason_rejects_invalid_response(reason, with_tools):
    # 作用：拒绝截断、未知结束和工具声明不匹配，防止错误响应被视为成功。
    from app.llm import ModelFailure
    from app.schemas import ToolCall

    calls = [ToolCall(id="c", name="calculator", arguments='{"expression":"1+1"}')] if with_tools else []
    with pytest.raises(ModelFailure):
        validate_finish_reason(ModelReply(text="回答", calls=calls, finish_reason=reason))


@pytest.mark.parametrize("reason", ["stop", "end_turn"])
def test_finish_reason_accepts_normal_answer(reason):
    # 作用：普通文本结束原因通过校验。
    validate_finish_reason(ModelReply(text="回答", finish_reason=reason))

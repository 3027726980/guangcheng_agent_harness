# 作者：LHF；时间：2026-10-23；作用：验证工具交互配对的纯逻辑。

import pytest

from app.context import ContextFailure, tool_groups


def test_incomplete_tool_pair_is_rejected():
    # 作用：验证孤立工具结果和缺失结果的工具声明被拒绝。
    with pytest.raises(ContextFailure):
        tool_groups([{"role": "assistant", "tool_calls": [{"id": "a"}]}])
    with pytest.raises(ContextFailure):
        tool_groups([{"role": "tool", "tool_call_id": "orphan"}])


def test_complete_tool_round_is_one_group():
    # 作者：LHF；时间：2026-10-23；作用：一批调用和全部结果构成不可拆分消息块。
    messages = [
        {"role": "assistant", "tool_calls": [{"id": "a"}, {"id": "b"}]},
        {"role": "tool", "tool_call_id": "a", "content": "1"},
        {"role": "tool", "tool_call_id": "b", "content": "2"},
        {"role": "user", "content": "继续"},
    ]
    assert tool_groups(messages) == [messages[:3], messages[3:]]

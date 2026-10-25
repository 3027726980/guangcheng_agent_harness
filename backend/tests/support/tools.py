# 作者：LHF；时间：2026-10-23；作用：通过真实注册表调用工具的公共辅助入口。

import json

from app.schemas import ToolCall
from app.tool.registry import ToolRegistry


async def invoke_tool(name, arguments, db=None, user_id="A", operation_id="test:operation"):
    # 作者：LHF；时间：2026-10-20；作用：所有工具业务测试都通过注册表校验并执行。
    call = ToolCall(id="test-call", name=name, arguments=json.dumps(arguments))
    return await ToolRegistry().execute(call, db, user_id, operation_id)

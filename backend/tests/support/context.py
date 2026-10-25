# 作者：LHF；时间：2026-10-23；作用：构造用于基础压缩测试的临时历史。

from app.storage import uid


async def setup(db):
    # 作用：构造多轮历史消息和受保护的当前请求，用于压缩测试。
    await db.initialize()
    for index in range(12):
        # 作用：在旧前缀中加入完整工具交互，检查压缩覆盖不会拆散调用与结果。
        message = {"role": "user" if index % 2 == 0 else "assistant", "content": "历史材料" * 60}
        if index == 0:
            message = {
                "role": "assistant",
                "content": "先计算",
                "tool_calls": [
                    {
                        "id": "history-calc",
                        "type": "function",
                        "function": {"name": "calculator", "arguments": '{"expression":"6*7"}'},
                    }
                ],
            }
        elif index == 1:
            message = {"role": "tool", "tool_call_id": "history-calc", "content": '{"ok":true,"result":42}'}
        await db.put(
            "message",
            {
                "id": f"history-{index}",
                "run_id": "old",
                "message": message,
            },
            parent="s",
        )
    request_id = uid()
    await db.put(
        "message",
        {
            "id": request_id,
            "run_id": "current",
            "input_kind": "request",
            "message": {"role": "user", "content": "每天最多30分钟，不要丢失这个要求"},
        },
        parent="s",
    )

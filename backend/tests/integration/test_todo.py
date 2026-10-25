# 作者：LHF；时间：2026-10-23；作用：验证待办的核心增查改完成删除真实落库。
from app.storage import Database
from tests.support.tools import invoke_tool


async def test_todo_crud_persists_state(tmp_path):
    # 作用：通过统一注册表完成所有基本操作，逐步核对数据库和列表状态。
    db = Database(str(tmp_path / "todo.db"))
    await db.initialize()
    try:
        added = await invoke_tool("todo", {"action": "add", "title": "计算4608"}, db, operation_id="add")
        item = added["item"]
        assert (await db.get(item["id"]))["title"] == "计算4608"
        listed = await invoke_tool("todo", {"action": "list"}, db, operation_id="list")
        assert [row["id"] for row in listed["items"]] == [item["id"]]
        updated = await invoke_tool(
            "todo",
            {
                "action": "update",
                "todo_id": item["id"],
                "expected_version": item["version"],
                "title": "复核4608",
            },
            db,
            operation_id="update",
        )
        assert (await db.get(item["id"]))["title"] == "复核4608"
        completed = await invoke_tool(
            "todo",
            {"action": "complete", "todo_id": item["id"], "expected_version": updated["item"]["version"]},
            db,
            operation_id="complete",
        )
        assert (await db.get(item["id"]))["status"] == "completed"
        await invoke_tool(
            "todo",
            {"action": "delete", "todo_id": item["id"], "expected_version": completed["item"]["version"]},
            db,
            operation_id="delete",
        )
        assert (await db.get(item["id"]))["deleted"] is True
        assert (await invoke_tool("todo", {"action": "list"}, db, operation_id="after"))["items"] == []
    finally:
        await db.close()

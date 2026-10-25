# 作者：LHF。
# 注释维护时间：2026-10-23。
# 文件作用：模拟搜索参数、工具定义、样例资料与关键词检索。

from pydantic import Field

from app.schemas import StrictModel
from app.storage import Database
from app.tool.base import BaseTool


class SearchArgs(StrictModel):
    query: str = Field(min_length=1, max_length=500, description="查询样例资料；结果为明确标记的模拟数据")
    limit: int = Field(default=3, ge=1, le=10)


class SearchTool(BaseTool[SearchArgs]):
    name = "search"
    description = "搜索固定样例资料（MOCK，非联网）。没有匹配返回空结果。"
    arguments = SearchArgs
    execution_mode = "parallel"

    async def execute(self, args: SearchArgs, db: Database, user_id: str, operation_id: str):
        # 作用：检索固定样例并保留模拟标记，不调用真实网络。
        return _search(args.query, args.limit)


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
    # 作用：以命中关键词数量排序，无命中则返回空结果，不补造资料。
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

# 作者：LHF。
# 时间：2026-10-21。
# 作用：集中定义执行任务字段；运行时使用模型，数据库与 API 使用公开字典。
from typing import Any, Literal

from pydantic import ConfigDict, Field

from app.schemas import RuntimeSettings, StrictModel

RunStatus = Literal[
    "queued", "running", "cancelling", "completed", "cancelled", "failed", "interrupted", "limited"
]
RunPurpose = Literal["chat", "context_compaction"]


class ModelSnapshot(StrictModel):
    # 作用：记录不含密钥的模型身份与容量，供任务追踪使用。
    id: str
    model: str
    context_capacity: int
    capacity_source: str


class Run(StrictModel):
    # 作用：表示一次执行任务；校验创建及后续赋值，禁止动态增加未声明字段。
    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)

    id: str
    session_id: str
    user_id: str
    client_id: str
    # 默认值兼容历史精简记录；新任务由 submit 显式填写内容和创建时间。
    content: str = ""
    purpose: RunPurpose = "chat"
    status: RunStatus = "queued"
    created_at: float = 0.0
    model_calls: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)
    reason: str | None = None
    tool_names: list[str] = Field(default_factory=list)
    started_at: float | None = None
    ended_at: float | None = None
    settings: RuntimeSettings | None = None
    model_snapshot: ModelSnapshot | None = None
    compaction_result: Literal["compacted", "skipped"] | None = None
    compaction_message: str | None = None
    steering_id: str | None = None
    steering_run_id: str | None = None

    # 以下字段仅用于进程内执行，任何 model_dump 都不会包含密钥或临时输出。
    profile: dict[str, Any] = Field(default_factory=dict, exclude=True, repr=False)
    summary_profile: dict[str, Any] = Field(default_factory=dict, exclude=True, repr=False)
    partial: str = Field(default="", exclude=True, repr=False)
    partial_reasoning: str = Field(default="", exclude=True, repr=False)

    def to_record(self) -> dict:
        # 作用：生成兼容现有数据库和 API 的 JSON 字典，保留旧记录的缺省字段形态。
        return self.model_dump(mode="json", exclude_unset=True)

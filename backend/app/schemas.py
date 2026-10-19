"""Shared Pydantic contracts; business rules live in services, not schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class RuntimeSettings(StrictModel):
    max_model_calls: int = Field(default=20, ge=1, le=1000)
    max_tool_calls: int = Field(default=40, ge=1, le=1000)
    max_seconds: float = Field(default=300.0, gt=0, le=86400)
    model_timeout: float = Field(default=60.0, gt=0, le=3600)
    tool_timeout: float = Field(default=10.0, gt=0, le=3600)
    retries: int = Field(default=3, ge=0, le=20)
    retry_seconds: float = Field(default=30.0, ge=0, le=3600)
    tool_concurrency: int = Field(default=4, ge=1, le=32)
    max_output_tokens: int = Field(default=2000, ge=64, le=131072)
    summary_tokens: int = Field(default=1000, ge=64, le=32768)
    context_trigger: float = Field(default=0.8, gt=0, lt=1)
    context_target: float = Field(default=0.5, gt=0, lt=1)
    default_profile_id: str | None = None
    summary_profile_id: str | None = None

    @model_validator(mode="after")
    def validate_watermarks(self):
        if self.context_target >= self.context_trigger:
            raise ValueError("压缩目标必须低于触发比例")
        return self


class ModelProfile(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    base_url: str = Field(min_length=1, max_length=1000)
    api_key: str = Field(default="", max_length=4096)
    model: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_url(self):
        HttpUrl(self.base_url)
        self.base_url = self.base_url.rstrip("/")
        return self


class SessionCreate(StrictModel):
    title: str = Field(default="新对话", min_length=1, max_length=100)


class MessageRequest(StrictModel):
    client_id: str = Field(min_length=16, max_length=100)
    request_id: str = Field(min_length=8, max_length=100)
    content: str = Field(min_length=1, max_length=200000)


class SteeringRequest(StrictModel):
    content: str = Field(min_length=1, max_length=200000)
    request_id: str = Field(min_length=8, max_length=100)


class CalculatorArgs(StrictModel):
    expression: str = Field(min_length=1, max_length=256, description="括号、小数、+ - * / %；不支持代码")


class SearchArgs(StrictModel):
    query: str = Field(min_length=1, max_length=500, description="查询样例资料；结果为明确标记的模拟数据")
    limit: int = Field(default=3, ge=1, le=10)


class TodoArgs(StrictModel):
    action: Literal["add", "list", "update", "complete", "delete"]
    todo_id: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=4000)
    expected_version: int | None = Field(default=None, ge=1)
    status: Literal["pending", "completed"] | None = None

    @model_validator(mode="after")
    def required_by_action(self):
        if self.action == "add" and not self.title:
            raise ValueError("新增待办必须提供标题")
        if self.action in {"update", "complete", "delete"}:
            if not self.todo_id or self.expected_version is None:
                raise ValueError("修改待办必须提供 todo_id 与 expected_version；请先查询")
        if self.action == "update" and self.title is None and self.notes is None and self.status is None:
            raise ValueError("修改内容不能为空")
        return self


class ToolCall(StrictModel):
    id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    arguments: str = Field(max_length=100000)


class ModelReply(BaseModel):
    text: str = ""
    calls: list[ToolCall] = Field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict = Field(default_factory=dict)


class Event(BaseModel):
    id: int
    user_id: str | None
    session_id: str | None
    run_id: str | None
    type: str
    timestamp: float
    data: dict

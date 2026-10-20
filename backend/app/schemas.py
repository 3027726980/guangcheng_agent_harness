# 作者：LHF。
# 注释维护时间：2026-10-20。
# 文件作用：HTTP 请求、运行配置、工具参数和模型响应的数据契约。
"""Shared Pydantic contracts; business rules live in services, not schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class StrictModel(BaseModel):
    # 禁止未知字段与隐式类型转换，使 HTTP 请求和工具参数在入口处暴露格式错误。
    model_config = ConfigDict(extra="forbid", strict=True)


class RuntimeSettings(StrictModel):
    # 每个任务启动时读取快照；摘要调用和重试同样消耗模型次数及执行时间预算。
    max_model_calls: int = Field(default=20, ge=1, le=1000)
    max_tool_calls: int = Field(default=40, ge=1, le=1000)
    max_seconds: float = Field(default=300.0, gt=0, le=86400)
    model_timeout: float = Field(default=60.0, gt=0, le=3600)
    tool_timeout: float = Field(default=10.0, gt=0, le=3600)
    retries: int = Field(default=3, ge=0, le=20)
    retry_seconds: float = Field(default=30.0, ge=0, le=3600)
    tool_concurrency: int = Field(default=4, ge=1, le=32)
    # 达到 trigger 触发压缩，尽量回落到 target；两者针对可用输入预算计算。
    context_trigger: float = Field(default=0.8, gt=0, lt=1)
    context_target: float = Field(default=0.5, gt=0, lt=1)
    default_profile_id: str | None = None
    summary_profile_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def discard_legacy_output_settings(cls, data):
        # 兼容旧数据库或客户端中的固定输出上限字段，但不再保留这些配置。
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if k not in {"max_output_tokens", "summary_tokens"}}
        return data

    @model_validator(mode="after")
    def validate_watermarks(self):
        # 作用：要求压缩目标比例低于触发比例，避免配置无法形成回落区间。
        if self.context_target >= self.context_trigger:
            raise ValueError("压缩目标必须低于触发比例")
        return self


class ModelProfile(StrictModel):
    # 仅描述用户可编辑的连接信息，测试状态和容量信息由服务端探测后补充。
    name: str = Field(min_length=1, max_length=80)
    base_url: str = Field(min_length=1, max_length=1000)
    api_key: str = Field(default="", max_length=4096)
    model: str = Field(min_length=1, max_length=200)
    output_token_parameter: Literal["max_tokens", "max_completion_tokens"] = "max_tokens"
    # 只允许启用或关闭；具体思考强度由供应商默认值决定，不向用户开放强度参数。
    thinking_enabled: bool = False

    @model_validator(mode="after")
    def validate_url(self):
        # 作用：校验模型地址为 HTTP URL，并去掉末尾斜杠以统一路径拼接。
        HttpUrl(self.base_url)
        self.base_url = self.base_url.rstrip("/")
        return self


class SessionCreate(StrictModel):
    title: str = Field(default="新对话", min_length=1, max_length=100)


class CompactionRequest(StrictModel):
    # client_id 绑定事件连接，request_id 用于识别重复提交；聊天请求复用这两个字段。
    client_id: str = Field(min_length=16, max_length=100)
    request_id: str = Field(min_length=8, max_length=100)


class MessageRequest(CompactionRequest):
    content: str = Field(min_length=1, max_length=200000)
    # @选择只声明工具名称，参数仍由模型根据任务生成并经过工具层校验。
    tool_names: list[str] = Field(default_factory=list, max_length=16)


class SteeringRequest(StrictModel):
    # 引导归属由 URL 中的任务 ID 决定，无需再提供客户端 ID。
    content: str = Field(min_length=1, max_length=200000)
    request_id: str = Field(min_length=8, max_length=100)
    tool_names: list[str] = Field(default_factory=list, max_length=16)


class CalculatorArgs(StrictModel):
    expression: str = Field(min_length=1, max_length=256, description="括号、小数、+ - * / %；不支持代码")


class SearchArgs(StrictModel):
    query: str = Field(min_length=1, max_length=500, description="查询样例资料；结果为明确标记的模拟数据")
    limit: int = Field(default=3, ge=1, le=10)


class TodoArgs(StrictModel):
    # 同一参数结构同时用于模型工具和手动接口；写操作需要调用方持有最新版本。
    action: Literal["add", "list", "update", "complete", "delete"]
    todo_id: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=4000)
    expected_version: int | None = Field(default=None, ge=1)
    status: Literal["pending", "completed"] | None = None

    @model_validator(mode="after")
    def required_by_action(self):
        # 字段是否必填取决于 action，跨字段规则在整体校验时检查。
        if self.action == "add" and not self.title:
            raise ValueError("新增待办必须提供标题")
        if self.action in {"update", "complete", "delete"}:
            if not self.todo_id or self.expected_version is None:
                raise ValueError("修改待办必须提供 todo_id 与 expected_version；请先查询")
        if self.action == "update" and self.title is None and self.notes is None and self.status is None:
            raise ValueError("修改内容不能为空")
        return self


class ToolCall(StrictModel):
    # arguments 保持模型返回的原始 JSON 字符串，注册表按具体工具参数模型解析。
    id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    arguments: str = Field(max_length=100000)


class ModelReply(BaseModel):
    # 将流式和非流式供应商响应统一成 Runtime 可处理的结构。
    text: str = ""
    reasoning: str = ""
    # 原生协议字段需原样回传；展示用 reasoning 还可能包含从 think 标签提取的内容。
    reasoning_content: str | None = None
    calls: list[ToolCall] = Field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict = Field(default_factory=dict)


class Event(BaseModel):
    # run/session 用于前端路由事件；id 与持久化事件表一致，timestamp 为 Unix 秒。
    id: int
    user_id: str | None
    session_id: str | None
    run_id: str | None
    type: str
    timestamp: float
    data: dict

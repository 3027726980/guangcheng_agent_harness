# 作者：LHF。
# 注释维护时间：2026-10-23。
# 文件作用：工具抽象契约与统一业务错误。

from abc import ABC, abstractmethod
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel

from app.storage import Database


class ToolError(Exception):
    def __init__(self, code, message):
        # 作用：保存稳定错误码和用户可读提示，供工具结果及接口复用。
        self.code = code
        super().__init__(message)


Args = TypeVar("Args", bound=BaseModel)


class BaseTool(ABC, Generic[Args]):
    """工具统一契约：子类声明元数据与参数模型，实现异步执行方法。"""

    name: str
    description: str
    arguments: type[Args]
    execution_mode: Literal["parallel", "sequential"]
    # 作者：LHF；时间：2026-10-21；作用：内部工具仅供模型调用，不开放用户 @ 选择。
    user_selectable: bool = True

    def schema(self):
        # 作用：从统一参数模型生成函数声明，与注册表执行前的校验保持一致。
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.arguments.model_json_schema(),
            },
        }

    @abstractmethod
    async def execute(self, args: Args, db: Database, user_id: str, operation_id: str):
        # 作用：由具体工具执行已校验参数，使用可信用户身份及幂等操作 ID。
        raise NotImplementedError

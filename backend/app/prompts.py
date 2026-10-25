# 作者：LHF；时间：2026-10-23；作用：汇总提示词模块，统一校验、渲染和标识版本。
"""Load Python prompt definitions with validated placeholders and version hashes."""

import hashlib
from string import Template

from app.prompt.summary import SUMMARY_PROMPT
from app.prompt.summary_prefix import SUMMARY_PREFIX_PROMPT
from app.prompt.system import SYSTEM_PROMPT
from app.prompt.tool_preference import TOOL_PREFERENCE_PROMPT

# 提示词随 Python 模块加载；修改后需重启进程或由开发服务器重载。
PROMPTS = {
    "system": SYSTEM_PROMPT,
    "summary": SUMMARY_PROMPT,
    "summary_prefix": SUMMARY_PREFIX_PROMPT,
    "tool_preference": TOOL_PREFERENCE_PROMPT,
}


class PromptError(ValueError):
    """Required prompt definitions are missing or malformed."""


class PromptMessages(list):
    """Message list carrying immutable request provenance outside the wire body."""

    def __init__(self, messages, *, prompt_versions=None, context_version=None):
        # 作用：保存本轮输入及版本，元数据不进入供应商 messages。
        super().__init__(messages)
        self.prompt_versions = dict(prompt_versions or {})
        self.context_version = context_version


class PromptStore:
    required = {
        "system": set(),
        "summary": set(),
        "summary_prefix": {"summary"},
        "tool_preference": {"tools"},
    }

    def load(self):
        # 作用：从模块常量构建独立模板快照，校验占位符并保留内容哈希。
        texts, versions = {}, {}
        for name, expected in self.required.items():
            value = PROMPTS.get(name)
            if not isinstance(value, str):
                raise PromptError(f"提示词 {name} 缺失或不是文本")
            text = value.strip()
            template = Template(text)
            if not text or not template.is_valid() or set(template.get_identifiers()) != expected:
                raise PromptError(f"提示词 {name} 为空或占位符不正确")
            texts[name] = text
            versions[name] = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return PromptBundle(texts, versions)


class PromptBundle:
    def __init__(self, texts, versions):
        # 作用：固定一次构建使用的模板及其内容摘要。
        self.texts, self.versions = texts, versions

    def render(self, name, **values):
        # 作用：只作字符串替换，不执行模板内容。
        return Template(self.texts[name]).substitute(values)

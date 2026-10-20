# 作者：LHF。
# 时间：2026-10-20。
# 作用：集中判断已知供应商的协议限制，避免按模型名称误改其他兼容服务。
from urllib.parse import urlsplit


def thinking_enabled(profile):
    """读取布尔开关；旧强度配置仅用于恢复开关状态，不继续向模型发送强度。"""
    enabled = profile.get("thinking_enabled")
    if isinstance(enabled, bool):
        return enabled
    effort = profile.get("reasoning_effort")
    if effort is not None:
        return effort != "none"
    # 兼容旧记录未指定参数时的官方 DeepSeek 默认行为，新配置始终含显式布尔值。
    model = profile.get("model", "")
    return urlsplit(profile.get("base_url", "")).hostname == "api.deepseek.com" and (
        model in {"deepseek-flash", "deepseek-reasoner"} or model.startswith("deepseek-v4-")
    )


def thinking_options(profile):
    """将开关转换成兼容接口的 thinking.type；普通未知接口关闭时不附加专有参数。"""
    enabled = thinking_enabled(profile)
    host = urlsplit(profile.get("base_url", "")).hostname
    if enabled or host in {"api.deepseek.com", "open.bigmodel.cn"}:
        return {"thinking": {"type": "enabled" if enabled else "disabled"}}
    return {}


def deepseek_thinking(profile):
    """只在官方 DeepSeek 且已开启思考时启用对应工具调用兼容策略。"""
    return urlsplit(profile.get("base_url", "")).hostname == "api.deepseek.com" and thinking_enabled(profile)

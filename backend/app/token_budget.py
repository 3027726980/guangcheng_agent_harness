# 作者：LHF。
# 注释维护时间：2026-10-20。
# 文件作用：计算本地上下文规划使用的输出预留空间。
"""Internal context budgets, independent of the provider's answer output limit."""


def output_reserve(profile):
    # 仅用于本地规划上下文：按容量预留 10%，至少 64；不会限制供应商的实际输出长度。
    return max(64, int(profile.get("context_capacity", 262144) * 0.1))

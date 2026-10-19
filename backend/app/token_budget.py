"""Internal context budgets, independent of the provider's answer output limit."""


def output_reserve(profile):
    return max(64, int(profile.get("context_capacity", 262144) * 0.1))


def summary_budget(profile, summary_profile, target):
    capacity = profile.get("context_capacity", 262144)
    summary_capacity = summary_profile.get("context_capacity", 262144)
    available = capacity - output_reserve(profile) - max(256, int(capacity * 0.05))
    # Text length target only: never use this as a reasoning + output generation cap.
    return max(64, min(8192, int(summary_capacity * 0.05), int(available * target / 8)))

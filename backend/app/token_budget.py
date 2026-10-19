"""Internal context budgets, independent of the provider's answer output limit."""


def output_reserve(profile):
    return max(64, int(profile.get("context_capacity", 262144) * 0.1))

from app.schemas import RuntimeSettings
from app.token_budget import output_reserve, summary_budget


def test_legacy_limits_do_not_survive_settings_round_trip():
    settings = RuntimeSettings.model_validate({"max_output_tokens": 2000, "summary_tokens": 1000})
    assert "max_output_tokens" not in settings.model_dump()
    assert "summary_tokens" not in settings.model_dump()


def test_budgets_follow_capacity_and_summary_target():
    small = {"context_capacity": 8000}
    large = {"context_capacity": 262144}
    assert output_reserve(small) < output_reserve(large)
    assert summary_budget(large, small, 0.5) <= 400
    assert summary_budget(small, large, 0.3) < summary_budget(small, large, 0.7)
    assert 64 <= summary_budget(large, large, 0.5) <= 8192

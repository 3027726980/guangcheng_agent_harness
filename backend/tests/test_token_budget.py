from app.schemas import RuntimeSettings
from app.token_budget import output_reserve


def test_legacy_limits_do_not_survive_settings_round_trip():
    settings = RuntimeSettings.model_validate({"max_output_tokens": 2000, "summary_tokens": 1000})
    assert "max_output_tokens" not in settings.model_dump()
    assert "summary_tokens" not in settings.model_dump()


def test_input_reserve_follows_capacity():
    small = {"context_capacity": 8000}
    large = {"context_capacity": 262144}
    assert output_reserve(small) < output_reserve(large)

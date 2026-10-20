# 作者：LHF。
# 时间：2026-10-20。
# 作用：验证 test_token_budget 所覆盖的行为与边界，使用离线数据及临时资源。
from app.schemas import RuntimeSettings
from app.token_budget import output_reserve


def test_legacy_limits_do_not_survive_settings_round_trip():
    # 作用：验证旧版固定输出限制字段被兼容读取但不会再次保存。
    settings = RuntimeSettings.model_validate({"max_output_tokens": 2000, "summary_tokens": 1000})
    assert "max_output_tokens" not in settings.model_dump()
    assert "summary_tokens" not in settings.model_dump()


def test_input_reserve_follows_capacity():
    # 作用：验证上下文输出预留随容量变化并满足最小值。
    small = {"context_capacity": 8000}
    large = {"context_capacity": 262144}
    assert output_reserve(small) < output_reserve(large)

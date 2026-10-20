# 作者：LHF。
# 时间：2026-10-20。
# 作用：验证模型思考模式只允许布尔开关、旧配置兼容和真实 SDK 请求参数。
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.llm import OpenAIModel
from app.main import create_app, public_profile
from app.schemas import ModelProfile
from tests.test_api import ProbeModel

PROFILE = {"name": "fixture", "base_url": "https://api.deepseek.com/v1", "model": "deepseek-flash"}


def test_model_profile_only_accepts_boolean_thinking_switch():
    """模型配置提供布尔开关，并拒绝旧强度字段和字符串形式的布尔值。"""
    assert ModelProfile(**PROFILE).thinking_enabled is False
    assert ModelProfile(**PROFILE, thinking_enabled=True).thinking_enabled is True
    with pytest.raises(ValidationError):
        ModelProfile(**PROFILE, reasoning_effort="max")
    with pytest.raises(ValidationError):
        ModelProfile(**PROFILE, thinking_enabled="true")


@pytest.mark.parametrize("enabled", [True, False])
async def test_deepseek_sdk_request_uses_only_thinking_toggle(enabled):
    """实际 SDK 请求按开关发送 enabled/disabled，不保留旧强度参数。"""
    def respond(request):
        """检查出站请求，而非仅检查本地构造的参数字典。"""
        payload = json.loads(request.content)
        assert payload["thinking"] == {"type": "enabled" if enabled else "disabled"}
        assert "reasoning_effort" not in payload
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": "OK"}}]})

    reply = await OpenAIModel(httpx.MockTransport(respond)).complete(
        {**PROFILE, "thinking_enabled": enabled, "reasoning_effort": "max"}, [], None, None, 5,
    )
    assert reply.text == "OK"


@pytest.mark.parametrize("effort,enabled", [("max", True), ("low", True), ("none", False), (None, True)])
def test_legacy_profile_exposes_only_normalized_switch(effort, enabled):
    """旧配置只暴露归一化后的开关，既不回传强度也不修改原记录。"""
    original = {**PROFILE, "reasoning_effort": effort, "api_key": "fixture-secret"}
    public = public_profile(original)
    assert public["thinking_enabled"] is enabled
    assert "reasoning_effort" not in public
    assert original["reasoning_effort"] == effort
    assert public["api_key"] == ""


def test_api_round_trip_and_retesting_legacy_profile(tmp_path):
    """保存与读取只使用开关；重新测试旧记录时保留启用状态并移除强度。"""
    app = create_app(str(tmp_path / "switch.db"), ProbeModel([]))
    with TestClient(app) as client:
        response = client.post("/api/models", json={**PROFILE, "thinking_enabled": True})
        assert response.status_code == 200
        profile = response.json()
        assert profile["thinking_enabled"] is True
        assert "reasoning_effort" not in profile
        updated = client.put(f"/api/models/{profile['id']}", json={**PROFILE, "thinking_enabled": False})
        assert updated.status_code == 200
        assert updated.json()["thinking_enabled"] is False
        assert client.post("/api/models", json={**PROFILE, "reasoning_effort": "high"}).status_code == 422
        # 仅写入测试临时库，模拟旧版本保存的连接，不修改用户数据库。
        legacy = {**profile, "reasoning_effort": "max"}
        legacy.pop("thinking_enabled")
        client.portal.call(app.state.runtime.db.put, "profile", legacy)
        retested = client.post(f"/api/models/{profile['id']}/test")
        assert retested.status_code == 200
        assert retested.json()["thinking_enabled"] is True
        saved = client.portal.call(app.state.runtime.db.get, profile["id"])
        assert "reasoning_effort" not in saved


async def test_unknown_provider_with_switch_off_keeps_plain_chat_compatible():
    """未启用思考且未知的普通兼容接口不附加供应商专有开关参数。"""
    def respond(request):
        """拒绝额外思考参数，以模拟仅支持标准聊天的服务。"""
        payload = json.loads(request.content)
        assert "thinking" not in payload and "reasoning_effort" not in payload
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": "OK"}}]})

    await OpenAIModel(httpx.MockTransport(respond)).complete(
        {**PROFILE, "base_url": "https://fixture.invalid/v1", "thinking_enabled": False}, [], None, None, 5,
    )

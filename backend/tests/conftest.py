# 作者：LHF；时间：2026-10-23；作用：注册离线夹具并隔离测试日志和真实模型网络。
import httpx
import pytest

from tests.support.runtime import harness  # noqa: F401


@pytest.fixture(autouse=True)
def isolate_local_diagnostics(tmp_path, monkeypatch):
    # 作者：LHF；时间：2026-10-22；作用：离线测试日志只落临时目录，不污染真实项目日志。
    monkeypatch.setenv("HARNESS_LOG_DIR", str(tmp_path / "logs"))


@pytest.fixture(autouse=True)
def reject_real_http(monkeypatch):
    # 作用：阻断默认异步 HTTP 传输，SDK 用例只能使用显式 MockTransport。
    async def reject(self, request):
        # 作用：在网络请求发送前终止，避免错误配置导致真实模型调用。
        raise AssertionError("离线测试禁止真实 HTTP 请求，请使用 MockTransport")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", reject)

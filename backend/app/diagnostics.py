# 作者：LHF；时间：2026-10-22；作用：按北京时间写入诊断日志，会话文件同时保存模型调用快照。
"""Ordered local diagnostics; SQLite remains authoritative on file failures."""

import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

BEIJING = timezone(timedelta(hours=8))
SECRET_FIELDS = {
    "api_key",
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "password",
    "access_token",
    "refresh_token",
    "client_secret",
    "credentials",
    "api_token",
    "bearer_token",
}


def redact(value, secrets=()):
    # 作用：去除结构化凭据并替换已知密钥，保留普通正文和工具结果长度。
    if isinstance(value, dict):
        return {
            key: "[REDACTED]"
            if key.lower().replace("-", "_") in {name.replace("-", "_") for name in SECRET_FIELDS}
            else redact(item, secrets)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item, secrets) for item in value]
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, "[REDACTED]")
        value = re.sub(r"(?i)(https?://)[^/\s:@]+:[^/\s@]+@", r"\1[REDACTED]@", value)
    return value


class Diagnostics:
    def __init__(self, root=None):
        # 作用：创建实例独立的写入锁；不在导入时创建文件或后台任务。
        self.root = Path(
            root or os.environ.get("HARNESS_LOG_DIR") or Path(__file__).resolve().parents[2] / "logs"
        )
        self.lock = asyncio.Lock()
        self.error = None
        self.secrets = set()

    def remember_secret(self, secret):
        # 作用：将已知连接密钥仅保存在进程内，用于日志脱敏。
        if secret:
            self.secrets.add(secret)

    def safe(self, data):
        # 作用：复制并脱敏输出，不修改执行过程中使用的原始内容。
        return redact(data, self.secrets)

    async def write(self, category, data, *, timestamp=None, filename=None, replace=False):
        # 作用：串行等待文件写入，失败记入状态和 stderr，不重放业务操作。
        stamp = timestamp if timestamp is not None else time.time()
        day = datetime.fromtimestamp(stamp, BEIJING).strftime("%Y-%m-%d")
        relative = Path(category) / filename if filename else Path(f"{category}.jsonl")
        path = self.root / day / relative
        payload = json.dumps(self.safe(data), ensure_ascii=False) + "\n"
        async with self.lock:
            try:
                writer = asyncio.create_task(asyncio.to_thread(self._write, path, payload, replace))
                try:
                    await asyncio.shield(writer)
                except asyncio.CancelledError:
                    await writer
                    raise
                return True
            except OSError as error:
                if not self.error or self.error["error"] != type(error).__name__:
                    self.error = {
                        "message": "本地日志写入失败，数据库记录仍保留",
                        "error": type(error).__name__,
                        "timestamp": time.time(),
                    }
                print(json.dumps(self.error, ensure_ascii=False), file=sys.stderr)
                # 主目录不可写时，这个尽力记录也可能失败，stderr 保留兜底信息。
                try:
                    await asyncio.to_thread(
                        self._write,
                        self.root / day / "app.jsonl",
                        json.dumps(self.error, ensure_ascii=False) + "\n",
                        False,
                    )
                except OSError:
                    pass
                return False

    @staticmethod
    def _write(path, payload, replace):
        # 作用：在线程内写入；快照通过同目录临时文件替换，避免读到半个 JSON。
        path.parent.mkdir(parents=True, exist_ok=True)
        if replace:
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(payload, encoding="utf-8")
            temporary.replace(path)
        else:
            with path.open("a", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()

    async def event(self, event):
        # 作用：使用数据库事件时间分目录，保留原始递增事件 ID。
        session = event.get("session_id")
        if session:
            safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", session)
            return await self.write(
                "sessions", event, timestamp=event["timestamp"], filename=f"{safe_id}.jsonl"
            )
        return await self.write("app", event, timestamp=event["timestamp"])

    async def call(self, record):
        # 作者：LHF；时间：2026-10-22；作用：将调用快照追加到所属会话日志，不再创建独立调用文件。
        # 开始和结束各保留一条快照，用 call_id 关联；结束记录使用结束时间参与日期归档。
        # 快照不是数据库业务事件，不占用事件 ID；原始调用字段完整保留在 data 中。
        return await self.event(
            {
                "type": "model.snapshot",
                "timestamp": record.get("ended_at", record["timestamp"]),
                "session_id": record["session_id"],
                "run_id": record["run_id"],
                "user_id": record["user_id"],
                "data": record,
            }
        )

    async def close(self):
        # 作用：等待已经进入写入锁的工作完成；调用方先等待业务协程收尾。
        async with self.lock:
            pass

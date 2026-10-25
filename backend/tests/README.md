# 笔试核心功能测试

作者：LHF；日期：2026-10-23。测试范围对应原题要求 2、3；生产功能没有随测试精简而删除。

| 目录 | 范围 | 外部依赖 |
| --- | --- | --- |
| `unit/` | 参数、注册机制、计算与样例搜索、思考解析、工具消息配对 | 无模型请求或数据库；异步函数也可属于单元测试 |
| `integration/` | Runtime 工具循环、会话、临时 SQLite、基础压缩、API、真实 SDK 假传输 | 临时资源、ScriptedModel、MockTransport，不启动监听服务 |
| `support/` | 公共夹具、工具调用和历史构造 | 不含测试入口 |
| `agent_acceptance/` | 六个真实模型人工验收场景与记录 | 由执行者自行配置和运行，不属于 pytest |

共用 `conftest.py` 隔离日志并阻断默认异步 HTTP 传输，避免错误配置发起真实模型调用。离线测试检查程序是否正确传递和处理模型输出；模型是否真正理解任务，需另做人工验收。

## PowerShell

从后端目录执行：

```powershell
Set-Location 'D:\MyProject\guangcheng_agent_harness\backend'
uv sync --group dev
uv run pytest tests/unit -q
uv run pytest tests/integration -q
uv run pytest -q
uv run ruff check tests
uv run ruff format --check tests
```

使用已配置解释器时，也可用 `.\.venv\Scripts\python.exe -m pytest` 代替 `uv run pytest`。

## 覆盖率

```powershell
uv run pytest -q --cov=app --cov-branch --cov-report=term-missing --cov-report=html --cov-report=xml
Start-Process .\test-results\coverage\html\index.html
```

这是**单元＋集成测试综合覆盖率**。`app` 全部 Python 业务模块纳入统计，包括未导入模块；没有通过排除难测模块抬高比例，也没有强制百分比门槛。终端 `Cover` 在开启分支统计时是语句与分支机会的综合比例，不能直接称为行覆盖率；分别读取 XML 根节点的 `line-rate`、`branch-rate`。HTML 可查看缺失行和未走到的分支。报告、`.coverage` 和 XML 不提交 Git。

如只运行 `tests/unit` 采集覆盖率，应另存报告并标为单元测试覆盖率，不能与本次综合报告混用。

## PyCharm

选择解释器 `D:\MyProject\guangcheng_agent_harness\backend\.venv\Scripts\python.exe`，工作目录统一为 `D:\MyProject\guangcheng_agent_harness\backend`。

在 Run → Edit Configurations → Python tests → pytest 分别创建：

| 配置 | Target | Additional Arguments |
| --- | --- | --- |
| 后端单元测试 | `tests/unit` | `-q` |
| 后端集成测试 | `tests/integration` | `-q` |
| 后端全部离线测试 | `tests` | `-q` |

普通 Run 显示测试结果；Run with Coverage 显示覆盖率及源码标色，重点查看 `app`。使用 IDE 覆盖率运行时不要同时在参数中加 `--cov`；需要生成本项目约定的 HTML／XML 时用上面的终端命令。

题目对应关系见 [需求映射](../../dev_docs/requirements.md)，六个场景见 [真实模型验收](agent_acceptance/README.md)，本轮增删与实测结果见 [验证记录](../../dev_docs/verification.md)。

# 日志、增量上下文和调用输入

作者：LHF。时间：2026-10-22。作用：说明本轮实现的数据流、维护入口和故障边界。

## 数据流

正式消息 → message 与 context 清单同事务保存 → 更新 SessionContext 内存 → 复制可见视图 → 从 Python 常量构建提示词快照并注入协议字段 → 检查容量 → 在 SDK 发送前保存调用快照 → 调用模型 → 保存响应及状态。

用户请求和引导正式应用时，Runtime 将工具偏好模板渲染一次并写入模型消息正文，原文另存为 `original_content` 供界面展示，实际模板版本另存为 `tool_preference_version`。后续构建直接复用正文，不遍历历史重新拼接偏好；重试、缓存恢复和摘要均使用该消息已固定的正文。模板修改只影响新应用的消息，旧记录不补写。

压缩时选取当前请求、引导等保护点之前的完整连续前缀；模型生成摘要期间不占会话锁。提交时核对版本，摘要与清单一起提交，之后更新内存。版本改变则丢弃旧结果、重新构建；模型失败、取消或提交失败不覆盖旧视图。摘要节点位于未压缩消息之前，后缀原顺序不变。

旧会话首次访问才读取完整 message 和 summary，根据 covered 建立清单。重启只按 message_ids 批量加载仍可见的消息。系统提示不保存在 SessionContext；聊天历史页面仍查询完整原消息，压缩不会删历史。工具调用 ID 集合按会话保存在 SessionContext 和上下文清单中，消息追加时同事务增量登记，后续 Run 直接查询内存集合。旧清单缺少集合字段时扫描一次完整历史补齐；上下文压缩保留全部调用 ID，重启直接恢复集合，不再逐个 Run 遍历消息。

## 本地文件

默认根目录为项目 `logs/`，环境变量 `HARNESS_LOG_DIR` 可覆盖。按北京时间日期写入：

```text
logs/YYYY-MM-DD/
  app.jsonl
  http.jsonl
  sessions/<session_id>.jsonl
```

app 包括启动、关闭、异常位置和日志故障；HTTP 记录方法、路径、状态码、耗时及 X-Request-ID，不采集正文、查询串和请求头。会话日志保存接收和处理的全部业务事件，包括增量、工具参数／结果、引导、取消及压缩，保留数据库事件 ID。模型调用快照也追加到同一会话文件，类型为 `model.snapshot`，完整记录放在 `data`，通过 `data.call_id` 关联开始与结束状态；快照不占用数据库业务事件 ID。记录按发生时间分目录，调用结束快照使用结束时间，因此跨日会话仍按天拆分。不再创建 `model-calls` 目录中的独立调用文件，已有历史文件保留。

写入按实例锁串行执行，等待文件写入完成；取消不会提前释放正在写文件的锁。正常关闭先等业务收尾再等写入结束。会话事件和调用快照均按行追加。密钥字段、认证头字段、已知 API Key 和 URL 中的账号密码会脱敏，正常正文不截断。日志不自动清理，运行目录被 Git 忽略。强制结束进程前未落盘的数据无法保证恢复。

文件失败仍保留 SQLite 事件，不重跑工具。故障写到 stderr，并尽力写 app 日志；`logging.status`、SSE ready 和健康接口告知前端。故障状态保留至本次进程结束，方便确认曾有日志缺失。相同类型故障不重复广播。若调用输入未能存入数据库或本地文件，该次请求不会发送。

## 调用快照

`request_capture.py` 在传输边界复制 SDK 参数，按 SDK 规则合并 extra_body，保存真正发送的 HTTP JSON。不存 API Key、认证头或连接凭据。调用元数据包括归属、Run、用途、尝试、时间、上下文版本和提示词哈希；响应包括最终文本、思考、工具调用、finish_reason 和 usage。失败／取消记录终态和已收到的正文／思考片段。

每次失败重试单独生成 call_id；同一请求的 messages、工具和模板版本在重试前冻结。历史输入不会被后续追加或模板变动修改。每次新请求从 Python 常量构建模板快照，缺少定义或模板不合法就报错。修改 Python 提示词后需重启后端或由开发服务器重载模块。旧调用不补造输入。

Trace 中“模型调用输入”独立查询清单，选中调用才读取完整输入，按消息顺序显示；可展开工具定义、参数、思考协议及完整 JSON，并复制。切换 Run 时清除旧详情，迟到响应不会覆盖新任务。列表不依赖当前事件窗口的 2000 条限制。接口分页和字段见 [interfaces.md](interfaces.md)。

## 维护入口

| 文件 | 职责 |
| --- | --- |
| `backend/app/diagnostics.py` | 分日写入、脱敏、故障状态 |
| `backend/app/session_context.py` | 清单、缓存、事务及版本检查 |
| `backend/app/context.py` | 协议组装、保护范围、预算及摘要 |
| `backend/app/prompt/` | 对话、摘要、摘要包装和工具偏好分别放在独立 Python 文件 |
| `backend/app/prompts.py` | 提示词汇总、占位符校验、渲染和版本 |
| `backend/app/request_capture.py`、`backend/app/llm.py` | 实际请求体捕获 |
| `backend/app/runtime.py` | 调用生命周期、快照落盘、普通完成 |
| `fronted/src/components/ModelCallContext.vue` | 输入详情和分页 |

`prompt/system.py`、`prompt/summary.py` 不允许占位符；`prompt/summary_prefix.py` 必须含 `$summary`，`prompt/tool_preference.py` 必须含 `$tools`。四份常量由 `prompts.py` 的 `PROMPTS` 映射汇总。字面量 `$` 写为 `$$`，模板渲染仅做字符串替换，不执行模板内容。`@` 工具偏好在 `prompt/tool_preference.py` 维护，具体工具的名称、描述和参数 Schema 在 `tool/calculator.py`、`tool/search.py`、`tool/todo.py` 维护。连接测试文字及界面文案保留在各自代码中。

## 结束逻辑

已移除 final_answer 工具、参数类型、注册和特殊批处理分支。返回工具调用时执行并记录，再请求模型；无调用时必须正常结束且有非空正文，再锁内检查取消及引导。有引导则继续；没有则完成当前 Run，lane 继续其他排队 Run。空白、截断、取消不伪报完成。历史中的旧 final_answer 记录保留展示，不重新执行。

对话响应在登记调用 ID、保存调用消息和执行工具之前统一校验结束原因：工具调用必须以 `tool_calls` 结束且实际包含调用；普通回答只接受 `stop` 或兼容值 `end_turn`。`length`、`content_filter`、`insufficient_system_resource`、`aborted` 以及未知／缺失结束原因均停止当前 Run，保留调用快照和已接收文本，不执行该批工具，不自动重试。供应商返回 `aborted` 记录为生成失败，不冒充用户取消。非流式传输也不再将缺失结束原因补为 `stop`。摘要分支继续使用自身的结束原因和内容完整性校验，失败时不提交新摘要。

本次只做离线模型、假传输和无服务组件测试，不代表真实供应商或浏览器联调已通过。

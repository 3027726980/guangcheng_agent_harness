# 接口、事件与数据边界

## 公共约定

- HTTP 前缀 `/api`，JSON 编码；自动接口文档 `/docs`。
- 演示身份 Header `X-Demo-User: A` 或 `B`，缺省 A。不是生产认证。
- 参数由 Pydantic 严格验证，未知字段拒绝。常规错误返回 `detail`，待办冲突附 `code`。
- Pydantic 和工具 Schema 在同一个参数定义上生成；业务归属／版本验证在服务执行阶段。

## 接口

| 方法 | 路径 | 关键输入／输出 |
| --- | --- | --- |
| GET | `/health` | Runtime、演示身份及 logging_error（无故障为 null） |
| GET | `/users` | A／B 演示用户 |
| GET | `/tools` | 注册工具的 name、description，供前端 @ 菜单使用；校验演示身份 |
| POST | `/clients` | 生成窗口客户端 ID |
| GET | `/events?client_id=…` | SSE；一个客户端一个连接，首先发送 ready |
| POST | `/clients/{id}/disconnect` | 显式断开对应客户端 |
| GET / POST | `/sessions` | 会话列表附 active_runs（仅任务 ID／状态）／以 title 创建会话 |
| GET | `/sessions/{id}` | 会话、消息、执行、摘要、最近事件 |
| GET | `/sessions/{id}/model-calls` | 可选 run_id、after（默认 0）、limit（1–100，默认 20）；返回 items 概要与 next_cursor |
| GET | `/sessions/{id}/model-calls/{call_id}` | 归属校验后返回完整脱敏输入、版本和结果；不存在／跨用户／跨会话为 404 |
| DELETE | `/sessions/{id}` | 按用户归属逻辑删除；有运行／排队任务时返回 409，共享待办保留 |
| POST | `/sessions/{id}/messages` | client_id、request_id、content、可选 tool_names；返回任务与队列状态 |
| POST | `/sessions/{id}/compact` | client_id、request_id；空闲会话创建独立压缩任务，返回普通任务状态；忙碌返回 409，支持原停止接口 |
| POST | `/runs/{id}/steering` | request_id、content、可选 tool_names；只接受运行中的任务 |
| POST | `/runs/{id}/steer-queued` | 将当前用户的该条排队消息转为同 Session 当前任务的引导；原子转换、重复请求幂等；无可引导任务时返回 409 并保留队列 |
| POST | `/runs/{id}/cancel` | 按明确任务 ID 停止 |
| GET | `/todos` | 当前用户未删除待办 |
| POST | `/todos` | tool/todo.py 中的 TodoArgs，写入需要 Idempotency-Key |
| GET / PUT | `/settings` | 全局 RuntimeSettings |
| GET / POST | `/models` | 掩码连接列表／保存并自动测试连接 |
| PUT / DELETE | `/models/{id}` | 修改并测试／删除未被选用的连接 |
| POST | `/models/{id}/test` | 重新测试连接和容量 |

模型配置可指定 `output_token_parameter` 为 `max_tokens` 或 `max_completion_tokens`；思考只提供 `thinking_enabled` 布尔开关，新连接默认关闭，不发送强度参数。旧记录的 `reasoning_effort` 仅用于恢复开关，不对外返回。后端不偷偷重发另一套参数，以免绕过预算或隐藏兼容错误。

`tool_names` 默认空列表，最多 16 项；后端校验注册名称并去重，未知名称入队前拒绝。它表示用户偏好，不是强制执行列表。所有工具继续提供给模型，`tool_choice=auto`；不要求按提及顺序或逐个使用，信息不足可先询问，也可直接回答或使用其他适用工具。实际参数仍由工具层严格验证。

偏好随请求和引导以消息外层 `tool_names` 元数据持久化；消息正式应用时一次性将偏好模板追加到 `message.content`，参与 token 预算和摘要压缩，后续 Context 构建直接复用已保存正文。`original_content` 保存用户原文供聊天界面展示，缺少该字段的历史消息回退到 `message.content`；`tool_preference_version` 保存该消息实际采用的偏好模板版本。修改模板只影响随后应用的新消息，不改写已有历史。排队转引导保留相同偏好，无提及的消息不额外注入提示；已有旧记录不补写偏好正文。

## 执行与消息

任务状态：`queued`、`running`、`cancelling`、`completed`、`cancelled`、`failed`、`interrupted`、`limited`。

停止原因单独记录，例如 `user_stop`、`client_disconnect`、`server_restart`。工具结果的 `ok` 只代表已确认操作结果；取消时工具可能已经成功，记录 `stop_requested` 解释两者并不矛盾。

排队转引导后，来源任务以 cancelled／converted_to_steering 记录，关联 steering_id 和 steering_run_id；引导记录保留 source_run_id。页面显示“已转为引导”，不作为取消错误提示；引导继续消耗当前任务预算。

消息保存 role/content、工具请求及 tool_call_id；应用元数据另存消息 ID、任务 ID、输入类别和时间。模型输入不重放残缺参数。修复未配对工具调用时，优先读取已提交操作证据，否则补中断结果。

展示思考保存在外层 `reasoning`，原生协议思考保存在 `message.reasoning_content` 并原样回传；展示文本可包含正文 think 标签提取的内容，不能替换新的原生协议字段。

## SSE 事件

普通事件包含：`id`、`user_id`、`session_id`、`run_id`、`type`、`timestamp`、`data`。

| 事件 | 数据 |
| --- | --- |
| `run.updated` | 任务状态、计数、设置快照和原因，不包含密钥 |
| `message.created` | 已持久化消息 |
| `model.started / delta / finished / failed / retry` | 调用 ID、用途、模型、内容增量、用量、重试原因和等待 |
| `model.context` | call_id、purpose；快照已保存，完整内容通过详情接口获取 |
| `logging.status` | 全局本地日志故障状态，前端顶部显示；SSE ready 同时携带 logging_error |
| `model.reasoning.delta` | call_id、text；独立思考增量，不混入回答正文 |
| `tool.started / finished` | 调用 ID、名称、参数、结果、错误、耗时 |
| `steering.updated` | pending / applied / unprocessed |
| `context.usage / compacting / compacted / compaction_failed` | 估算、容量来源、覆盖范围、摘要及失败状态 |
| `todo.changed` | 当前用户共享待办已变化，页面重新查询 |
| `session.created / models.changed / settings.changed` | 刷新对应数据 |
| `session.deleted` | 被删除的会话 ID；各窗口刷新列表，当前会话被删除时切换到其他会话或新建 |

前端保存最近 2000 条当前会话事件，详情接口最多返回最近 2000 条；数据库保留完整事件。SSE 实时连接不作为历史重放源，重连后从详情接口恢复状态。

页面链路按任务及调用 ID 聚合模型／工具的开始和结果，每页 8 个步骤，默认折叠原始记录；文本 delta 和 message.created 不单列步骤，对话区保留最终消息。缺少或未通过测试的模型、容量与输出预留冲突，会在提交入队前返回 409，不创建空任务。

会话列表的 active_runs 仅包含当前用户 queued／running／cancelling 任务。前端在筛选当前会话事件之前更新全列表活动状态；列表请求期间收到的任务事件优先于旧 HTTP 快照，避免已结束任务重新显示转圈。事件连接就绪后重新获取列表以恢复状态。

## 工具注册契约

已移除 `final_answer` 及其参数和注册项。模型返回正常结束、非空正文且无工具调用时，锁内检查引导和取消后完成。历史中的旧调用与结果只保留展示。

工具内部契约：`BaseTool` 是抽象基类，子类声明 `name`、`description`、`arguments`（Pydantic 模型）和 `execution_mode`（parallel／sequential），实现 `async execute(args, db, user_id, operation_id)`。基类 `schema()` 生成函数声明；`ToolRegistry.register()` 校验继承、异步方法、元数据及重名，`execute()` 校验参数后统一分发。Agent 和手动待办接口都通过注册表，HTTP 路径及响应格式不变。同步计算与样例检索封装在异步方法中，仍在当前线程执行，不代表自动进入线程池。

## SQLite

首版使用 `records` 存储按 kind、owner、parent 索引的业务记录，使用 `events` 存储有序执行事件。JSON payload 让初版结构保持小而可读；多类型复杂查询和正式迁移属于后续演进点。

写入由单进程异步锁协调，事务内同时保存待办变更与操作去重记录；不能把进程锁当作多实例分布式锁。默认数据库为 `backend/.data/harness.db`，可用 `HARNESS_DB` 环境变量覆盖。

## Run 字段契约（2026-10-21）

后端定义：[app/run.py](../backend/app/run.py)；前端公开类型：[types/harness.ts](../fronted/src/types/harness.ts)。任务接口与 run.updated 保持原有 JSON 字段结构。

| 分组 | 字段 |
| --- | --- |
| 身份与请求 | id、session_id、user_id、client_id、content、purpose、tool_names |
| 状态与预算 | status、reason、model_calls、tool_calls |
| 生命周期 | created_at、started_at、ended_at，Unix 秒 |
| 配置快照 | settings、model_snapshot（id、model、context_capacity、capacity_source） |
| 可选扩展 | compaction_result、compaction_message、steering_id、steering_run_id |
| 仅内存，不序列化 | profile、summary_profile、partial、partial_reasoning |

status 仅允许 queued、running、cancelling、completed、cancelled、failed、interrupted、limited；purpose 为 chat 或 context_compaction。可选字段在尚未赋值时可省略，reason 可为 null。settings 不包含模型连接密钥。

## 调用快照与可见上下文（2026-10-22）

`records.kind=model_call`：id 为 `model-call:<call_id>`，包含 user_id、session_id、run_id、purpose（answer／summary）、attempt、timestamp、sequence、model、status、request、prompt_versions、context_version，以及完成后的 response／error／partial_response、ended_at。request 是实际 HTTP JSON 请求体，SDK extra_body 已合并，未设置的参数不补造；API Key 和认证头不属于该请求体。状态为 sending／completed／failed／cancelled。正文、工具结果和协议思考不截断，但凭据脱敏。

列表按 sequence 升序，after 是最后一条 sequence；有下一页时 next_cursor 为本页最后序号，结束为 null。列表不返回 request、response 或 partial_response，详情按需读取。列表不依赖 events 的最近 2000 条窗口。旧调用没有该记录，列表为空或不包含旧条目，不重建过去输入。

`records.kind=context`：id 为 `context:<session_id>`，保存 version、summary 节点、有序 message_ids。消息与清单同事务保存；摘要与清单同事务替换。系统提示、工具偏好及兼容协议字段只在独立输入副本上动态注入。完整聊天历史继续由 message 记录提供。

本地目录和失败策略见 [日志与增量上下文](logs_context.md)。

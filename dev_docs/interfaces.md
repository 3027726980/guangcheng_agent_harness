# 接口、事件与数据边界

## 公共约定

- HTTP 前缀 `/api`，JSON 编码；自动接口文档 `/docs`。
- 演示身份 Header `X-Demo-User: A` 或 `B`，缺省 A。不是生产认证。
- 参数由 Pydantic 严格验证，未知字段拒绝。常规错误返回 `detail`，待办冲突附 `code`。
- Pydantic 和工具 Schema 在同一个参数定义上生成；业务归属／版本验证在服务执行阶段。

## 接口

| 方法 | 路径 | 关键输入／输出 |
| --- | --- | --- |
| GET | `/health` | Runtime 与演示身份标记 |
| GET | `/users` | A／B 演示用户 |
| GET | `/tools` | 注册工具的 name、description，供前端 @ 菜单使用；校验演示身份 |
| POST | `/clients` | 生成窗口客户端 ID |
| GET | `/events?client_id=…` | SSE；一个客户端一个连接，首先发送 ready |
| POST | `/clients/{id}/disconnect` | 显式断开对应客户端 |
| GET / POST | `/sessions` | 会话列表附 active_runs（仅任务 ID／状态）／以 title 创建会话 |
| GET | `/sessions/{id}` | 会话、消息、执行、摘要、最近事件 |
| DELETE | `/sessions/{id}` | 按用户归属逻辑删除；有运行／排队任务时返回 409，共享待办保留 |
| POST | `/sessions/{id}/messages` | client_id、request_id、content、可选 tool_names；返回任务与队列状态 |
| POST | `/sessions/{id}/compact` | client_id、request_id；空闲会话创建独立压缩任务，返回普通任务状态；忙碌返回 409，支持原停止接口 |
| POST | `/runs/{id}/steering` | request_id、content、可选 tool_names；只接受运行中的任务 |
| POST | `/runs/{id}/steer-queued` | 将当前用户的该条排队消息转为同 Session 当前任务的引导；原子转换、重复请求幂等；无可引导任务时返回 409 并保留队列 |
| POST | `/runs/{id}/cancel` | 按明确任务 ID 停止 |
| GET | `/todos` | 当前用户未删除待办 |
| POST | `/todos` | TodoArgs，写入需要 Idempotency-Key |
| GET / PUT | `/settings` | 全局 RuntimeSettings |
| GET / POST | `/models` | 掩码连接列表／保存并自动测试连接 |
| PUT / DELETE | `/models/{id}` | 修改并测试／删除未被选用的连接 |
| POST | `/models/{id}/test` | 重新测试连接和容量 |

模型配置可指定 `output_token_parameter` 为 `max_tokens` 或 `max_completion_tokens`；思考只提供 `thinking_enabled` 布尔开关，新连接默认关闭，不发送强度参数。旧记录的 `reasoning_effort` 仅用于恢复开关，不对外返回。后端不偷偷重发另一套参数，以免绕过预算或隐藏兼容错误。

`tool_names` 默认空列表，最多 16 项；后端校验注册名称并去重，未知名称入队前拒绝。它表示用户偏好，不是强制执行列表。所有工具继续提供给模型，`tool_choice=auto`；不要求按提及顺序或逐个使用，信息不足可先询问，也可直接回答或使用其他适用工具。实际参数仍由工具层严格验证。

偏好随请求和引导以消息外层 `tool_names` 元数据持久化；Context 向对应用户消息副本追加提示，参与 token 预算和摘要压缩，数据库中的原正文不变。排队转引导保留相同偏好，无提及的消息不额外注入提示。

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

工具内部契约：`BaseTool` 是抽象基类，子类声明 `name`、`description`、`arguments`（Pydantic 模型）和 `execution_mode`（parallel／sequential），实现 `async execute(args, db, user_id, operation_id)`。基类 `schema()` 生成函数声明；`ToolRegistry.register()` 校验继承、异步方法、元数据及重名，`execute()` 校验参数后统一分发。Agent 和手动待办接口都通过注册表，HTTP 路径及响应格式不变。同步计算与样例检索封装在异步方法中，仍在当前线程执行，不代表自动进入线程池。

## SQLite

首版使用 `records` 存储按 kind、owner、parent 索引的业务记录，使用 `events` 存储有序执行事件。JSON payload 让初版结构保持小而可读；多类型复杂查询和正式迁移属于后续演进点。

写入由单进程异步锁协调，事务内同时保存待办变更与操作去重记录；不能把进程锁当作多实例分布式锁。默认数据库为 `backend/.data/harness.db`，可用 `HARNESS_DB` 环境变量覆盖。

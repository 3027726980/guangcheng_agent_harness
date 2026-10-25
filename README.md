# Agent Harness

从零实现的最小 Agent：原生 Function Calling、自写循环、Pydantic 工具契约、独立 Session、用户共享待办、排队／引导／取消、Context 压缩和执行 Trace。

核心流程没有使用 LangChain、LangGraph、OpenHands 或托管 Agent 服务。前端基于 [PinLayout](https://github.com/3027726980/PinLayout)，保留原 MIT 声明。

本文介绍运行方式、界面操作、系统设计和 Memory 机制。文档结构更新于 2026-10-25；历史验证结果以对应记录为准，本次文档整理不代表重新执行测试。

## 阅读导航

- [快速运行](#快速运行)：安装依赖、启动服务与启动前检查。
- [界面使用](#界面使用)：模型配置、工具提及、思考展示、Context 与会话管理。
- [项目目录与代码入口](#项目目录与代码入口)：定位后端、前端与工具实现。
- [系统设计](#系统设计)：执行循环、排队、引导、停止与预算。
- [Memory 的召回时机与放置方式](#memory-的召回时机与放置方式)：历史恢复、模型输入顺序与摘要压缩。
- [本地日志、提示词和调用输入](#本地日志提示词和调用输入)：排查调用、查看输入与修改提示词。
- [验证](#验证)：离线测试命令、覆盖率与真实模型验收。
- [版本管理](#版本管理)与[来源与扩展](#来源与扩展)：仓库分支、许可与后续方向。

## 快速运行

需要 Python 3.12、uv、Node.js 22.6 或以上，以及支持 Chat Completions、Function Calling、流式输出的模型服务。

### Windows 快速启动

参考 Pin 的 `backend/scripts-dev/quick-start`，本项目提供以下双击入口：

- [main.bat](backend/scripts-dev/quick-start/main.bat)：同时打开后端和前端 PowerShell 窗口。
- [backend.bat](backend/scripts-dev/quick-start/backend.bat)：只启动后端。
- [frontend.bat](backend/scripts-dev/quick-start/frontend.bat)：只启动前端（项目目录仍为 `fronted`）。
- [restart.bat](backend/scripts-dev/quick-start/restart.bat)：检查依赖与进程归属，停止本项目旧服务并重新打开前后端窗口；会中断运行及排队任务。

首次使用先按[手动安装与启动](#手动安装与启动)安装依赖，之后可使用双击入口。

- **依赖检查**：脚本自动定位项目根目录，检查虚拟环境、依赖和 Node 版本，不自动安装依赖。
- **端口检查**：普通启动入口遇到 8000／5173 端口占用时会报错。
- **重启检查**：只停止已核实属于本项目的监听进程；无法核实或属于其他程序时拒绝执行，两个服务都核实后才开始停止。

#### 只检查，不启动

也可以在 PowerShell 中仅做启动前检查，不启动服务：

```powershell
& 'D:\MyProject\guangcheng_agent_harness\backend\scripts-dev\quick-start\main.bat' --check
```

四个入口均支持 `--check`，不会停止或启动服务；`restart.bat --check` 会列出待停止的本项目监听进程。底层逻辑为同目录 `start.ps1`，可直接使用 `-Target All|Backend|Frontend -CheckOnly`。

#### 单独重启与停止

在项目根目录单独重启后端：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File backend/scripts-dev/quick-start/start.ps1 -Target Backend -Restart
```

单独重启前端时将 `-Target Backend` 改为 `-Target Frontend`。

实际启动后，等待两个窗口显示就绪信息，再访问 [本地界面](http://127.0.0.1:5173)。停止时在各服务窗口按 `Ctrl+C`。脚本本身不调用模型，保存模型配置／发起聊天时才会调用。

### 手动安装与启动

后端，在 PowerShell 中运行：

```powershell
Set-Location 'D:\MyProject\guangcheng_agent_harness\backend'
uv sync --group dev
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

另开一个 PowerShell 运行前端：

```powershell
Set-Location 'D:\MyProject\guangcheng_agent_harness\fronted'
npm ci
npm run dev
```

打开 [本地界面](http://127.0.0.1:5173)。关闭服务使用 `Ctrl+C`。后端 OpenAPI 位于 [接口文档](http://127.0.0.1:8000/docs)。

## 界面使用

### 首次配置模型

1. 进入“全局设置”，填写连接名称、Base URL、API Key 和模型 ID。
2. 保存会真实调用模型测试连接，并尝试读取 Context；无法读取时使用默认 256K，页面显示来源。
3. 在“对话模型”中选中连接，保存全局运行设置。摘要模型留空复用对话模型，也可独立配置。
4. 回到对话页，发送任务，例如“计算 128 乘 36，把结果记入待办”。

#### 输出参数与思考开关

输出限制参数默认 `max_tokens`；需要时选择 `max_completion_tokens`。模型连接只允许设置是否开启思考模式，不提供思考强度选项，也不发送思考强度参数；新连接默认关闭。请自行查阅所用模型的 API 开发文档，确认该模型是否支持思考模式及其调用方式。连接成功只验证基本访问，工具能力仍需用实际任务验收。

思考开关通过兼容接口的 `thinking.type` 传递。官方 DeepSeek、智谱接口在关闭时也明确发送 `disabled`；未知的普通兼容接口关闭时不附加专有参数，以保留基本聊天兼容性，其默认思考行为仍以模型文档为准。旧记录中的思考强度仅用于恢复开启或关闭状态，不再向界面暴露或发送给模型，重新保存或测试连接后使用新的布尔开关字段。

### 使用 @ 提及工具

输入框中键入 `@` 可选择当前后端注册的 `calculator`、`search`、`todo`，支持按名称或中文描述筛选、上下键和 Enter 选择。例如：

- `@calculator 计算 128*36`
- `@calculator @todo 计算 128*36 并记入待办`

工具提及的行为如下：

- **发送时生效**：选择不会立即发送；发送后将去重的工具名称作为当前消息的偏好加入模型上下文，界面保留原文。删除对应提及即可取消偏好。
- **由模型决定调用**：提示模型优先考虑所选工具，不强制调用、固定顺序或逐个执行；信息或必要参数不足时先询问。模型也可直接回答或使用其他适用工具；所有工具仍可用，`tool_choice` 使用 `auto`，包括 DeepSeek 思考模式。
- **以后端结果为准**：参数经后端严格校验，写入成功只能依据工具结果。
- **引导沿用相同规则**：运行中引导和排队消息转引导保留相同语义，偏好提示参与上下文预算和摘要压缩。

### 查看思考过程

模型返回的 `reasoning_content`、文本形式的 `reasoning`，以及正文中的 `<think>…</think>` 会与回答分开解析，包括流式分片标签。聊天消息上方的“思考过程”可折叠查看，正常完成或中断时已接收的思考随消息保存，刷新后仍可查看。只有供应商实际返回的文本才会展示，不会根据最终答案补造思考；未返回思考时不显示该区域。

#### 思考字段的协议兼容

原生 `reasoning_content` 还会单独保存在协议消息中，工具追问及之后的用户追问均原样携带，避免 DeepSeek 携带 `tools` 时因缺少历史思考返回 400。它与包含标签思考的展示文本分开存储。

旧版本记录在回放时利用已保存的思考补字段，不改写旧历史；原来没有保存的思考无法还原，不会补造。相关限制见 [DeepSeek 工具选择参数](https://api-docs.deepseek.com/api/create-chat-completion/) 与 [思考模式](https://api-docs.deepseek.com/zh-cn/guides/thinking_mode/)。

### 发送条件与连接状态

缺少对话／摘要模型、连接测试未通过、配置读取失败或模型容量不足时，对话页会提示并提供设置入口，发送按钮和 Enter 均不可提交；后端在任务入队前再次检查。对话和摘要均不发送固定输出上限，摘要不设正文长度目标，由模型及供应商决定长度；Context 预留自动管理，无需填写输出 token 数。

右上角只有在后端实时连接正常且模型配置就绪、连接测试通过时显示“后端已链接”。悬浮可分别查看后端与模型的勾叉状态及原因；模型状态使用最近一次保存／测试结果，不会因悬浮额外调用模型。

### Context 用量与手动压缩

发送按钮旁的圆环显示估算 Context 使用率，点击可查看容量、来源、历史摘要以及“立即压缩”按钮；尚未估算时显示“—”。手动压缩仅在会话空闲时可发起，会调用摘要模型，保留最近一轮及完整原始历史，可使用停止按钮取消；失败或无压缩收益时不覆盖原摘要。

界面容量与用量采用千进制单位：`k = 1,000 tokens`、`m = 1,000,000 tokens`，最多一位小数；例如默认容量 262144 显示为 `262.1k`。底层容量判断和原始事件仍使用完整数值。

### 工具结果与完整链路

连续工具调用在消息流原位合并为一个折叠入口，展开后可单独查看每次调用与结果，文字消息保留原位置。同批并发调用按请求顺序展示，不代表完成先后。完整链路按任务选择、按步骤聚合，每页 8 个步骤，展开后查看原始事件。

### 删除会话

会话列表支持确认后删除。删除使用逻辑标记：隐藏会话并拒绝继续访问，保留底层执行证据；共享待办保留。仍有运行／排队任务时不能删除，先停止任务、取消排队消息。其他窗口收到删除事件后同步更新。

### 本地数据与访问范围

模型 Key 在本地 SQLite 保存，接口只回读是否已配置，不回传原值；编辑时留空表示保留。数据库与运行数据均被 Git 忽略。演示用户 A／B 不是登录认证机制，首版默认仅绑定本机地址。

## 项目目录与代码入口

```text
backend/app/       自写 Runtime、模型适配、Context、工具、SQLite、API
backend/app/prompt/ 按用途拆分的 Python 提示词：system、summary、summary_prefix、tool_preference
logs/             北京时间日期分目录的本地诊断与模型调用快照（忽略）
backend/tests/     可重复离线测试，真实 SDK 的假 HTTP 传输测试
fronted/           Vue + TypeScript + Naive UI
dev_docs/          规划、设计、接口、十道架构题研究和验证记录
```

### 后端入口

后端入口为 `backend/app/main.py`，执行主链为 `backend/app/runtime.py`。

### 工具定义与注册

新增工具按以下方式接入：

1. 继承 `backend/app/tool/base.py` 的 `BaseTool`，声明名称、描述、Pydantic 参数模型和执行策略。
2. 实现异步 `execute(args, db, user_id, operation_id)`。
3. 通过 `backend/app/tool/registry.py` 中的 `ToolRegistry.register()` 注册。

基类提供统一 Schema；注册表检查工具契约、严格校验参数并调用实例。`calculator.py`、`search.py`、`todo.py` 分别包含对应参数模型与 `CalculatorTool`、`SearchTool`、`TodoTool` 实现。Agent 调用与手动待办接口都经 `ToolRegistry.execute()` 执行。

## 系统设计

采用 Vue 前端、FastAPI 接口、自写 Runtime 和本地 SQLite 的单进程方案。OpenAI SDK 只负责兼容接口传输；工具选择由模型根据 Schema 决定，循环、调度、预算、取消、持久化和恢复均由项目代码实现。

```text
Vue 对话页／设置页／待办面板
        │ HTTP 请求                  ↑ SSE 增量与状态事件
        ▼                            │
FastAPI 接口：用户归属、参数校验、消息提交、历史和调用详情查询
        │
        ▼
Runtime：Session lane → Run → Context → 模型调用 → 工具执行 → 下一轮
        │                      │             │
        │                 OpenAI SDK     ToolRegistry
        │                      │         calculator / search / todo
        ▼                      ▼
SQLite：消息、摘要、上下文清单、Run、待办、事件、调用快照
        └─ 本地 JSONL 日志：诊断与调用证据
```

| 模块 | 主要职责与代码入口 |
| --- | --- |
| 接口与页面 | `backend/app/main.py` 提供 HTTP／SSE；`fronted/src/views/ChatView.vue` 展示消息、队列、引导和停止入口 |
| 执行与调度 | `backend/app/runtime.py` 管理 Session lane 和 Agent Loop；`backend/app/run.py` 定义任务状态、预算计数和配置快照 |
| 模型适配 | `backend/app/llm.py` 发送请求、解析流式正文／思考／工具参数并分类错误；`response_parser.py` 处理正文中的思考标签 |
| 工具契约 | `backend/app/tool/` 使用 BaseTool、Pydantic 参数模型和注册表统一生成 Schema、校验与执行；写操作另做归属、事务、幂等和版本检查 |
| 上下文与记忆 | `backend/app/context.py` 组装协议输入和摘要压缩；`session_context.py` 维护数据库清单及内存可见视图 |
| 数据与诊断 | `backend/app/storage.py` 保存业务记录和事件；`diagnostics.py` 写本地日志；`request_capture.py` 捕获发送前的实际请求体 |

### 数据对象与隔离范围

| 对象 | 含义 |
| --- | --- |
| User | 数据归属 |
| Session | 一条独立对话 |
| Run | 一次完整任务执行 |
| Message | 正式交互记录 |
| Event | 执行过程记录 |

一个 Run 可以包含多次模型及工具调用；`asyncio.Task` 负责执行协程，Run 模型负责记录状态，两者分开管理。SQLite 是恢复事实来源，本地日志用于排查，不用于重建聊天记忆。

首版使用统一 Agent，避免为三种工具增加意图路由和子 Agent 调度。相同 Session 串行、不同 Session 并行；待办按用户共享，聊天上下文按 Session 隔离。演示使用预置 A／B 用户，无登录认证，SQLite 与进程内锁面向本地单进程运行，多实例部署需要另行设计。

### 执行模型

模型返回工具调用时，执行并保存配对结果，继续下一轮。没有工具调用时，必须有非空正文和正常结束标记；完成前锁内检查取消及待生效引导，有引导就应用后继续，否则完成当前 Run，由 lane 领取后续排队 Run。已移除 `final_answer` 工具及特殊分支，旧历史中的调用与结果继续保留展示。

```text
消息入队 → 固定配置快照 → 恢复会话／检查 Context → 调用模型
                                              ├─ 文本 → 检查引导 → 结束
                                              └─ 工具 → 校验／执行／保存结果 → 再调用模型
```

- 同一 Session 顺序执行，不同 Session 可以并行；同用户可打开多个窗口独立对话。
- 左侧会话列表中，有执行／排队／停止中任务的会话显示转圈标识，悬浮查看状态；切换会话持续更新，刷新／重连从后端恢复，全部任务结束后消失。
- `calculator` 和模拟 `search` 可并行，默认上限 4；同批含 `todo` 或未知工具时整批串行。
- 参数必须完整，结果依赖通过下一次模型调用处理，不实现自动依赖图。
- `search` 只匹配代码中的固定样例资料，结果始终带 Mock 标记，不访问真实搜索引擎。
- `todo` 按用户共享，支持增查改、完成、逻辑删除。前端面板和 Agent 共用事务服务，版本检查防止跨窗口静默覆盖。
- 已执行成功的工具结果才是完成证据；模型口头说“已完成”不构成写入证据。

### 排队、引导、停止

#### 排队消息转为引导

普通发送默认排队。运行中发送的消息，在该条排队消息旁点击“引导”，可将它转为当前任务的补充；输入区不再单列引导按钮。转换会原子地移出独立队列并保存引导，重复点击不会重复执行。补充在下一次模型调用前生效，不中断当前步骤；最终回答期间收到引导也会继续处理，沿用原预算。当前任务已结束时拒绝转换并保留原排队消息。

#### 手动停止

手动停止会保留部分输出和操作证据，记录“已被用户手动停止”，清理当前执行后自动开始下一条排队消息。已提交的待办不会被撤销。

#### 断线与重连

断线取消该客户端的当前执行和未执行队列。重连只恢复历史，不自动重新发送。切换会话不关闭连接；其他窗口不受影响。后端只能在检测到断线时执行取消，远端模型停止计算不由本地保证。

#### 服务重启后的恢复

服务重启会把遗留任务标记为中断、队列标记取消，恢复工具结果的配对信息，不自动重放工具。继续任务请发送新消息，获得新预算并利用已有历史。

### 预算与重试

#### 默认预算

| 项目 | 默认值 |
| --- | --- |
| 模型调用次数 | 20 次 |
| 工具调用次数 | 40 次 |
| 任务总时长 | 300 秒 |
| 单次模型超时 | 60 秒 |
| 单次工具超时 | 10 秒 |
| 失败后重试次数 | 3 次 |
| 重试间隔 | 30 秒 |

全部可在全局设置中修改，对后续开始的任务生效。

#### 重试条件与提示

重试、摘要计入模型调用次数，等待计入总时长；预算不足会提前结束。仅暂时性网络、限流和上游故障重试，遵循更长的 `Retry-After`。认证、请求错误、Context 超限、不确定写入及已展示部分回答的流失败不透明重试。

等待重试时，页面和链路显示错误原因、等待秒数及重试次数。例如 HTTP 429 会被当作可重试的限流响应；它也可能来自额度限制，具体原因需结合供应商信息判断。全局设置可修改间隔，重试次数设为 0 可关闭自动重试。

## Memory 的召回时机与放置方式

本项目的聊天记忆是 Session 级短期记忆，不自动跨会话召回聊天。用户待办属于共享业务数据，由工具按需读取，不等于跨会话聊天记忆。

### 召回时机

这里的“召回”指恢复当前会话的历史与摘要，没有向量检索、相似度检索或跨会话长期记忆库。

| 时机 | 读取与使用方式 |
| --- | --- |
| 打开已有会话或首次为它构建输入 | `ContextState` 懒加载可见清单；有清单时按 `message_ids` 恢复正文，没有清单的旧会话读取完整历史与摘要，并按 `covered` 排除已摘要消息 |
| 后续用户追问、工具执行后继续循环 | 每次模型调用前复制当前 SessionContext，加入已正式保存的新消息与工具结果；已有缓存时不全量查询历史 |
| 运行中引导生效 | 在下一次模型调用前保存并加入当前会话，沿用当前 Run 的预算；排队消息在被 lane 领取或转为引导之前不提前注入 |
| Context 达到阈值或用户点击“立即压缩” | 调用摘要模型归纳可压缩旧前缀，后续调用使用新摘要和保留后缀；手动压缩要求会话空闲 |
| 进程重启后再次访问会话 | 从 SQLite 恢复清单、摘要和可见消息；遗留 Run 中断、队列取消，不自动续跑或重放工具 |
| 需要当前待办状态 | 模型调用 `todo` 查询用户共享数据，工具结果随后进入当前会话；不会把全部待办自动塞进每次请求 |

### 存储位置与模型输入位置

默认数据库为 `backend/.data/harness.db`，可通过环境变量 `HARNESS_DB` 指定其他路径。数据放置如下：

| 数据 | 存储方式 | 是否进入模型输入 |
| --- | --- | --- |
| 原始消息和工具结果 | SQLite `records` 表中的 `message` 记录，按 Session 归属 | 仅当前可见消息按原顺序进入，压缩覆盖部分不重复发送 |
| 历史摘要 | `summary:<session_id>` 摘要记录，含正文与 `covered` 消息 ID | 包装为“历史资料摘要”的 `user` 消息，位于系统提示之后、近期消息之前 |
| 可见清单 | `context:<session_id>` 保存版本、摘要、`message_ids` 和工具调用 ID 集合；进程内 SessionContext 缓存可见正文 | 清单、版本及 ID 集合是管理元数据，不作为聊天正文发送 |
| 用户待办 | SQLite 用户归属的业务记录，跨该用户的 Session 共享 | 按需读取后以 `tool` 结果进入，不以旧摘要替代数据库最新值 |
| Trace 与调用快照 | SQLite 事件／调用记录及 `logs/YYYY-MM-DD/` | 用于查看与诊断，不自动注入聊天 |

### 模型输入顺序

实际请求中的 `messages` 顺序为：

```text
system：当前系统提示
user：历史资料摘要（存在时；明确不是新指令）
未覆盖的近期消息：user → assistant → tool → assistant …
当前已应用的请求／引导／工具结果（按其在会话中的实际顺序）
```

工具 Schema 通过请求顶层的 `tools` 字段发送，不是额外的历史消息。`@` 偏好在用户请求或引导正式应用时渲染进对应消息正文，界面原文另存为 `original_content`。供应商返回的原生 `reasoning_content` 与展示思考分开保存，工具追问及后续追问按协议回传；不依据答案补造思考。系统提示每次新请求从模板读取，不保存在 SessionContext 中。

### 压缩与一致性保护

1. 旧会话首次使用时从 SQLite 历史及 covered 初始化可见清单；随后维护 SessionContext。重启只按清单加载可见消息，正常调用从内存复制输入，不再全量读取历史。
2. 输入按上述顺序组装，系统提示、摘要、消息和请求顶层的工具定义都参与容量估算。
3. 已知模型尝试匹配 tokenizer，未知兼容模型使用保守 UTF-8 字节估算；输入计数含消息和 Schema 开销，页面明确是估算。
4. 可用输入空间扣除自动输出预留 `max(64, 容量的10%)`，以及 `max(256, 容量的5%)` 估算余量。预留仅影响压缩判断，对话请求不传固定输出上限；供应商默认限制仍然生效，预留也不能保证任意长回答都能容纳。
5. 达到可用空间 80% 触发摘要，目标约 50%；保护当前用户请求与引导、最近完整工具交互。
6. 只选择受保护节点之前的连续旧前缀，按摘要模型容量分批。摘要和可见清单同事务提交，再替换内存对象；范围外节点及顺序保持不变。并发追加导致版本变化时丢弃过时摘要并重新构建。
7. 摘要失败／停止不覆盖旧摘要；原输入超限时保留历史并停止，必要输入过大时也不强行删除。

完整历史不随压缩删除。后续读取待办时以数据库最新状态为准，旧摘要里的状态不是当前事实。Trace 可查看每次容量估算、压缩前后用量和摘要。

## 本地日志、提示词和调用输入

### 日志位置与记录范围

日志默认写入项目根目录 `logs/YYYY-MM-DD/`，按北京时间分目录：

| 文件 | 内容 |
| --- | --- |
| `app.jsonl` | 应用诊断日志 |
| `http.jsonl` | HTTP 方法、路径、状态、耗时和请求标识，不采集正文或认证头 |
| `sessions/<session_id>.jsonl` | 会话事件与模型调用快照 |

模型请求的开始与结束快照以 `model.snapshot` 追加到对应会话文件，通过 `data.call_id` 关联，不再为每次调用创建独立 JSON 文件。

可通过 PowerShell 修改日志根目录：

```powershell
$env:HARNESS_LOG_DIR = 'D:\HarnessLogs'
```

完整业务事件仍存 SQLite；文件保留相同事件 ID，调用快照不占用业务事件 ID，不自动删除，也不补造旧数据。

### 查看模型调用输入

在“完整链路”选择 Run，查看“模型调用输入”：清单独立分页，展开后按顺序读取当时的系统提示、摘要、消息、工具结果及思考字段，工具定义和参数单独折叠；支持原始 JSON 和复制。每次重试有独立调用 ID，保留相同输入版本。旧调用显示未记录快照。输入在 SDK 发送前保存到数据库及文件；保存失败会阻止该次发送，文件写入故障在页面顶部、健康接口及 stderr 明确显示。

### 提示词文件与修改规则

四类模型提示词统一放在 `backend/app/prompt/`：

| 文件 | 用途 |
| --- | --- |
| `system.py` | Agent 系统提示 |
| `summary.py` | 历史摘要生成提示 |
| `summary_prefix.py` | 历史摘要在模型输入中的包装提示 |
| `tool_preference.py` | 用户通过 `@` 提及工具时的偏好提示 |

`backend/app/prompts.py` 负责汇总、校验、渲染和版本记录。

- **修改生效**：需重启后端或由开发服务器重载模块。每次新请求构建模板快照和内容哈希，同一请求的重试保留原版本。
- **占位符要求**：`summary_prefix` 必须保留 `$summary`，`tool_preference` 必须保留 `$tools`；字面量美元符号用 `$$`。
- **校验失败**：缺少定义、空内容、非法或多余占位符会报错。

#### 工具描述与偏好的生效范围

工具自身的模型描述与参数说明分别位于 `backend/app/tool/calculator.py`、`search.py`、`todo.py`，由 `BaseTool.schema()` 转成 Function Calling Schema；连接测试文字及界面文案仍在各自代码中。

工具偏好在请求或引导正式应用时仅渲染一次，随模型消息正文保存；后续上下文构建直接复用，不重复加工历史。聊天界面通过 `original_content` 展示用户原文。修改偏好模板只影响新应用的消息，已有旧记录不补写。

结构及接口详见 [日志与增量上下文](dev_docs/logs_context.md)。

## 验证

### 离线测试与构建

后端测试按 [单元、集成与真实模型人工验收](backend/tests/README.md) 分类。日常 pytest 只运行离线测试；题目对应关系见 [需求映射](dev_docs/requirements.md)。

```powershell
Set-Location 'D:\MyProject\guangcheng_agent_harness\backend'
uv run pytest -q
uv run pytest tests/unit -q
uv run pytest tests/integration -q
uv run pytest -q --cov=app --cov-branch --cov-report=term-missing --cov-report=html --cov-report=xml
uv run ruff check app tests
uv run ruff format --check app tests

Set-Location 'D:\MyProject\guangcheng_agent_harness\fronted'
npm test
npm run build
```

综合覆盖率 HTML 位于 `backend/test-results/coverage/html/index.html`，XML 位于同级 `coverage.xml`。

### 真实模型与页面验收

真实模型需要在页面配置自己的连接。离线假模型只由测试显式注入，生产界面不会自动用假模型替代失败的服务。

六个核心场景见 [真实模型人工验收](backend/tests/agent_acceptance/README.md)，结果尚待执行者填写。

真实供应商的模型行为和真实页面联调不由离线测试代替。

### 相关文档

| 文档 | 用途 |
| --- | --- |
| [逐项验收清单](dev_docs/manual_test_checklist.md) | 按功能进行人工验收 |
| [验证记录](dev_docs/verification.md) | 查看已记录的验证结果及边界 |
| [接口与事件](dev_docs/interfaces.md) | 查询 HTTP 与事件协议 |
| [十道架构题备选研究](dev_docs/architecture_study.md) | 阅读架构问题分析 |
| [开发路线](dev_docs/开发路线-2026-10-20.md) | 查看阶段规划 |

## 版本管理

近期问题、原因、修复提交和验证边界汇总见 [Bug 修复与体验改进记录](dev_docs/bugfix_log.md)。

`main` 保留原题与规划基线，`dev/runtime` 保存完整开发实现；每批验证后提交。

GitHub 仓库为 [guangcheng_agent_harness](https://github.com/3027726980/guangcheng_agent_harness)，查看代码请使用 [dev/runtime 分支](https://github.com/3027726980/guangcheng_agent_harness/tree/dev/runtime)。

推送须由用户明确授权，不自动合并 main 或强推；本地／远端状态以 `git status`、`git log --all --oneline` 和 `git ls-remote --heads origin` 为准。

## 来源与扩展

PinLayout 采用 MIT 许可，原声明保存在 `fronted/LICENSE`。后续扩展 Jev 前置决策、真实搜索、多模态和必要时的 Decisions API，均不改变首版统一 Agent 的可独立运行能力。

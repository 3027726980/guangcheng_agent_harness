# Agent Harness

从零实现的最小 Agent：原生 Function Calling、自写循环、Pydantic 工具契约、独立 Session、用户共享待办、排队／引导／取消、Context 压缩和执行 Trace。

核心流程没有使用 LangChain、LangGraph、OpenHands 或托管 Agent 服务。前端基于 [PinLayout](https://github.com/3027726980/PinLayout)，保留原 MIT 声明。

## 快速运行

需要 Python 3.12、uv、Node.js 22.6 或以上，以及支持 Chat Completions、Function Calling、流式输出的模型服务。

### Windows 快速启动

参考 Pin 的 `backend/scripts-dev/quick-start`，本项目提供以下双击入口：

- [main.bat](backend/scripts-dev/quick-start/main.bat)：同时打开后端和前端 PowerShell 窗口。
- [backend.bat](backend/scripts-dev/quick-start/backend.bat)：只启动后端。
- [frontend.bat](backend/scripts-dev/quick-start/frontend.bat)：只启动前端（项目目录仍为 `fronted`）。
- [restart.bat](backend/scripts-dev/quick-start/restart.bat)：检查依赖与进程归属，停止本项目旧服务并重新打开前后端窗口；会中断运行及排队任务。

首次使用先按下方命令安装依赖，之后双击入口即可。脚本自动定位项目根目录，检查虚拟环境、依赖、Node 版本和端口，不自动安装依赖。普通启动入口遇到占用的 8000／5173 端口时会明确报错；重启入口只停止已核实属于本项目的监听进程，无法核实或属于其他程序时拒绝执行，两个服务都核实后才开始停止。

也可以在 PowerShell 中仅做启动前检查，不启动服务：

```powershell
& 'D:\MyProject\guangcheng_agent_harness\backend\scripts-dev\quick-start\main.bat' --check
```

四个入口均支持 `--check`，不会停止或启动服务；`restart.bat --check` 会列出待停止的本项目监听进程。底层逻辑为同目录 `start.ps1`，可直接使用 `-Target All|Backend|Frontend -CheckOnly`。单独重启后端可运行 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File backend/scripts-dev/quick-start/start.ps1 -Target Backend -Restart`；前端将 Target 改为 Frontend。实际启动后，等待两个窗口显示就绪信息，访问 `http://127.0.0.1:5173`。停止时在各服务窗口按 `Ctrl+C`。脚本本身不调用模型，保存模型配置／发起聊天时才会调用。

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

1. 进入“全局设置”，填写连接名称、Base URL、API Key 和模型 ID。
2. 保存会真实调用模型测试连接，并尝试读取 Context；无法读取时使用默认 256K，页面显示来源。
3. 在“对话模型”中选中连接，保存全局运行设置。摘要模型留空复用对话模型，也可独立配置。
4. 回到对话页，发送任务，例如“计算 128 乘 36，把结果记入待办”。

输出限制参数默认 `max_tokens`；需要时选择 `max_completion_tokens`。模型连接只允许设置是否开启思考模式，不提供思考强度选项，也不发送思考强度参数；新连接默认关闭。请自行查阅所用模型的 API 开发文档，确认该模型是否支持思考模式及其调用方式。连接成功只验证基本访问，工具能力仍需用实际任务验收。

思考开关通过兼容接口的 `thinking.type` 传递。官方 DeepSeek、智谱接口在关闭时也明确发送 `disabled`；未知的普通兼容接口关闭时不附加专有参数，以保留基本聊天兼容性，其默认思考行为仍以模型文档为准。旧记录中的思考强度仅用于恢复开启或关闭状态，不再向界面暴露或发送给模型，重新保存或测试连接后使用新的布尔开关字段。

输入框中键入 `@` 可选择当前后端注册的 `calculator`、`search`、`todo`，支持按名称或中文描述筛选、上下键和 Enter 选择。示例：`@calculator 计算 128*36`，或 `@calculator @todo 计算 128*36 并记入待办`。选择时不会立即发送；发送后将去重的工具名称作为该条用户消息的偏好加入模型上下文，原始消息正文保持不变。提示模型优先考虑这些工具，但不强制调用、固定顺序或逐个执行；信息或必要参数不足时先询问，不编造参数。模型也可以直接回答或使用其他适用工具，所有工具保持可用，`tool_choice` 使用 `auto`，包括 DeepSeek 思考模式。实际工具参数仍经后端严格校验，写入成功只能依据工具结果。删除输入中的对应提及即可取消偏好；运行中引导和排队消息转引导保留相同语义，偏好提示参与上下文预算和摘要压缩。

模型返回的 `reasoning_content`、文本形式的 `reasoning`，以及正文中的 `<think>…</think>` 会与回答分开解析，包括流式分片标签。聊天消息上方的“思考过程”可折叠查看，正常完成或中断时已接收的思考随消息保存，刷新后仍可查看。只有供应商实际返回的文本才会展示，不会根据最终答案补造思考；未返回思考时不显示该区域。

原生 `reasoning_content` 还会单独保存在协议消息中，工具追问及之后的用户追问均原样携带，避免 DeepSeek 携带 `tools` 时因缺少历史思考返回 400。它与包含标签思考的展示文本分开存储。旧版本记录在回放时利用已保存的思考补字段，不改写旧历史；原来没有保存的思考无法还原，不会补造。相关限制见 [DeepSeek 工具选择参数](https://api-docs.deepseek.com/api/create-chat-completion/) 与 [思考模式](https://api-docs.deepseek.com/zh-cn/guides/thinking_mode/)。

缺少对话／摘要模型、连接测试未通过、配置读取失败或模型容量不足时，对话页会提示并提供设置入口，发送按钮和 Enter 均不可提交；后端在任务入队前再次检查。对话和摘要均不发送固定输出上限，摘要不设正文长度目标，由模型及供应商决定长度；Context 预留自动管理，无需填写输出 token 数。

右上角只有在后端实时连接正常且模型配置就绪、连接测试通过时显示“后端已链接”。悬浮可分别查看后端与模型的勾叉状态及原因；模型状态使用最近一次保存／测试结果，不会因悬浮额外调用模型。

发送按钮旁的圆环显示估算 Context 使用率，点击可查看容量、来源、历史摘要以及“立即压缩”按钮；尚未估算时显示“—”。手动压缩仅在会话空闲时可发起，会调用摘要模型，保留最近一轮及完整原始历史，可使用停止按钮取消；失败或无压缩收益时不覆盖原摘要。连续工具调用在消息流原位合并为一个折叠入口，展开后可单独查看每次调用与结果，文字消息保留原位置。同批并发调用按请求顺序展示，不代表完成先后。完整链路按任务选择、按步骤聚合，每页 8 个步骤，展开后查看原始事件。

界面容量与用量采用千进制单位：`k = 1,000 tokens`、`m = 1,000,000 tokens`，最多一位小数；例如默认容量 262144 显示为 `262.1k`。底层容量判断和原始事件仍使用完整数值。

会话列表支持确认后删除。删除使用逻辑标记：隐藏会话并拒绝继续访问，保留底层执行证据；共享待办保留。仍有运行／排队任务时不能删除，先停止任务、取消排队消息。其他窗口收到删除事件后同步更新。

模型 Key 在本地 SQLite 保存，接口只回读是否已配置，不回传原值；编辑时留空表示保留。数据库与运行数据均被 Git 忽略。演示用户 A／B 不是登录认证机制，首版默认仅绑定本机地址。

## 目录

```text
backend/app/       自写 Runtime、模型适配、Context、工具、SQLite、API
backend/tests/     可重复离线测试，真实 SDK 的假 HTTP 传输测试
fronted/           Vue + TypeScript + Naive UI
dev_docs/          规划、设计、接口、十道架构题研究和验证记录
```

后端入口为 `backend/app/main.py`，执行主链为 `backend/app/runtime.py`。工具定义与处理器在 `tools.py`，参数在 `schemas.py`；新增工具通过 `ToolRegistry.register()` 注册参数模型和处理器。

## 执行模型

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

普通发送默认排队。运行中发送的消息，在该条排队消息旁点击“引导”，可将它转为当前任务的补充；输入区不再单列引导按钮。转换会原子地移出独立队列并保存引导，重复点击不会重复执行。补充在下一次模型调用前生效，不中断当前步骤；最终回答期间收到引导也会继续处理，沿用原预算。当前任务已结束时拒绝转换并保留原排队消息。

手动停止会保留部分输出和操作证据，记录“已被用户手动停止”，清理当前执行后自动开始下一条排队消息。已提交的待办不会被撤销。

断线取消该客户端的当前执行和未执行队列。重连只恢复历史，不自动重新发送。切换会话不关闭连接；其他窗口不受影响。后端只能在检测到断线时执行取消，远端模型停止计算不由本地保证。

服务重启会把遗留任务标记为中断、队列标记取消，恢复工具结果的配对信息，不自动重放工具。继续任务请发送新消息，获得新预算并利用已有历史。

### 预算与重试

默认：模型 20 次、工具 40 次、总时长 300 秒、单次模型 60 秒、单次工具 10 秒、失败后重试 3 次、每次间隔 30 秒。全部可在全局设置中修改，后续开始的任务生效。

重试、摘要计入模型调用次数，等待计入总时长；预算不足会提前结束。仅暂时性网络、限流和上游故障重试，遵循更长的 `Retry-After`。认证、请求错误、Context 超限、不确定写入及已展示部分回答的流失败不透明重试。

等待重试时，页面和链路显示错误原因、等待秒数及重试次数。例如 HTTP 429 会被当作可重试的限流响应；它也可能来自额度限制，具体原因需结合供应商信息判断。全局设置可修改间隔，重试次数设为 0 可关闭自动重试。

## Memory 的恢复时机和放置方式

本项目的聊天记忆是 Session 级短期记忆，不自动跨会话召回聊天。用户待办属于共享业务数据，由工具按需读取，不等于跨会话聊天记忆。

1. 每次模型调用前，从 SQLite 读取当前 Session 消息与摘要，移除已被摘要覆盖的旧消息。
2. 输入放置顺序为系统指令／工具定义、明确标记的历史摘要、未覆盖的近期交互和当前请求／引导／工具结果。
3. 已知模型尝试匹配 tokenizer，未知兼容模型使用保守 UTF-8 字节估算；输入计数含消息和 Schema 开销，页面明确是估算。
4. 可用输入空间扣除自动输出预留 `max(64, 容量的10%)`，以及 `max(256, 容量的5%)` 估算余量。预留仅影响压缩判断，对话请求不传固定输出上限；供应商默认限制仍然生效，预留也不能保证任意长回答都能容纳。
5. 达到可用空间 80% 触发摘要，目标约 50%；保护当前用户请求与引导、最近完整工具交互。
6. 旧对话和当前任务较早的已完成步骤可摘要；按摘要模型自身容量分批，成功后才更新覆盖范围。
7. 摘要失败／停止不覆盖旧摘要；原输入超限时保留历史并停止，必要输入过大时也不强行删除。

完整历史不随压缩删除。后续读取待办时以数据库最新状态为准，旧摘要里的状态不是当前事实。Trace 可查看每次容量估算、压缩前后用量和摘要。

## 验证

```powershell
Set-Location 'D:\MyProject\guangcheng_agent_harness\backend'
uv run pytest -q
uv run ruff check app tests
uv run ruff format --check app tests

Set-Location 'D:\MyProject\guangcheng_agent_harness\fronted'
npm test
npm run build
```

真实模型需要在页面配置自己的连接。离线假模型只由测试显式注入，生产界面不会自动用假模型替代失败的服务。

详见 [逐项验收清单](dev_docs/manual_test_checklist.md)、[验证记录](dev_docs/verification.md)、[接口与事件](dev_docs/interfaces.md)、[十道架构题备选研究](dev_docs/architecture_study.md) 和 [开发路线](dev_docs/开发路线-2026-10-20.md)。真实供应商的模型行为和真实页面联调不由离线测试代替。

## 后端学习

三天深入导读见 [后端学习路线](dev_docs/backend_learning_3days.md)，包含每日阅读范围、核心函数、断点、练习与验收；按函数查位置可使用 [源码与测试符号索引](dev_docs/backend_source_index.md)。

## Git

近期问题、原因、修复提交和验证边界汇总见 [Bug 修复与体验改进记录](dev_docs/bugfix_log.md)。

`main` 保留原题与规划基线，`dev/runtime` 保存完整开发实现；每批验证后提交。GitHub 仓库为 [guangcheng_agent_harness](https://github.com/3027726980/guangcheng_agent_harness)，查看代码请使用 [dev/runtime 分支](https://github.com/3027726980/guangcheng_agent_harness/tree/dev/runtime)。推送须由用户明确授权，不自动合并 main 或强推；本地／远端状态以 `git status`、`git log --all --oneline` 和 `git ls-remote --heads origin` 为准。

## 来源与扩展

PinLayout 采用 MIT 许可，原声明保存在 `fronted/LICENSE`。后续扩展 Jev 前置决策、真实搜索、多模态和必要时的 Decisions API，均不改变首版统一 Agent 的可独立运行能力。

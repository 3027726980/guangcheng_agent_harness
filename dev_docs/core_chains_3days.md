# 核心链路导航

更新日期：2026-10-20。毛毛的完整学习入口为 [三天读懂项目核心链路：后端学习指导路线](backend_learning_3days.md)，每天 3–4 小时，目标是能读懂并修改代码。

本页仅保留导航，不重复维护另一份完整路线。各链路的流程、精读行段、输入输出、练习和验收均以指导路线为准。

| 想理解什么 | 在指导路线中阅读 | 首要代码入口 |
| --- | --- | --- |
| 对象和整体请求过程 | 第 1 节 | Runtime.submit → _lane → _execute |
| 对话输入到输出 | 第 2.1 节 | 前端 send → HTTP send_message → Runtime |
| 模型协议和流式响应 | 第 2.2 节 | _invoke → OpenAIModel.complete → ModelReply |
| 工具契约、注册和执行 | 第 2.3 节 | BaseTool → ToolRegistry.register / execute |
| Agent Loop 的循环与结束 | 第 2.4 节 | _execute → _batch |
| Context 组装和摘要压缩 | 第 2.5 节 | ContextManager.build → tool_groups |
| Session 隔离与调度 | 第 2.6 节 | session → _lane → session_detail |
| 幂等、事务和恢复 | 第 2.7 节 | submit → _todo → repair_calls |
| 事件与 Trace | 第 2.8 节 | emit → append_event → SSE → traceSteps |
| 每天按什么顺序学习 | 第 3 节 | 第一天正常链路、第二天历史与数据、第三天控制与排错 |
| 用哪些测试核对理解 | 第 4 节 | 已有离线测试的准备、动作和断言 |
| 如何定位后续修改 | 第 5 节 | 需求／故障到代码入口的对照表 |

按符号精确查找代码可使用 [源码与测试符号索引](backend_source_index.md)。验证边界见 [实施与验证记录](verification.md)。

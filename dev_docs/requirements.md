# 需求到实现的映射

| 要求 | 实现入口 | 验证 |
| --- | --- | --- |
| 自写核心 Loop | `backend/app/runtime.py` | 直接回答、工具闭环、无 Agent 框架依赖 |
| 工具注册／Schema | `tools.py` + `schemas.py` | 参数模型生成 Schema、注册自定义处理器、非法参数拒绝 |
| 至少三个工具，包含 todo | calculator / search / todo | 计算与异常、Mock 搜索、待办事务与隔离 |
| 真实 LLM 接口 | `llm.py` | SDK 假 HTTP 流测试已提供；真实模型待配置验收 |
| 两个窗口独立 Session | Runtime 单会话 lane、窗口客户端 ID | 双窗口运行与断线隔离测试 |
| 最大轮次 | 全局运行设置，任务配置快照 | 模型、工具及总时长限制 |
| 持续对话／纯追问／工具追问 | Session 历史、摘要、工具结果 | 多轮及会话隔离测试；真实语义效果待验收 |
| 基础 Context 压缩 | `context.py` | 触发、覆盖范围、保留请求、失败保留、完整工具边界 |
| 异常处理 | ModelFailure / ToolError / DomainError | 重试、输出中断、参数及版本冲突 |
| trace／日志 | 持久事件、页面链路抽屉 | SDK 调用、工具、摘要、引导、取消事件 |
| 测试用例 | `backend/tests/`、`fronted/tests/` | 可重复离线运行 |
| README 与记忆说明 | 根 README | 恢复时机、注入位置和共享待办边界明确 |
| AI Prompt／问题记录 | `ai_prompt_log.md`、`troubleshooting.md` | 记录实际开发决策与故障，不伪造模型实验 |
| 架构题 | `architecture_study.md` | 十道均为备选研究，最终用户每模块选一题 |

本地版本管理、开发分支与私有 GitHub 远端已建立；开发实现查看 `dev/runtime`，`main` 保留基线。远端发布按毛毛明确授权执行，并核对远端 SHA，不把本地提交当作已推送。

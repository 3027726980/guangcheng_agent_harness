# 需求到实现的映射

| 要求 | 实现入口 | 验证 |
| --- | --- | --- |
| 自写核心 Loop | `backend/app/runtime.py` | 直接回答、工具闭环、无 Agent 框架依赖 |
| 工具注册／Schema | `tool/base.py`、`tool/registry.py` 与各工具文件 | 参数模型生成 Schema、注册自定义处理器、非法参数拒绝 |
| 至少三个工具，包含 todo | calculator / search / todo | 计算与异常、Mock 搜索、待办事务与隔离 |
| 真实 LLM 接口 | `llm.py` | SDK 假 HTTP 流测试已提供；真实模型待配置验收 |
| 两个窗口独立 Session | Runtime 单会话 lane、窗口客户端 ID | 两客户端独立历史及纯对话追问测试 |
| 最大轮次 | 全局运行设置 | 连续工具循环达到模型调用上限停止 |
| 持续对话／纯追问／工具追问 | Session 历史、摘要、工具结果 | 多轮及会话隔离测试；真实语义效果待验收 |
| 基础 Context 压缩 | `context.py` | 触发、覆盖范围、保留请求、失败保留、完整工具边界 |
| 异常处理 | ModelFailure / ToolError / DomainError | 模型失败、流中断、未知工具、非法参数和截断输出 |
| trace／日志 | 持久事件、页面链路抽屉 | 模型开始、工具参数及结果、最终任务状态及凭据不泄漏 |
| 测试用例 | `backend/tests/`、`fronted/tests/` | 后端按单元／集成分类；前端维持现有测试 |
| README 与记忆说明 | 根 README | 恢复时机、注入位置和共享待办边界明确 |
| AI Prompt／问题记录 | `ai_prompt_log.md`、`troubleshooting.md` | 记录实际开发决策与故障，不伪造模型实验 |
| 架构题 | `architecture_study.md` | 十道均为备选研究，最终用户每模块选一题 |

本地版本管理、开发分支与私有 GitHub 远端已建立；开发实现查看 `dev/runtime`，`main` 保留基线。远端发布按毛毛明确授权执行，并核对远端 SHA，不把本地提交当作已推送。

## 要求 3：需求、自动化用例与真实验收

更新日期：2026-10-23。下表只对应原题核心功能；自动化用例使用离线模型及临时资源，不代表真实模型语义效果已验收。运行方式、PyCharm 配置与报告说明见 [测试说明](../backend/tests/README.md)。A1—A6 均见 [真实模型验收模板](../backend/tests/agent_acceptance/README.md)，当前全部未执行。

| 题目功能 | 自动化用例（实际路径与函数） | 人工验收 |
| --- | --- | --- |
| 直接回答 | [integration/test_runtime.py](../backend/tests/integration/test_runtime.py)：`test_direct_answer` | A1 |
| 工具注册、名称／描述／Schema | [unit/test_contracts.py](../backend/tests/unit/test_contracts.py)：`test_tool_schemas_describe_all_three_tools`；[unit/test_tools.py](../backend/tests/unit/test_tools.py)：`test_registered_subclass_executes_without_registry_branch_changes`、`test_base_tool_contract_and_registration_guards` | A2、A3 |
| calculator／search／todo | [unit/test_tools.py](../backend/tests/unit/test_tools.py)：`test_calculator`、`test_calculator_rejects_code_and_bad_expressions`、`test_search_mock_and_empty`；[integration/test_todo.py](../backend/tests/integration/test_todo.py)：`test_todo_crud_persists_state` | A2、A3、A5 |
| 严格参数校验 | [unit/test_contracts.py](../backend/tests/unit/test_contracts.py)：`test_calculator_args_reject_invalid_input`、`test_search_args_reject_invalid_input`、`test_todo_args_require_action_fields`；[unit/test_tools.py](../backend/tests/unit/test_tools.py)：`test_registry_rejects_unknown_tool_and_invalid_arguments` | 自动化边界检查 |
| LLM 输出解析 | [unit/test_response_parser.py](../backend/tests/unit/test_response_parser.py)：`test_think_tags_split_at_every_character_and_unclosed_reasoning`、`test_parser_handles_empty_multiple_and_incomplete_tags`；[integration/test_model_output.py](../backend/tests/integration/test_model_output.py)：`test_native_reasoning_nonstreaming_is_separate_from_answer`、`test_streaming_reasoning_tool_arguments_and_auto_tool_choice`、`test_runtime_persists_reasoning_and_emits_it_separately` | A1、A2；模型未公开思考时不要求补造 |
| 一次／多次工具循环和结果回传 | [integration/test_runtime.py](../backend/tests/integration/test_runtime.py)：`test_single_tool_result_feeds_answer`、`test_multiple_tools_then_followup` | A2、A5 |
| 两个会话、纯对话与工具追问 | [integration/test_runtime.py](../backend/tests/integration/test_runtime.py)：`test_conversation_followup_and_session_isolation`、`test_multiple_tools_then_followup`；[integration/test_api.py](../backend/tests/integration/test_api.py)：`test_api_tools_and_independent_sessions` | A4、A5 |
| 最大轮次及工具预算 | [integration/test_runtime.py](../backend/tests/integration/test_runtime.py)：`test_model_round_limit_stops_tool_loop`、`test_tool_budget_blocks_entire_batch` | 自动化模拟持续循环 |
| 基础 Context 压缩 | [integration/test_context.py](../backend/tests/integration/test_context.py)：`test_compaction_coverage_and_pinned_request`、`test_summary_failure_keeps_original_and_stops_when_over_limit`；[unit/test_context.py](../backend/tests/unit/test_context.py)：`test_incomplete_tool_pair_is_rejected`、`test_complete_tool_round_is_one_group` | A6 |
| 模型与工具基本异常 | [integration/test_runtime.py](../backend/tests/integration/test_runtime.py)：`test_model_failure_is_not_success`、`test_tool_error_returns_to_model`、`test_blank_answer_fails`、`test_partial_output_failure_is_not_retried`、`test_truncated_tool_response_is_never_executed`；[integration/test_llm.py](../backend/tests/integration/test_llm.py)：缺失结束标记和 429 分类三个用例；[unit/test_contracts.py](../backend/tests/unit/test_contracts.py)：`test_finish_reason_rejects_invalid_response` | A3 的无匹配检查；网络错误不主动制造 |
| Trace 与基本凭据保护 | [integration/test_runtime.py](../backend/tests/integration/test_runtime.py)：`test_trace_records_tools_and_redacts_credentials`；[unit/test_contracts.py](../backend/tests/unit/test_contracts.py)：`test_request_and_run_lists_are_not_shared` | A1—A6 对应任务的 Trace |

排队转引导、复杂取消竞争、重启恢复、旧结束工具历史兼容、供应商专属协议、日志轮转、调用详情分页、热更新和增量缓存等扩展功能仍存在于生产代码，但其专用自动化测试已按本次精简范围移除。

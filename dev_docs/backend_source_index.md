# 后端源码与测试符号索引

更新日期：2026-10-20。按当前待发布的后端源码与测试静态生成，包含 BaseTool 重构、工具偏好、模型协议与思考解析；不再沿用 df7ceee 的旧行号。配套 [新版三天学习指导路线](backend_learning_3days.md) 与 [核心链路导航](core_chains_3days.md)。

仅解析 AST，不导入应用、不启动服务。起始行为定义行，装饰器可能位于前面；嵌套路径用于阅读定位，FastAPI 路由位于 create_app 内。后续变更优先搜索符号名。

## 应用源码

### context.py

文件：[backend/app/context.py](../backend/app/context.py)，共 292 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `ContextFailure` | 类 | 18 | 19 |
| `tokenizer_for` | 函数 | 23 | 28 |
| `tokens` | 函数 | 31 | 38 |
| `tool_groups` | 函数 | 41 | 64 |
| `ContextManager` | 类 | 67 | 292 |
| `ContextManager.__init__` | 函数 | 68 | 70 |
| `ContextManager.build` | 异步函数 | 72 | 292 |
| `ContextManager.build.count` | 函数 | 114 | 116 |
| `ContextManager.build.summary_count` | 函数 | 118 | 120 |
| `ContextManager.build.assemble` | 函数 | 128 | 133 |

### llm.py

文件：[backend/app/llm.py](../backend/app/llm.py)，共 243 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `ModelFailure` | 类 | 23 | 29 |
| `ModelFailure.__init__` | 函数 | 25 | 29 |
| `OpenAIModel` | 类 | 32 | 216 |
| `OpenAIModel.__init__` | 函数 | 33 | 35 |
| `OpenAIModel.complete` | 异步函数 | 37 | 174 |
| `OpenAIModel.probe` | 异步函数 | 176 | 192 |
| `OpenAIModel.capacity` | 异步函数 | 194 | 216 |
| `ScriptedModel` | 类 | 219 | 243 |
| `ScriptedModel.__init__` | 函数 | 222 | 225 |
| `ScriptedModel.complete` | 异步函数 | 227 | 243 |

### main.py

文件：[backend/app/main.py](../backend/app/main.py)，共 322 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `public_profile` | 函数 | 35 | 41 |
| `create_app` | 函数 | 44 | 318 |
| `create_app.lifespan` | 异步函数 | 52 | 56 |
| `create_app.domain_error` | 异步函数 | 62 | 64 |
| `create_app.tool_error` | 异步函数 | 67 | 72 |
| `create_app.model_error` | 异步函数 | 75 | 77 |
| `create_app.validation_error` | 异步函数 | 80 | 82 |
| `create_app.user` | 异步函数 | 84 | 88 |
| `create_app.health` | 异步函数 | 91 | 93 |
| `create_app.users` | 异步函数 | 96 | 98 |
| `create_app.available_tools` | 异步函数 | 101 | 104 |
| `create_app.register_client` | 异步函数 | 107 | 111 |
| `create_app.subscribe` | 异步函数 | 114 | 144 |
| `create_app.subscribe.stream` | 异步函数 | 121 | 138 |
| `create_app.disconnect` | 异步函数 | 147 | 153 |
| `create_app.sessions` | 异步函数 | 156 | 163 |
| `create_app.create_session` | 异步函数 | 166 | 168 |
| `create_app.delete_session` | 异步函数 | 171 | 173 |
| `create_app.session_detail` | 异步函数 | 176 | 185 |
| `create_app.send_message` | 异步函数 | 188 | 190 |
| `create_app.compact_context` | 异步函数 | 193 | 195 |
| `create_app.steer` | 异步函数 | 198 | 200 |
| `create_app.cancel` | 异步函数 | 203 | 205 |
| `create_app.steer_queued` | 异步函数 | 208 | 210 |
| `create_app.todos` | 异步函数 | 213 | 217 |
| `create_app.change_todo` | 异步函数 | 220 | 229 |
| `create_app.settings` | 异步函数 | 232 | 234 |
| `create_app.save_settings` | 异步函数 | 237 | 248 |
| `create_app.profiles` | 异步函数 | 251 | 253 |
| `create_app.save_profile` | 异步函数 | 255 | 280 |
| `create_app.add_profile` | 异步函数 | 283 | 285 |
| `create_app.update_profile` | 异步函数 | 288 | 290 |
| `create_app.test_profile` | 异步函数 | 293 | 303 |
| `create_app.delete_profile` | 异步函数 | 306 | 316 |

### model_protocol.py

文件：[backend/app/model_protocol.py](../backend/app/model_protocol.py)，共 33 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `thinking_enabled` | 函数 | 7 | 19 |
| `thinking_options` | 函数 | 22 | 28 |
| `deepseek_thinking` | 函数 | 31 | 33 |

### response_parser.py

文件：[backend/app/response_parser.py](../backend/app/response_parser.py)，共 58 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `native_reasoning` | 函数 | 6 | 13 |
| `protocol_reasoning` | 函数 | 16 | 19 |
| `ReasoningParser` | 类 | 22 | 58 |
| `ReasoningParser.__init__` | 函数 | 24 | 27 |
| `ReasoningParser.push` | 函数 | 29 | 52 |
| `ReasoningParser.finish` | 函数 | 54 | 58 |

### runtime.py

文件：[backend/app/runtime.py](../backend/app/runtime.py)，共 821 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `BudgetExceeded` | 类 | 34 | 35 |
| `DomainError` | 类 | 38 | 42 |
| `DomainError.__init__` | 函数 | 39 | 42 |
| `Client` | 类 | 46 | 53 |
| `Runtime` | 类 | 56 | 821 |
| `Runtime.__init__` | 函数 | 57 | 72 |
| `Runtime.initialize` | 异步函数 | 74 | 91 |
| `Runtime.settings` | 异步函数 | 93 | 96 |
| `Runtime.emit` | 异步函数 | 98 | 111 |
| `Runtime.public_run` | 函数 | 114 | 119 |
| `Runtime.session` | 异步函数 | 121 | 131 |
| `Runtime.delete_session` | 异步函数 | 133 | 143 |
| `Runtime.configured_models` | 异步函数 | 145 | 162 |
| `Runtime.create_session` | 异步函数 | 164 | 175 |
| `Runtime.submit` | 异步函数 | 177 | 216 |
| `Runtime.validate_tools` | 函数 | 218 | 223 |
| `Runtime.steer` | 异步函数 | 225 | 242 |
| `Runtime.cancel` | 异步函数 | 244 | 251 |
| `Runtime.steer_queued` | 异步函数 | 253 | 297 |
| `Runtime._cancel_locked` | 异步函数 | 299 | 309 |
| `Runtime.disconnect` | 异步函数 | 311 | 329 |
| `Runtime._lane` | 异步函数 | 331 | 359 |
| `Runtime.append` | 异步函数 | 361 | 377 |
| `Runtime._apply_steering` | 异步函数 | 379 | 391 |
| `Runtime._invoke` | 异步函数 | 393 | 482 |
| `Runtime._compact_manually` | 异步函数 | 484 | 516 |
| `Runtime._compact_manually.summarize` | 异步函数 | 488 | 490 |
| `Runtime._compact_manually.emit` | 异步函数 | 492 | 501 |
| `Runtime._execute` | 异步函数 | 518 | 647 |
| `Runtime._save_interruption` | 异步函数 | 649 | 662 |
| `Runtime._batch` | 异步函数 | 664 | 780 |
| `Runtime._batch.one` | 异步函数 | 683 | 745 |
| `Runtime.repair_calls` | 异步函数 | 782 | 813 |
| `Runtime.close` | 异步函数 | 815 | 821 |

### schemas.py

文件：[backend/app/schemas.py](../backend/app/schemas.py)，共 146 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `StrictModel` | 类 | 11 | 13 |
| `RuntimeSettings` | 类 | 16 | 45 |
| `RuntimeSettings.discard_legacy_output_settings` | 函数 | 34 | 38 |
| `RuntimeSettings.validate_watermarks` | 函数 | 41 | 45 |
| `ModelProfile` | 类 | 48 | 63 |
| `ModelProfile.validate_url` | 函数 | 59 | 63 |
| `SessionCreate` | 类 | 66 | 67 |
| `CompactionRequest` | 类 | 70 | 73 |
| `MessageRequest` | 类 | 76 | 79 |
| `SteeringRequest` | 类 | 82 | 86 |
| `CalculatorArgs` | 类 | 89 | 90 |
| `SearchArgs` | 类 | 93 | 95 |
| `TodoArgs` | 类 | 98 | 117 |
| `TodoArgs.required_by_action` | 函数 | 108 | 117 |
| `ToolCall` | 类 | 120 | 124 |
| `ModelReply` | 类 | 127 | 135 |
| `Event` | 类 | 138 | 146 |

### storage.py

文件：[backend/app/storage.py](../backend/app/storage.py)，共 166 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `uid` | 函数 | 41 | 43 |
| `Database` | 类 | 46 | 166 |
| `Database.__init__` | 函数 | 48 | 53 |
| `Database.initialize` | 异步函数 | 55 | 60 |
| `Database.transaction` | 异步函数 | 63 | 67 |
| `Database.get` | 异步函数 | 69 | 75 |
| `Database.put` | 异步函数 | 77 | 97 |
| `Database.list` | 异步函数 | 99 | 109 |
| `Database.remove` | 异步函数 | 111 | 114 |
| `Database.append_event` | 异步函数 | 116 | 139 |
| `Database.history_events` | 异步函数 | 141 | 162 |
| `Database.close` | 异步函数 | 164 | 166 |

### token_budget.py

文件：[backend/app/token_budget.py](../backend/app/token_budget.py)，共 9 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `output_reserve` | 函数 | 7 | 9 |

### tools.py

文件：[backend/app/tools.py](../backend/app/tools.py)，共 273 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `ToolError` | 类 | 20 | 24 |
| `ToolError.__init__` | 函数 | 21 | 24 |
| `BaseTool` | 类 | 30 | 52 |
| `BaseTool.schema` | 函数 | 38 | 47 |
| `BaseTool.execute` | 异步函数 | 50 | 52 |
| `CalculatorTool` | 类 | 55 | 63 |
| `CalculatorTool.execute` | 异步函数 | 61 | 63 |
| `SearchTool` | 类 | 66 | 74 |
| `SearchTool.execute` | 异步函数 | 72 | 74 |
| `TodoTool` | 类 | 77 | 85 |
| `TodoTool.execute` | 异步函数 | 83 | 85 |
| `ToolRegistry` | 类 | 88 | 129 |
| `ToolRegistry.__init__` | 函数 | 90 | 94 |
| `ToolRegistry.register` | 函数 | 96 | 113 |
| `ToolRegistry.schemas` | 函数 | 115 | 117 |
| `ToolRegistry.is_parallel` | 函数 | 119 | 121 |
| `ToolRegistry.execute` | 异步函数 | 123 | 129 |
| `_calculate` | 函数 | 132 | 168 |
| `_search` | 函数 | 200 | 215 |
| `_todo` | 异步函数 | 218 | 273 |

## 测试源码

### test_api.py

文件：[backend/tests/test_api.py](../backend/tests/test_api.py)，共 209 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `ProbeModel` | 类 | 16 | 24 |
| `ProbeModel.probe` | 异步函数 | 17 | 24 |
| `test_manual_todos_use_the_same_tool_registry` | 函数 | 27 | 47 |
| `test_manual_todos_use_the_same_tool_registry.execute` | 异步函数 | 34 | 37 |
| `test_api_identity_models_settings_and_shared_todos` | 函数 | 50 | 105 |
| `test_sse_disconnect_cancels_owned_active_and_queued_runs` | 异步函数 | 108 | 163 |
| `test_sse_disconnect_cancels_owned_active_and_queued_runs.block` | 异步函数 | 113 | 116 |
| `test_sse_disconnect_cancels_owned_active_and_queued_runs.receive` | 异步函数 | 121 | 128 |
| `test_sse_disconnect_cancels_owned_active_and_queued_runs.output` | 异步函数 | 130 | 133 |
| `test_session_list_reports_only_owned_pending_runs` | 函数 | 166 | 209 |

### test_context.py

文件：[backend/tests/test_context.py](../backend/tests/test_context.py)，共 185 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `setup` | 异步函数 | 14 | 37 |
| `test_compaction_coverage_and_pinned_request` | 异步函数 | 40 | 77 |
| `test_summary_failure_keeps_original_and_stops_when_over_limit` | 异步函数 | 80 | 109 |
| `test_incomplete_tool_pair_is_rejected` | 函数 | 112 | 117 |
| `test_smaller_summary_model_preserves_still_fitting_original` | 异步函数 | 120 | 153 |
| `test_cancelled_summary_does_not_update_coverage` | 异步函数 | 156 | 185 |

### test_deepseek_compat.py

文件：[backend/tests/test_deepseek_compat.py](../backend/tests/test_deepseek_compat.py)，共 146 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `test_deepseek_tools_keep_thinking_and_use_auto_choice` | 异步函数 | 20 | 45 |
| `test_deepseek_tools_keep_thinking_and_use_auto_choice.respond` | 函数 | 22 | 39 |
| `test_deepseek_native_reasoning_survives_tool_loop_and_next_user_turn` | 异步函数 | 48 | 89 |
| `test_deepseek_native_reasoning_survives_tool_loop_and_next_user_turn.respond` | 函数 | 55 | 77 |
| `test_old_saved_reasoning_is_replayed_without_mutating_legacy_records` | 异步函数 | 92 | 107 |
| `test_known_400_has_actionable_hint_without_raw_provider_secrets` | 异步函数 | 111 | 124 |
| `test_known_400_has_actionable_hint_without_raw_provider_secrets.respond` | 函数 | 113 | 118 |
| `test_nonstream_native_reasoning_is_not_replaced_by_display_tags` | 异步函数 | 128 | 139 |
| `test_nonstream_native_reasoning_is_not_replaced_by_display_tags.respond` | 函数 | 130 | 134 |
| `test_compatibility_check_does_not_match_a_similar_untrusted_host` | 函数 | 142 | 146 |

### test_llm.py

文件：[backend/tests/test_llm.py](../backend/tests/test_llm.py)，共 202 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `test_actual_sdk_streaming_arguments_and_text` | 异步函数 | 14 | 75 |
| `test_actual_sdk_streaming_arguments_and_text.respond` | 函数 | 16 | 62 |
| `test_actual_sdk_streaming_arguments_and_text.on_text` | 异步函数 | 66 | 68 |
| `test_sdk_rate_limit_classified_without_hidden_retries` | 异步函数 | 78 | 96 |
| `test_sdk_rate_limit_classified_without_hidden_retries.respond` | 函数 | 82 | 89 |
| `test_stream_without_finish_marker_fails` | 异步函数 | 99 | 112 |
| `test_stream_without_finish_marker_fails.respond` | 函数 | 101 | 103 |
| `test_stream_without_finish_marker_fails.output` | 异步函数 | 105 | 107 |
| `test_completion_token_parameter_and_reasoning_configuration` | 异步函数 | 115 | 141 |
| `test_completion_token_parameter_and_reasoning_configuration.respond` | 函数 | 117 | 135 |
| `test_answer_can_use_provider_default_output_and_report_actual_usage` | 异步函数 | 144 | 168 |
| `test_answer_can_use_provider_default_output_and_report_actual_usage.respond` | 函数 | 146 | 163 |
| `test_profile_probe_reads_capacity_or_falls_back` | 异步函数 | 172 | 202 |
| `test_profile_probe_reads_capacity_or_falls_back.respond` | 函数 | 174 | 198 |

### test_manual_compaction.py

文件：[backend/tests/test_manual_compaction.py](../backend/tests/test_manual_compaction.py)，共 175 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `history` | 异步函数 | 17 | 30 |
| `compact` | 异步函数 | 33 | 43 |
| `test_manual_compaction_below_threshold_preserves_last_turn_and_history` | 异步函数 | 46 | 62 |
| `test_empty_manual_compaction_skips_model` | 异步函数 | 65 | 72 |
| `test_longer_summary_is_not_committed` | 异步函数 | 75 | 85 |
| `test_reasoning_summary_uses_provider_default_instead_of_text_target_cap` | 异步函数 | 88 | 131 |
| `test_reasoning_summary_uses_provider_default_instead_of_text_target_cap.respond` | 函数 | 94 | 121 |
| `test_provider_truncated_summary_reports_reason_and_keeps_prior_summary` | 异步函数 | 134 | 145 |
| `test_manual_compaction_exclusion_failure_and_cancel_preserve_coverage` | 异步函数 | 149 | 175 |
| `test_manual_compaction_exclusion_failure_and_cancel_preserve_coverage.summary` | 异步函数 | 155 | 159 |

### test_recovery.py

文件：[backend/tests/test_recovery.py](../backend/tests/test_recovery.py)，共 162 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `test_tool_parallel_limit_and_result_order` | 异步函数 | 13 | 50 |
| `test_tool_parallel_limit_and_result_order.execute` | 异步函数 | 21 | 30 |
| `test_batch_with_todo_is_sequential` | 异步函数 | 53 | 79 |
| `test_batch_with_todo_is_sequential.execute` | 异步函数 | 58 | 65 |
| `test_cancel_during_committed_write_preserves_result` | 异步函数 | 82 | 110 |
| `test_cancel_during_committed_write_preserves_result.execute` | 异步函数 | 88 | 93 |
| `test_total_timeout_is_terminal` | 异步函数 | 113 | 125 |
| `test_total_timeout_is_terminal.block` | 异步函数 | 119 | 121 |
| `test_restart_marks_runs_and_recovers_committed_tool_result` | 异步函数 | 128 | 162 |

### test_response_features.py

文件：[backend/tests/test_response_features.py](../backend/tests/test_response_features.py)，共 254 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `test_think_tags_split_at_every_character_and_unclosed_reasoning` | 函数 | 19 | 29 |
| `test_native_reasoning_nonstreaming_is_separate_from_answer` | 异步函数 | 33 | 44 |
| `test_native_reasoning_nonstreaming_is_separate_from_answer.respond` | 函数 | 35 | 40 |
| `test_streaming_reasoning_tool_arguments_and_auto_tool_choice` | 异步函数 | 47 | 81 |
| `test_streaming_reasoning_tool_arguments_and_auto_tool_choice.respond` | 函数 | 49 | 63 |
| `test_streaming_reasoning_tool_arguments_and_auto_tool_choice.on_text` | 异步函数 | 67 | 69 |
| `test_streaming_reasoning_tool_arguments_and_auto_tool_choice.on_reasoning` | 异步函数 | 71 | 73 |
| `test_runtime_persists_reasoning_and_emits_it_separately` | 异步函数 | 84 | 94 |
| `test_selected_tool_preference_and_results_feed_followup` | 异步函数 | 97 | 110 |
| `test_unknown_selected_tool_is_rejected_before_queuing` | 异步函数 | 113 | 120 |
| `test_missing_tool_parameters_allow_clarification` | 异步函数 | 123 | 133 |
| `test_reasoning_only_failure_is_not_retried_and_is_preserved` | 异步函数 | 136 | 151 |
| `test_reasoning_only_failure_is_not_retried_and_is_preserved.complete` | 异步函数 | 140 | 144 |
| `test_multiple_mentions_allow_a_different_tool_order` | 异步函数 | 154 | 168 |
| `test_tool_preference_allows_other_tools` | 异步函数 | 171 | 183 |
| `test_direct_steering_mentions_allow_clarification` | 异步函数 | 186 | 211 |
| `test_direct_steering_mentions_allow_clarification.block` | 异步函数 | 191 | 195 |
| `test_queued_mentions_survive_conversion_to_steering` | 异步函数 | 214 | 239 |
| `test_queued_mentions_survive_conversion_to_steering.block` | 异步函数 | 219 | 223 |
| `test_tool_catalog_comes_from_registry_and_requires_valid_demo_user` | 函数 | 242 | 254 |

### test_runtime.py

文件：[backend/tests/test_runtime.py](../backend/tests/test_runtime.py)，共 371 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `wait_until` | 异步函数 | 17 | 21 |
| `terminal` | 异步函数 | 24 | 31 |
| `terminal.check` | 异步函数 | 26 | 28 |
| `harness` | 异步函数 | 35 | 65 |
| `harness.sleep` | 异步函数 | 40 | 43 |
| `send` | 异步函数 | 68 | 74 |
| `test_direct_reply_and_request_deduplication` | 异步函数 | 77 | 88 |
| `test_tool_loop_followup_and_session_isolation` | 异步函数 | 91 | 113 |
| `test_three_retries_and_model_budget` | 异步函数 | 116 | 134 |
| `test_partial_output_failure_is_not_retried` | 异步函数 | 137 | 151 |
| `test_partial_output_failure_is_not_retried.partial` | 异步函数 | 141 | 144 |
| `test_final_answer_steering_remains_in_current_task` | 异步函数 | 154 | 173 |
| `test_final_answer_steering_remains_in_current_task.answer` | 异步函数 | 159 | 163 |
| `test_manual_stop_advances_queue_but_disconnect_cancels_it` | 异步函数 | 176 | 202 |
| `test_manual_stop_advances_queue_but_disconnect_cancels_it.block` | 异步函数 | 181 | 185 |
| `test_truncated_tool_response_is_never_executed` | 异步函数 | 205 | 219 |
| `test_tool_budget_blocks_entire_batch` | 异步函数 | 222 | 237 |
| `test_settings_snapshot_and_two_window_isolation` | 异步函数 | 240 | 265 |
| `test_settings_snapshot_and_two_window_isolation.block` | 异步函数 | 245 | 249 |
| `test_invalid_configuration_rejected_before_queueing` | 异步函数 | 269 | 286 |
| `test_deletion_rejects_busy_session_then_hides_history` | 异步函数 | 289 | 316 |
| `test_deletion_rejects_busy_session_then_hides_history.block` | 异步函数 | 294 | 297 |
| `test_queued_message_can_be_atomically_promoted_to_current_run` | 异步函数 | 319 | 352 |
| `test_queued_message_can_be_atomically_promoted_to_current_run.block` | 异步函数 | 324 | 328 |
| `test_promoting_after_current_task_finishes_preserves_queue` | 异步函数 | 355 | 371 |

### test_thinking_switch.py

文件：[backend/tests/test_thinking_switch.py](../backend/tests/test_thinking_switch.py)，共 90 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `test_model_profile_only_accepts_boolean_thinking_switch` | 函数 | 19 | 26 |
| `test_deepseek_sdk_request_uses_only_thinking_toggle` | 异步函数 | 30 | 42 |
| `test_deepseek_sdk_request_uses_only_thinking_toggle.respond` | 函数 | 32 | 37 |
| `test_legacy_profile_exposes_only_normalized_switch` | 函数 | 46 | 53 |
| `test_api_round_trip_and_retesting_legacy_profile` | 函数 | 56 | 77 |
| `test_unknown_provider_with_switch_off_keeps_plain_chat_compatible` | 异步函数 | 80 | 90 |
| `test_unknown_provider_with_switch_off_keeps_plain_chat_compatible.respond` | 函数 | 82 | 86 |

### test_token_budget.py

文件：[backend/tests/test_token_budget.py](../backend/tests/test_token_budget.py)，共 19 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `test_legacy_limits_do_not_survive_settings_round_trip` | 函数 | 8 | 12 |
| `test_input_reserve_follows_capacity` | 函数 | 15 | 19 |

### test_tools.py

文件：[backend/tests/test_tools.py](../backend/tests/test_tools.py)，共 174 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `invoke_tool` | 异步函数 | 15 | 18 |
| `invoke_todo` | 异步函数 | 21 | 23 |
| `test_calculator` | 异步函数 | 29 | 31 |
| `test_calculator_rejects_code_and_bad_expressions` | 异步函数 | 35 | 38 |
| `test_pydantic_schema_and_validation` | 函数 | 41 | 49 |
| `test_search_mock_and_empty` | 异步函数 | 52 | 56 |
| `test_tool_declarations` | 函数 | 59 | 70 |
| `test_tool_declarations.call` | 函数 | 63 | 65 |
| `test_todo_transaction_idempotency_user_isolation_and_version` | 异步函数 | 73 | 97 |
| `test_registered_subclass_executes_without_registry_branch_changes` | 异步函数 | 100 | 121 |
| `test_registered_subclass_executes_without_registry_branch_changes.EchoTool` | 类 | 102 | 113 |
| `test_registered_subclass_executes_without_registry_branch_changes.EchoTool.execute` | 异步函数 | 108 | 113 |
| `test_base_tool_contract_and_registration_guards` | 函数 | 124 | 139 |
| `test_base_tool_contract_and_registration_guards.MissingExecute` | 类 | 129 | 130 |
| `test_invalid_tool_metadata_is_rejected` | 函数 | 144 | 150 |
| `test_synchronous_tool_override_is_rejected` | 函数 | 153 | 163 |
| `test_synchronous_tool_override_is_rejected.SyncTool` | 类 | 155 | 160 |
| `test_synchronous_tool_override_is_rejected.SyncTool.execute` | 函数 | 158 | 160 |
| `test_registry_rejects_unknown_tool_and_invalid_arguments` | 异步函数 | 166 | 174 |

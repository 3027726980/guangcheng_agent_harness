# 后端源码与测试符号索引

生成日期：2026-10-20。源码基线：`df7ceee`。配套 [三天学习路线](backend_learning_3days.md)。行号以此版本为准，后续修改后请搜索完整函数名。

本索引由 Python AST 静态解析生成，没有导入或执行应用。表中的嵌套路径是阅读定位名称；路由函数位于 create_app 内部，不是需要手动创建的类方法。

## 一、应用源码

### main.py

文件：[backend/app/main.py](../backend/app/main.py)，共 266 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `public_profile` | 函数 | 30 | 34 |
| `create_app` | 函数 | 37 | 263 |
| `create_app.lifespan` | 异步函数 | 44 | 47 |
| `create_app.domain_error` | 异步函数 | 53 | 54 |
| `create_app.tool_error` | 异步函数 | 57 | 61 |
| `create_app.model_error` | 异步函数 | 64 | 65 |
| `create_app.validation_error` | 异步函数 | 68 | 69 |
| `create_app.user` | 异步函数 | 71 | 74 |
| `create_app.health` | 异步函数 | 77 | 78 |
| `create_app.users` | 异步函数 | 81 | 82 |
| `create_app.register_client` | 异步函数 | 85 | 88 |
| `create_app.subscribe` | 异步函数 | 91 | 118 |
| `create_app.subscribe.stream` | 异步函数 | 97 | 112 |
| `create_app.disconnect` | 异步函数 | 121 | 126 |
| `create_app.sessions` | 异步函数 | 129 | 135 |
| `create_app.create_session` | 异步函数 | 138 | 139 |
| `create_app.delete_session` | 异步函数 | 142 | 143 |
| `create_app.session_detail` | 异步函数 | 146 | 154 |
| `create_app.send_message` | 异步函数 | 157 | 158 |
| `create_app.compact_context` | 异步函数 | 161 | 162 |
| `create_app.steer` | 异步函数 | 165 | 166 |
| `create_app.cancel` | 异步函数 | 169 | 170 |
| `create_app.steer_queued` | 异步函数 | 173 | 174 |
| `create_app.todos` | 异步函数 | 177 | 178 |
| `create_app.change_todo` | 异步函数 | 181 | 187 |
| `create_app.settings` | 异步函数 | 190 | 191 |
| `create_app.save_settings` | 异步函数 | 194 | 204 |
| `create_app.profiles` | 异步函数 | 207 | 208 |
| `create_app.save_profile` | 异步函数 | 210 | 233 |
| `create_app.add_profile` | 异步函数 | 236 | 237 |
| `create_app.update_profile` | 异步函数 | 240 | 241 |
| `create_app.test_profile` | 异步函数 | 244 | 249 |
| `create_app.delete_profile` | 异步函数 | 252 | 261 |

### schemas.py

文件：[backend/app/schemas.py](../backend/app/schemas.py)，共 123 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `StrictModel` | 类 | 8 | 9 |
| `RuntimeSettings` | 类 | 12 | 38 |
| `RuntimeSettings.discard_legacy_output_settings` | 函数 | 28 | 32 |
| `RuntimeSettings.validate_watermarks` | 函数 | 35 | 38 |
| `ModelProfile` | 类 | 41 | 53 |
| `ModelProfile.validate_url` | 函数 | 50 | 53 |
| `SessionCreate` | 类 | 56 | 57 |
| `CompactionRequest` | 类 | 60 | 62 |
| `MessageRequest` | 类 | 65 | 66 |
| `SteeringRequest` | 类 | 69 | 71 |
| `CalculatorArgs` | 类 | 74 | 75 |
| `SearchArgs` | 类 | 78 | 80 |
| `TodoArgs` | 类 | 83 | 100 |
| `TodoArgs.required_by_action` | 函数 | 92 | 100 |
| `ToolCall` | 类 | 103 | 106 |
| `ModelReply` | 类 | 109 | 113 |
| `Event` | 类 | 116 | 123 |

### runtime.py

文件：[backend/app/runtime.py](../backend/app/runtime.py)，共 734 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `BudgetExceeded` | 类 | 27 | 28 |
| `DomainError` | 类 | 31 | 34 |
| `DomainError.__init__` | 函数 | 32 | 34 |
| `Client` | 类 | 38 | 43 |
| `Runtime` | 类 | 46 | 734 |
| `Runtime.__init__` | 函数 | 47 | 58 |
| `Runtime.initialize` | 异步函数 | 60 | 76 |
| `Runtime.settings` | 异步函数 | 78 | 80 |
| `Runtime.emit` | 异步函数 | 82 | 93 |
| `Runtime.public_run` | 函数 | 96 | 99 |
| `Runtime.session` | 异步函数 | 101 | 110 |
| `Runtime.delete_session` | 异步函数 | 112 | 121 |
| `Runtime.configured_models` | 异步函数 | 123 | 139 |
| `Runtime.create_session` | 异步函数 | 141 | 151 |
| `Runtime.submit` | 异步函数 | 153 | 187 |
| `Runtime.steer` | 异步函数 | 189 | 204 |
| `Runtime.cancel` | 异步函数 | 206 | 212 |
| `Runtime.steer_queued` | 异步函数 | 214 | 256 |
| `Runtime._cancel_locked` | 异步函数 | 258 | 267 |
| `Runtime.disconnect` | 异步函数 | 269 | 285 |
| `Runtime._lane` | 异步函数 | 287 | 314 |
| `Runtime.append` | 异步函数 | 316 | 327 |
| `Runtime._apply_steering` | 异步函数 | 329 | 339 |
| `Runtime._invoke` | 异步函数 | 341 | 417 |
| `Runtime._compact_manually` | 异步函数 | 419 | 448 |
| `Runtime._compact_manually.summarize` | 异步函数 | 422 | 423 |
| `Runtime._compact_manually.emit` | 异步函数 | 425 | 433 |
| `Runtime._execute` | 异步函数 | 450 | 569 |
| `Runtime._save_interruption` | 异步函数 | 571 | 581 |
| `Runtime._batch` | 异步函数 | 583 | 695 |
| `Runtime._batch.one` | 异步函数 | 601 | 662 |
| `Runtime.repair_calls` | 异步函数 | 697 | 727 |
| `Runtime.close` | 异步函数 | 729 | 734 |

### llm.py

文件：[backend/app/llm.py](../backend/app/llm.py)，共 179 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `ModelFailure` | 类 | 16 | 20 |
| `ModelFailure.__init__` | 函数 | 17 | 20 |
| `OpenAIModel` | 类 | 23 | 157 |
| `OpenAIModel.__init__` | 函数 | 24 | 25 |
| `OpenAIModel.complete` | 异步函数 | 27 | 117 |
| `OpenAIModel.probe` | 异步函数 | 119 | 134 |
| `OpenAIModel.capacity` | 异步函数 | 136 | 157 |
| `ScriptedModel` | 类 | 160 | 179 |
| `ScriptedModel.__init__` | 函数 | 163 | 165 |
| `ScriptedModel.complete` | 异步函数 | 167 | 179 |

### tools.py

文件：[backend/app/tools.py](../backend/app/tools.py)，共 226 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `ToolError` | 类 | 17 | 20 |
| `ToolError.__init__` | 函数 | 18 | 20 |
| `Tool` | 类 | 24 | 39 |
| `Tool.schema` | 函数 | 31 | 39 |
| `ToolRegistry` | 类 | 42 | 92 |
| `ToolRegistry.__init__` | 函数 | 43 | 71 |
| `ToolRegistry.register` | 函数 | 73 | 78 |
| `ToolRegistry.schemas` | 函数 | 80 | 81 |
| `ToolRegistry.is_parallel` | 函数 | 83 | 84 |
| `ToolRegistry.execute` | 异步函数 | 86 | 92 |
| `calculate` | 函数 | 95 | 128 |
| `search` | 函数 | 159 | 172 |
| `todo` | 异步函数 | 175 | 226 |

### storage.py

文件：[backend/app/storage.py](../backend/app/storage.py)，共 149 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `uid` | 函数 | 36 | 37 |
| `Database` | 类 | 40 | 149 |
| `Database.__init__` | 函数 | 41 | 45 |
| `Database.initialize` | 异步函数 | 47 | 51 |
| `Database.transaction` | 异步函数 | 54 | 57 |
| `Database.get` | 异步函数 | 59 | 64 |
| `Database.put` | 异步函数 | 66 | 85 |
| `Database.list` | 异步函数 | 87 | 96 |
| `Database.remove` | 异步函数 | 98 | 100 |
| `Database.append_event` | 异步函数 | 102 | 124 |
| `Database.history_events` | 异步函数 | 126 | 146 |
| `Database.close` | 异步函数 | 148 | 149 |

### context.py

文件：[backend/app/context.py](../backend/app/context.py)，共 253 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `ContextFailure` | 类 | 12 | 13 |
| `tokenizer_for` | 函数 | 17 | 21 |
| `tokens` | 函数 | 24 | 29 |
| `tool_groups` | 函数 | 32 | 53 |
| `ContextManager` | 类 | 56 | 253 |
| `ContextManager.__init__` | 函数 | 57 | 58 |
| `ContextManager.build` | 异步函数 | 60 | 253 |
| `ContextManager.build.count` | 函数 | 82 | 83 |
| `ContextManager.build.summary_count` | 函数 | 85 | 86 |
| `ContextManager.build.assemble` | 函数 | 93 | 97 |

### token_budget.py

文件：[backend/app/token_budget.py](../backend/app/token_budget.py)，共 5 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `output_reserve` | 函数 | 4 | 5 |

## 二、测试源码

按实际函数名搜索，parametrize 可能将一个函数展开为多项用例。测试辅助函数与 fixture 一并列出，阅读测试前应先理解 harness、send 和 terminal。

### test_api.py

文件：[backend/tests/test_api.py](../backend/tests/test_api.py)。

| 符号 | 起始行 | 结束行 |
| --- | ---: | ---: |
| `ProbeModel` | 13 | 20 |
| `test_api_identity_models_settings_and_shared_todos` | 23 | 77 |
| `test_sse_disconnect_cancels_owned_active_and_queued_runs` | 80 | 131 |
| `test_session_list_reports_only_owned_pending_runs` | 134 | 176 |

### test_context.py

文件：[backend/tests/test_context.py](../backend/tests/test_context.py)。

| 符号 | 起始行 | 结束行 |
| --- | ---: | ---: |
| `setup` | 11 | 33 |
| `test_compaction_coverage_and_pinned_request` | 36 | 66 |
| `test_summary_failure_keeps_original_and_stops_when_over_limit` | 69 | 95 |
| `test_incomplete_tool_pair_is_rejected` | 98 | 102 |
| `test_smaller_summary_model_preserves_still_fitting_original` | 105 | 135 |
| `test_cancelled_summary_does_not_update_coverage` | 138 | 164 |

### test_llm.py

文件：[backend/tests/test_llm.py](../backend/tests/test_llm.py)。

| 符号 | 起始行 | 结束行 |
| --- | ---: | ---: |
| `test_actual_sdk_streaming_arguments_and_text` | 11 | 69 |
| `test_sdk_rate_limit_classified_without_hidden_retries` | 72 | 88 |
| `test_stream_without_finish_marker_fails` | 91 | 101 |
| `test_completion_token_parameter_and_reasoning_configuration` | 104 | 127 |
| `test_answer_can_use_provider_default_output_and_report_actual_usage` | 130 | 152 |
| `test_profile_probe_reads_capacity_or_falls_back` | 156 | 184 |

### test_manual_compaction.py

文件：[backend/tests/test_manual_compaction.py](../backend/tests/test_manual_compaction.py)。

| 符号 | 起始行 | 结束行 |
| --- | ---: | ---: |
| `history` | 14 | 26 |
| `compact` | 29 | 38 |
| `test_manual_compaction_below_threshold_preserves_last_turn_and_history` | 41 | 56 |
| `test_empty_manual_compaction_skips_model` | 59 | 65 |
| `test_longer_summary_is_not_committed` | 68 | 77 |
| `test_reasoning_summary_uses_provider_default_instead_of_text_target_cap` | 80 | 121 |
| `test_provider_truncated_summary_reports_reason_and_keeps_prior_summary` | 124 | 134 |
| `test_manual_compaction_exclusion_failure_and_cancel_preserve_coverage` | 138 | 162 |

### test_recovery.py

文件：[backend/tests/test_recovery.py](../backend/tests/test_recovery.py)。

| 符号 | 起始行 | 结束行 |
| --- | ---: | ---: |
| `test_tool_parallel_limit_and_result_order` | 10 | 45 |
| `test_batch_with_todo_is_sequential` | 48 | 72 |
| `test_cancel_during_committed_write_preserves_result` | 75 | 101 |
| `test_total_timeout_is_terminal` | 104 | 114 |
| `test_restart_marks_runs_and_recovers_committed_tool_result` | 117 | 150 |

### test_runtime.py

文件：[backend/tests/test_runtime.py](../backend/tests/test_runtime.py)。

| 符号 | 起始行 | 结束行 |
| --- | ---: | ---: |
| `wait_until` | 14 | 17 |
| `terminal` | 20 | 25 |
| `harness` | 29 | 57 |
| `send` | 60 | 65 |
| `test_direct_reply_and_request_deduplication` | 68 | 78 |
| `test_tool_loop_followup_and_session_isolation` | 81 | 102 |
| `test_three_retries_and_model_budget` | 105 | 122 |
| `test_partial_output_failure_is_not_retried` | 125 | 137 |
| `test_final_answer_steering_remains_in_current_task` | 140 | 157 |
| `test_manual_stop_advances_queue_but_disconnect_cancels_it` | 160 | 184 |
| `test_truncated_tool_response_is_never_executed` | 187 | 200 |
| `test_tool_budget_blocks_entire_batch` | 203 | 217 |
| `test_settings_snapshot_and_two_window_isolation` | 220 | 243 |
| `test_invalid_configuration_rejected_before_queueing` | 247 | 263 |
| `test_deletion_rejects_busy_session_then_hides_history` | 266 | 291 |
| `test_queued_message_can_be_atomically_promoted_to_current_run` | 294 | 325 |
| `test_promoting_after_current_task_finishes_preserves_queue` | 328 | 343 |

### test_token_budget.py

文件：[backend/tests/test_token_budget.py](../backend/tests/test_token_budget.py)。

| 符号 | 起始行 | 结束行 |
| --- | ---: | ---: |
| `test_legacy_limits_do_not_survive_settings_round_trip` | 5 | 8 |
| `test_input_reserve_follows_capacity` | 11 | 14 |

### test_tools.py

文件：[backend/tests/test_tools.py](../backend/tests/test_tools.py)。

| 符号 | 起始行 | 结束行 |
| --- | ---: | ---: |
| `test_calculator` | 14 | 15 |
| `test_calculator_rejects_code_and_bad_expressions` | 19 | 21 |
| `test_pydantic_schema_and_validation` | 24 | 31 |
| `test_search_mock_and_empty` | 34 | 37 |
| `test_tool_declarations` | 40 | 49 |
| `test_todo_transaction_idempotency_user_isolation_and_version` | 52 | 75 |
| `test_registered_handler_executes_without_registry_branch_changes` | 78 | 92 |

# 后端源码与测试符号索引

更新日期：2026-10-23。按当前 AST 生成，包含 Run、SessionContext、日志、调用快照和按文件拆分的提示词及工具包。

仅静态解析，不导入应用或启动服务。相关机制见 [日志及上下文说明](logs_context.md)。行号随修改可能变化，优先按符号名搜索。

## 应用源码

### __init__.py

文件：[backend/app/__init__.py](../backend/app/__init__.py)，共 1 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |

### context.py

文件：[backend/app/context.py](../backend/app/context.py)，共 320 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `ContextFailure` | 类 | 20 | 21 |
| `tokenizer_for` | 函数 | 25 | 30 |
| `tokens` | 函数 | 33 | 40 |
| `tool_groups` | 函数 | 43 | 66 |
| `ContextManager` | 类 | 69 | 320 |
| `ContextManager.__init__` | 函数 | 70 | 74 |
| `ContextManager.build` | 异步函数 | 76 | 320 |
| `ContextManager.build.count` | 函数 | 111 | 113 |
| `ContextManager.build.summary_count` | 函数 | 115 | 117 |
| `ContextManager.build.assemble` | 函数 | 125 | 132 |

### diagnostics.py

文件：[backend/app/diagnostics.py](../backend/app/diagnostics.py)，共 145 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `redact` | 函数 | 30 | 46 |
| `Diagnostics` | 类 | 49 | 145 |
| `Diagnostics.__init__` | 函数 | 50 | 57 |
| `Diagnostics.remember_secret` | 函数 | 59 | 62 |
| `Diagnostics.safe` | 函数 | 64 | 66 |
| `Diagnostics.write` | 异步函数 | 68 | 102 |
| `Diagnostics._write` | 函数 | 105 | 115 |
| `Diagnostics.event` | 异步函数 | 117 | 125 |
| `Diagnostics.call` | 异步函数 | 127 | 140 |
| `Diagnostics.close` | 异步函数 | 142 | 145 |

### llm.py

文件：[backend/app/llm.py](../backend/app/llm.py)，共 258 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `ModelFailure` | 类 | 23 | 29 |
| `ModelFailure.__init__` | 函数 | 25 | 29 |
| `OpenAIModel` | 类 | 32 | 228 |
| `OpenAIModel.__init__` | 函数 | 33 | 35 |
| `OpenAIModel.complete` | 异步函数 | 37 | 186 |
| `OpenAIModel.complete.publish` | 异步函数 | 88 | 98 |
| `OpenAIModel.probe` | 异步函数 | 188 | 204 |
| `OpenAIModel.capacity` | 异步函数 | 206 | 228 |
| `ScriptedModel` | 类 | 231 | 258 |
| `ScriptedModel.__init__` | 函数 | 234 | 237 |
| `ScriptedModel.complete` | 异步函数 | 239 | 258 |

### main.py

文件：[backend/app/main.py](../backend/app/main.py)，共 396 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `public_profile` | 函数 | 36 | 42 |
| `create_app` | 函数 | 45 | 392 |
| `create_app.lifespan` | 异步函数 | 53 | 59 |
| `create_app.diagnostic_http` | 异步函数 | 65 | 101 |
| `create_app.domain_error` | 异步函数 | 104 | 106 |
| `create_app.tool_error` | 异步函数 | 109 | 114 |
| `create_app.model_error` | 异步函数 | 117 | 119 |
| `create_app.validation_error` | 异步函数 | 122 | 124 |
| `create_app.user` | 异步函数 | 126 | 130 |
| `create_app.health` | 异步函数 | 133 | 140 |
| `create_app.users` | 异步函数 | 143 | 145 |
| `create_app.available_tools` | 异步函数 | 148 | 153 |
| `create_app.register_client` | 异步函数 | 156 | 160 |
| `create_app.subscribe` | 异步函数 | 163 | 194 |
| `create_app.subscribe.stream` | 异步函数 | 170 | 188 |
| `create_app.disconnect` | 异步函数 | 197 | 203 |
| `create_app.sessions` | 异步函数 | 206 | 213 |
| `create_app.create_session` | 异步函数 | 216 | 218 |
| `create_app.delete_session` | 异步函数 | 221 | 223 |
| `create_app.session_detail` | 异步函数 | 226 | 235 |
| `create_app.model_calls` | 异步函数 | 238 | 247 |
| `create_app.model_call` | 异步函数 | 250 | 256 |
| `create_app.send_message` | 异步函数 | 259 | 261 |
| `create_app.compact_context` | 异步函数 | 264 | 266 |
| `create_app.steer` | 异步函数 | 269 | 271 |
| `create_app.cancel` | 异步函数 | 274 | 276 |
| `create_app.steer_queued` | 异步函数 | 279 | 281 |
| `create_app.todos` | 异步函数 | 284 | 288 |
| `create_app.change_todo` | 异步函数 | 291 | 300 |
| `create_app.settings` | 异步函数 | 303 | 305 |
| `create_app.save_settings` | 异步函数 | 308 | 319 |
| `create_app.profiles` | 异步函数 | 322 | 324 |
| `create_app.save_profile` | 异步函数 | 326 | 352 |
| `create_app.add_profile` | 异步函数 | 355 | 357 |
| `create_app.update_profile` | 异步函数 | 360 | 362 |
| `create_app.test_profile` | 异步函数 | 365 | 377 |
| `create_app.delete_profile` | 异步函数 | 380 | 390 |

### model_protocol.py

文件：[backend/app/model_protocol.py](../backend/app/model_protocol.py)，共 33 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `thinking_enabled` | 函数 | 7 | 19 |
| `thinking_options` | 函数 | 22 | 28 |
| `deepseek_thinking` | 函数 | 31 | 33 |

### prompt/__init__.py

文件：[backend/app/prompt/__init__.py](../backend/app/prompt/__init__.py)，共 1 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |

### prompt/summary.py

文件：[backend/app/prompt/summary.py](../backend/app/prompt/summary.py)，共 7 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `SUMMARY_PROMPT` | 常量 | 3 | 7 |

### prompt/summary_prefix.py

文件：[backend/app/prompt/summary_prefix.py](../backend/app/prompt/summary_prefix.py)，共 3 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `SUMMARY_PREFIX_PROMPT` | 常量 | 3 | 3 |

### prompt/system.py

文件：[backend/app/prompt/system.py](../backend/app/prompt/system.py)，共 10 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `SYSTEM_PROMPT` | 常量 | 3 | 10 |

### prompt/tool_preference.py

文件：[backend/app/prompt/tool_preference.py](../backend/app/prompt/tool_preference.py)，共 9 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `TOOL_PREFERENCE_PROMPT` | 常量 | 3 | 9 |

### prompts.py

文件：[backend/app/prompts.py](../backend/app/prompts.py)，共 66 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `PROMPTS` | 常量 | 13 | 18 |
| `PromptError` | 类 | 21 | 22 |
| `PromptMessages` | 类 | 25 | 32 |
| `PromptMessages.__init__` | 函数 | 28 | 32 |
| `PromptStore` | 类 | 35 | 56 |
| `PromptStore.load` | 函数 | 43 | 56 |
| `PromptBundle` | 类 | 59 | 66 |
| `PromptBundle.__init__` | 函数 | 60 | 62 |
| `PromptBundle.render` | 函数 | 64 | 66 |

### request_capture.py

文件：[backend/app/request_capture.py](../backend/app/request_capture.py)，共 31 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `request_body` | 函数 | 12 | 22 |
| `capture_request` | 异步函数 | 25 | 31 |

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

### run.py

文件：[backend/app/run.py](../backend/app/run.py)，共 58 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `ModelSnapshot` | 类 | 16 | 21 |
| `Run` | 类 | 24 | 58 |
| `Run.to_record` | 函数 | 56 | 58 |

### runtime.py

文件：[backend/app/runtime.py](../backend/app/runtime.py)，共 998 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `BudgetExceeded` | 类 | 33 | 34 |
| `validate_finish_reason` | 函数 | 37 | 56 |
| `DomainError` | 类 | 59 | 63 |
| `DomainError.__init__` | 函数 | 60 | 63 |
| `Client` | 类 | 67 | 74 |
| `Runtime` | 类 | 77 | 998 |
| `Runtime.__init__` | 函数 | 78 | 95 |
| `Runtime.initialize` | 异步函数 | 97 | 113 |
| `Runtime.settings` | 异步函数 | 115 | 118 |
| `Runtime.emit` | 异步函数 | 120 | 129 |
| `Runtime._broadcast` | 函数 | 131 | 140 |
| `Runtime.report_logging_status` | 异步函数 | 142 | 148 |
| `Runtime.public_run` | 函数 | 151 | 153 |
| `Runtime.get_run` | 异步函数 | 155 | 160 |
| `Runtime.list_runs` | 异步函数 | 162 | 164 |
| `Runtime.session` | 异步函数 | 166 | 177 |
| `Runtime.delete_session` | 异步函数 | 179 | 190 |
| `Runtime.configured_models` | 异步函数 | 192 | 206 |
| `Runtime.create_session` | 异步函数 | 208 | 219 |
| `Runtime.submit` | 异步函数 | 221 | 262 |
| `Runtime.validate_tools` | 函数 | 264 | 269 |
| `Runtime.steer` | 异步函数 | 271 | 293 |
| `Runtime.cancel` | 异步函数 | 295 | 302 |
| `Runtime.steer_queued` | 异步函数 | 304 | 346 |
| `Runtime._cancel_locked` | 异步函数 | 348 | 359 |
| `Runtime.disconnect` | 异步函数 | 361 | 379 |
| `Runtime._lane` | 异步函数 | 381 | 413 |
| `Runtime.append` | 异步函数 | 415 | 445 |
| `Runtime._apply_steering` | 异步函数 | 447 | 461 |
| `Runtime._invoke` | 异步函数 | 463 | 623 |
| `Runtime._invoke.on_text` | 异步函数 | 488 | 493 |
| `Runtime._invoke.on_reasoning` | 异步函数 | 495 | 500 |
| `Runtime._invoke.record_request` | 异步函数 | 505 | 530 |
| `Runtime._compact_manually` | 异步函数 | 625 | 658 |
| `Runtime._compact_manually.summarize` | 异步函数 | 629 | 631 |
| `Runtime._compact_manually.emit` | 异步函数 | 633 | 642 |
| `Runtime._execute` | 异步函数 | 660 | 819 |
| `Runtime._execute.summarize` | 异步函数 | 689 | 691 |
| `Runtime._execute.context_event` | 异步函数 | 693 | 695 |
| `Runtime._save_interruption` | 异步函数 | 821 | 836 |
| `Runtime._batch` | 异步函数 | 838 | 955 |
| `Runtime._batch.one` | 异步函数 | 857 | 919 |
| `Runtime.repair_calls` | 异步函数 | 957 | 988 |
| `Runtime.close` | 异步函数 | 990 | 998 |

### schemas.py

文件：[backend/app/schemas.py](../backend/app/schemas.py)，共 115 行。

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
| `ToolCall` | 类 | 89 | 93 |
| `ModelReply` | 类 | 96 | 104 |
| `Event` | 类 | 107 | 115 |

### session_context.py

文件：[backend/app/session_context.py](../backend/app/session_context.py)，共 133 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `SessionContext` | 类 | 10 | 25 |
| `SessionContext.record` | 函数 | 17 | 25 |
| `ContextState` | 类 | 28 | 133 |
| `ContextState.__init__` | 函数 | 29 | 31 |
| `ContextState.lock` | 函数 | 33 | 35 |
| `ContextState._load` | 异步函数 | 37 | 63 |
| `ContextState.ensure_loaded` | 异步函数 | 65 | 68 |
| `ContextState.has_tool_calls` | 异步函数 | 70 | 74 |
| `ContextState.snapshot` | 异步函数 | 76 | 79 |
| `ContextState.append` | 异步函数 | 81 | 91 |
| `ContextState.compact` | 异步函数 | 93 | 110 |
| `ContextState._commit` | 异步函数 | 112 | 128 |
| `ContextState._commit.commit` | 异步函数 | 114 | 121 |
| `ContextState.evict` | 函数 | 130 | 133 |

### storage.py

文件：[backend/app/storage.py](../backend/app/storage.py)，共 223 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `uid` | 函数 | 55 | 57 |
| `Database` | 类 | 60 | 223 |
| `Database.__init__` | 函数 | 62 | 67 |
| `Database.initialize` | 异步函数 | 69 | 74 |
| `Database.transaction` | 异步函数 | 77 | 81 |
| `Database.get` | 异步函数 | 83 | 89 |
| `Database.put` | 异步函数 | 91 | 111 |
| `Database.list` | 异步函数 | 113 | 123 |
| `Database.get_many` | 异步函数 | 125 | 134 |
| `Database.run_messages` | 异步函数 | 136 | 148 |
| `Database.model_calls` | 异步函数 | 150 | 166 |
| `Database.remove` | 异步函数 | 168 | 171 |
| `Database.append_event` | 异步函数 | 173 | 196 |
| `Database.history_events` | 异步函数 | 198 | 219 |
| `Database.close` | 异步函数 | 221 | 223 |

### token_budget.py

文件：[backend/app/token_budget.py](../backend/app/token_budget.py)，共 9 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `output_reserve` | 函数 | 7 | 9 |

### tool/__init__.py

文件：[backend/app/tool/__init__.py](../backend/app/tool/__init__.py)，共 4 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |

### tool/base.py

文件：[backend/app/tool/base.py](../backend/app/tool/base.py)，共 47 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `ToolError` | 类 | 13 | 17 |
| `ToolError.__init__` | 函数 | 14 | 17 |
| `BaseTool` | 类 | 23 | 47 |
| `BaseTool.schema` | 函数 | 33 | 42 |
| `BaseTool.execute` | 异步函数 | 45 | 47 |

### tool/calculator.py

文件：[backend/app/tool/calculator.py](../backend/app/tool/calculator.py)，共 67 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `CalculatorArgs` | 类 | 16 | 17 |
| `CalculatorTool` | 类 | 20 | 28 |
| `CalculatorTool.execute` | 异步函数 | 26 | 28 |
| `_calculate` | 函数 | 31 | 67 |
| `_calculate.evaluate` | 函数 | 45 | 60 |

### tool/registry.py

文件：[backend/app/tool/registry.py](../backend/app/tool/registry.py)，共 61 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `ToolRegistry` | 类 | 16 | 61 |
| `ToolRegistry.__init__` | 函数 | 18 | 22 |
| `ToolRegistry.register` | 函数 | 24 | 41 |
| `ToolRegistry.user_tools` | 函数 | 43 | 45 |
| `ToolRegistry.schemas` | 函数 | 47 | 49 |
| `ToolRegistry.is_parallel` | 函数 | 51 | 53 |
| `ToolRegistry.execute` | 异步函数 | 55 | 61 |

### tool/search.py

文件：[backend/app/tool/search.py](../backend/app/tool/search.py)，共 72 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `SearchArgs` | 类 | 12 | 14 |
| `SearchTool` | 类 | 17 | 25 |
| `SearchTool.execute` | 异步函数 | 23 | 25 |
| `_search` | 函数 | 57 | 72 |

### tool/todo.py

文件：[backend/app/tool/todo.py](../backend/app/tool/todo.py)，共 103 行。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `TodoArgs` | 类 | 15 | 34 |
| `TodoArgs.required_by_action` | 函数 | 25 | 34 |
| `TodoTool` | 类 | 37 | 45 |
| `TodoTool.execute` | 异步函数 | 43 | 45 |
| `_todo` | 异步函数 | 48 | 103 |

## 离线测试

2026-10-23：按笔试核心要求精简。运行方式见 [测试说明](../backend/tests/README.md)，真实模型场景见 [人工验收](../backend/tests/agent_acceptance/README.md)。以下为当前静态 AST 索引。

### conftest.py

文件：[conftest.py](../backend/tests/conftest.py)。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `isolate_local_diagnostics` | 函数 | 9 | 11 |
| `reject_real_http` | 函数 | 15 | 21 |

### integration/test_api.py

文件：[integration/test_api.py](../backend/tests/integration/test_api.py)。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `test_api_tools_and_independent_sessions` | 函数 | 8 | 22 |

### integration/test_context.py

文件：[integration/test_context.py](../backend/tests/integration/test_context.py)。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `test_compaction_coverage_and_pinned_request` | 异步函数 | 12 | 48 |
| `test_summary_failure_keeps_original_and_stops_when_over_limit` | 异步函数 | 51 | 81 |

### integration/test_llm.py

文件：[integration/test_llm.py](../backend/tests/integration/test_llm.py)。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `test_nonstream_missing_finish_reason_is_rejected` | 异步函数 | 11 | 29 |
| `test_sdk_rate_limit_classified_without_hidden_retries` | 异步函数 | 32 | 50 |
| `test_stream_without_finish_marker_fails` | 异步函数 | 53 | 66 |

### integration/test_model_output.py

文件：[integration/test_model_output.py](../backend/tests/integration/test_model_output.py)。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `test_native_reasoning_nonstreaming_is_separate_from_answer` | 异步函数 | 16 | 34 |
| `test_streaming_reasoning_tool_arguments_and_auto_tool_choice` | 异步函数 | 37 | 99 |
| `test_runtime_persists_reasoning_and_emits_it_separately` | 异步函数 | 102 | 112 |

### integration/test_runtime.py

文件：[integration/test_runtime.py](../backend/tests/integration/test_runtime.py)。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `test_direct_answer` | 异步函数 | 15 | 23 |
| `test_single_tool_result_feeds_answer` | 异步函数 | 26 | 38 |
| `test_multiple_tools_then_followup` | 异步函数 | 41 | 58 |
| `test_conversation_followup_and_session_isolation` | 异步函数 | 61 | 84 |
| `test_model_round_limit_stops_tool_loop` | 异步函数 | 87 | 100 |
| `test_model_failure_is_not_success` | 异步函数 | 103 | 110 |
| `test_tool_error_returns_to_model` | 异步函数 | 121 | 133 |
| `test_blank_answer_fails` | 异步函数 | 136 | 141 |
| `test_trace_records_tools_and_redacts_credentials` | 异步函数 | 144 | 163 |
| `test_partial_output_failure_is_not_retried` | 异步函数 | 166 | 180 |
| `test_truncated_tool_response_is_never_executed` | 异步函数 | 183 | 199 |
| `test_tool_budget_blocks_entire_batch` | 异步函数 | 202 | 217 |

### integration/test_todo.py

文件：[integration/test_todo.py](../backend/tests/integration/test_todo.py)。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `test_todo_crud_persists_state` | 异步函数 | 6 | 44 |

### support/context.py

文件：[support/context.py](../backend/tests/support/context.py)。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `setup` | 异步函数 | 6 | 45 |

### support/runtime.py

文件：[support/runtime.py](../backend/tests/support/runtime.py)。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `wait_until` | 异步函数 | 13 | 17 |
| `terminal` | 异步函数 | 20 | 30 |
| `harness` | 异步函数 | 34 | 64 |
| `send` | 异步函数 | 67 | 73 |

### support/tools.py

文件：[support/tools.py](../backend/tests/support/tools.py)。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `invoke_tool` | 异步函数 | 9 | 12 |

### unit/test_context.py

文件：[unit/test_context.py](../backend/tests/unit/test_context.py)。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `test_incomplete_tool_pair_is_rejected` | 函数 | 8 | 13 |
| `test_complete_tool_round_is_one_group` | 函数 | 16 | 24 |

### unit/test_contracts.py

文件：[unit/test_contracts.py](../backend/tests/unit/test_contracts.py)。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `test_calculator_args_reject_invalid_input` | 函数 | 18 | 21 |
| `test_search_args_reject_invalid_input` | 函数 | 28 | 31 |
| `test_todo_args_require_action_fields` | 函数 | 45 | 48 |
| `test_tool_schemas_describe_all_three_tools` | 函数 | 51 | 59 |
| `test_request_and_run_lists_are_not_shared` | 函数 | 62 | 73 |
| `test_output_reserve_minimum_and_capacity` | 函数 | 77 | 79 |
| `test_context_watermarks_must_allow_compaction` | 函数 | 82 | 85 |
| `test_finish_reason_rejects_invalid_response` | 函数 | 99 | 106 |
| `test_finish_reason_accepts_normal_answer` | 函数 | 110 | 112 |

### unit/test_response_parser.py

文件：[unit/test_response_parser.py](../backend/tests/unit/test_response_parser.py)。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `test_think_tags_split_at_every_character_and_unclosed_reasoning` | 函数 | 8 | 18 |
| `test_parser_handles_empty_multiple_and_incomplete_tags` | 函数 | 30 | 37 |

### unit/test_tools.py

文件：[unit/test_tools.py](../backend/tests/unit/test_tools.py)。

| 符号 | 类型 | 起始行 | 结束行 |
| --- | --- | ---: | ---: |
| `test_calculator` | 异步函数 | 20 | 22 |
| `test_calculator_rejects_code_and_bad_expressions` | 异步函数 | 26 | 29 |
| `test_search_mock_and_empty` | 异步函数 | 32 | 38 |
| `test_registered_subclass_executes_without_registry_branch_changes` | 异步函数 | 41 | 62 |
| `test_base_tool_contract_and_registration_guards` | 函数 | 65 | 80 |
| `test_registry_rejects_unknown_tool_and_invalid_arguments` | 异步函数 | 83 | 91 |

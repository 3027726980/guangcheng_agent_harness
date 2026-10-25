// 作者：LHF。
// 注释维护时间：2026-10-20。
// 文件作用：前后端交互数据的 TypeScript 类型定义。
/** 作用：会话列表项与活跃任务概要。 */
export interface Session {
  // 会话列表只附带活跃任务概要，完整任务与消息在详情接口加载。
  id: string;
  title: string;
  user_id: string;
  active_runs?: { id: string; status: string }[];
}
// 作者：LHF；时间：2026-10-21；作用：同步后端 app/run.py 的公开任务字段。
export type RunStatus =
  | "queued" | "running" | "cancelling" | "completed"
  | "cancelled" | "failed" | "interrupted" | "limited";
/** 作用：一次聊天或压缩执行的状态和预算信息；内部配置与临时输出不会返回。 */
export interface Run {
  // 一次排队执行对应一个 Run，可能用于聊天或手动压缩。
  id: string;
  session_id: string;
  user_id: string;
  client_id: string;
  content: string;
  status: RunStatus;
  reason?: string | null;
  model_calls: number;
  tool_calls: number;
  created_at: number;
  started_at?: number | null;
  ended_at?: number | null;
  tool_names?: string[];
  settings?: { retries?: number } | null;
  purpose?: "chat" | "context_compaction";
  model_snapshot?: {
    id: string;
    model: string;
    context_capacity: number;
    capacity_source: string;
  } | null;
  compaction_result?: "compacted" | "skipped" | null;
  compaction_message?: string | null;
  steering_id?: string | null;
  steering_run_id?: string | null;
}
/** 作用：带执行来源、协议消息及思考展示元数据的历史记录。 */
export interface Message {
  // 外层记录追踪执行来源，内层 message 保留模型工具调用协议结构。
  id: string;
  run_id: string;
  timestamp: number;
  input_kind?: string;
  // 作者：LHF；时间：2026-10-22；作用：展示用户原文，模型正文可包含写入时固定的工具偏好。
  original_content?: string;
  reasoning?: string;
  message: {
    role: string;
    content: string | null;
    tool_call_id?: string;
    tool_calls?: {
      id: string;
      type: string;
      function: { name: string; arguments: string };
    }[];
  };
}
/** 作用：执行事件的归属、类型、时间和动态载荷。 */
export interface TraceEvent {
  // data 随 type 变化，界面按事件类型读取字段；timestamp 使用 Unix 秒。
  id: number;
  type: string;
  session_id?: string;
  run_id?: string;
  timestamp: number;
  data: Record<string, any>;
}
/** 作用：用户共享待办与用于并发校验的版本。 */
export interface Todo {
  // 写操作必须携带读取时的 version，后端据此检查并发修改。
  id: string;
  title: string;
  notes: string;
  status: string;
  version: number;
}
/** 作用：已脱敏模型配置与容量和连接测试结果。 */
export interface Profile {
  // 只暴露密钥是否存在，不包含已保存密钥的明文。
  id: string;
  name: string;
  base_url: string;
  model: string;
  has_api_key: boolean;
  context_capacity: number;
  capacity_source: string;
  test_status: string;
  output_token_parameter?: string;
  // 只控制思考模式是否启用，具体强度由供应商默认值决定。
  thinking_enabled: boolean;
}
/** 作用：历史摘要内容、压缩用量和覆盖的原消息 ID。 */
export interface Summary {
  // covered 保存摘要覆盖的原消息 ID；原消息仍保留，可用于追溯完整历史。
  text: string;
  before: number;
  after: number;
  covered: string[];
}

// @ 菜单的数据来自后端注册表，描述用于说明工具能力及模拟数据边界。
/** 作用：后端注册工具的名称与能力描述。 */
export interface AvailableTool {
  name: string;
  description: string;
}

/** 作者：LHF；时间：2026-10-22；作用：描述模型调用的分页概要。 */
export interface ModelCall {
  call_id: string;
  run_id: string;
  session_id: string;
  sequence: number;
  timestamp: number;
  purpose: string;
  attempt: number;
  model: string;
  status: string;
  context_version: number | null;
  prompt_versions: Record<string, string>;
}

/** 作用：完整脱敏输入按需获取，不随普通事件广播。 */
export interface ModelCallDetail extends ModelCall {
  request: {
    messages: Array<{ role: string; content?: unknown; tool_calls?: unknown; tool_call_id?: string; reasoning_content?: string }>;
    tools?: unknown[];
    [key: string]: unknown;
  };
  response?: unknown;
  error?: string;
  partial_response?: { text: string; reasoning: string };
}

export interface Session {
  id: string;
  title: string;
  user_id: string;
  active_runs?: { id: string; status: string }[];
}
export interface Run {
  id: string;
  session_id: string;
  user_id: string;
  content: string;
  status: string;
  reason?: string;
  model_calls: number;
  tool_calls: number;
  created_at: number;
  settings?: { retries?: number };
  purpose?: string;
  compaction_result?: string;
  compaction_message?: string;
}
export interface Message {
  id: string;
  run_id: string;
  timestamp: number;
  input_kind?: string;
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
export interface TraceEvent {
  id: number;
  type: string;
  session_id?: string;
  run_id?: string;
  timestamp: number;
  data: Record<string, any>;
}
export interface Todo {
  id: string;
  title: string;
  notes: string;
  status: string;
  version: number;
}
export interface Profile {
  id: string;
  name: string;
  base_url: string;
  model: string;
  has_api_key: boolean;
  context_capacity: number;
  capacity_source: string;
  test_status: string;
  output_token_parameter?: string;
  reasoning_effort?: string | null;
}
export interface Summary {
  text: string;
  before: number;
  after: number;
  covered: string[];
}

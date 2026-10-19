import type {
  Message,
  Profile,
  Session,
  Run,
  TraceEvent,
} from "../types/harness";

export function updateSessionActivity(
  sessions: Session[],
  run: Pick<Run, "id" | "session_id" | "status">,
) {
  const session = sessions.find((item) => item.id === run.session_id);
  if (!session) return;
  const active = (session.active_runs || []).filter(
    (item) => item.id !== run.id,
  );
  if (["queued", "running", "cancelling"].includes(run.status))
    active.push({ id: run.id, status: run.status });
  session.active_runs = active;
}

export function sessionActivityLabel(session: Session) {
  const runs = session.active_runs || [];
  if (runs.some((run) => run.status === "cancelling")) return "正在停止任务";
  const running = runs.filter((run) => run.status === "running").length;
  const queued = runs.filter((run) => run.status === "queued").length;
  return running
    ? `任务执行中${queued ? `，${queued} 条排队` : ""}`
    : queued
      ? `${queued} 条任务排队中`
      : "";
}

export function configurationIssue(
  status: string,
  settings: Record<string, any>,
  profiles: Profile[],
): string {
  if (status === "loading") return "正在读取模型与运行配置，请稍候。";
  if (status !== "ready")
    return "未能读取运行配置，请重试或前往全局设置检查连接。";
  for (const [label, id, output] of [
    ["对话", settings.default_profile_id, settings.max_output_tokens],
    [
      "摘要",
      settings.summary_profile_id || settings.default_profile_id,
      settings.summary_tokens,
    ],
  ] as const) {
    const profile = profiles.find((item) => item.id === id);
    if (!profile) return `请先在全局设置中配置并选择${label}模型。`;
    if (!profile.base_url?.trim() || !profile.model?.trim())
      return `${label}模型缺少地址或模型 ID，请补全配置。`;
    if (profile.test_status !== "connected")
      return `${label}模型连接测试未通过，请重新测试。`;
    if (!Number.isFinite(output) || output < 1)
      return `请先设置${label}模型的输出上限。`;
    const capacity = profile.context_capacity;
    if (
      !Number.isFinite(capacity) ||
      capacity <= output + Math.max(256, Math.floor(capacity * 0.05)) + 256
    )
      return `${label}模型容量不足，请调整输出上限或模型配置。`;
  }
  return "";
}

export interface ConversationItem {
  id: string;
  kind: "message" | "tools";
  rows: Message[];
}

export function conversationItems(messages: Message[]): ConversationItem[] {
  const result: ConversationItem[] = [];
  const pending = new Map<string, ConversationItem>();
  for (const row of messages) {
    if (row.message.role === "tool") {
      const item = pending.get(`${row.run_id}:${row.message.tool_call_id}`);
      if (item) item.rows.push(row);
      else result.push({ id: row.id, kind: "tools", rows: [row] });
      continue;
    }
    pending.clear();
    const calls = row.message.tool_calls || [];
    // Keep public assistant text at its original position, outside collapsed details.
    if (!calls.length || row.message.content?.trim()) {
      result.push({
        id: row.id,
        kind: "message",
        rows: [{ ...row, message: { ...row.message, tool_calls: undefined } }],
      });
    }
    for (const call of calls) {
      const item: ConversationItem = {
        id: `${row.id}:${call.id}`,
        kind: "tools",
        rows: [
          {
            ...row,
            message: { ...row.message, content: null, tool_calls: [call] },
          },
        ],
      };
      pending.set(`${row.run_id}:${call.id}`, item);
      result.push(item);
    }
  }
  return result;
}

export function contextSnapshot(events: TraceEvent[]) {
  let usage: Record<string, any> | undefined;
  for (const event of events) {
    if (event.type === "context.usage") usage = { ...event.data };
    if (event.type === "context.compacted" && usage)
      usage = { ...usage, estimated_tokens: event.data.after };
  }
  return usage;
}

export function eventLabel(type: string) {
  return (
    (
      {
        "run.updated": "任务状态",
        "model.started": "开始调用模型",
        "model.finished": "模型返回",
        "model.failed": "模型调用失败",
        "model.retry": "等待重试",
        "tool.started": "开始执行工具",
        "tool.finished": "工具执行结果",
        "context.usage": "上下文用量",
        "context.compacting": "开始压缩上下文",
        "context.compacted": "上下文压缩完成",
        "context.compaction_failed": "压缩未完成",
        "steering.updated": "用户引导",
        "message.created": "保存消息",
      } as Record<string, string>
    )[type] || type
  );
}

export function runStatus(status: string) {
  return (
    (
      {
        queued: "排队中",
        running: "执行中",
        cancelling: "停止中",
        completed: "已完成",
        cancelled: "已取消",
        failed: "失败",
        limited: "达到限制",
        interrupted: "已中断",
      } as Record<string, string>
    )[status] || status
  );
}

export function traceSteps(events: TraceEvent[]) {
  const steps = new Map<
    string,
    { id: string; label: string; events: TraceEvent[]; failed: boolean }
  >();
  for (const event of events) {
    // Text deltas are represented by saved messages; the drawer focuses on execution steps.
    if (["model.delta", "message.created"].includes(event.type)) continue;
    const family = event.type.split(".")[0];
    const key = event.data.call_id
      ? `${event.run_id}:${family}:${event.data.call_id}`
      : event.type === "run.updated"
        ? `${event.run_id}:status`
        : event.type === "steering.updated"
          ? `${event.run_id}:steering:${event.data.id}`
          : `event:${event.id}`;
    const label =
      family === "model" && event.data.call_id
        ? "模型调用"
        : family === "tool"
          ? `工具 · ${event.data.name || "调用"}`
          : eventLabel(event.type);
    const step = steps.get(key) || {
      id: key,
      label,
      events: [],
      failed: false,
    };
    step.events.push(event);
    step.failed ||=
      event.type === "model.failed" ||
      event.data.ok === false ||
      ["failed", "limited", "interrupted"].includes(event.data.status) ||
      event.type === "context.compaction_failed";
    steps.set(key, step);
  }
  return [...steps.values()];
}

// 作者：LHF。
// 注释维护时间：2026-10-20。
// 文件作用：会话状态、聊天消息和执行链路的展示数据转换。
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
  // 作用：根据最新任务状态更新会话的活跃任务概要。
  // 用最新任务状态替换侧栏记录，终态任务从活跃列表移除。
  const session = sessions.find(/* 作用：按当前标识或状态定位匹配记录，避免引用其他任务或会话。 */ (item) => item.id === run.session_id);
  if (!session) return;
  const active = (session.active_runs || []).filter(
    /* 作用：按所属任务、消息角色或状态筛选当前需要的记录。 */ (item) => item.id !== run.id,
  );
  if (["queued", "running", "cancelling"].includes(run.status))
    active.push({ id: run.id, status: run.status });
  session.active_runs = active;
}

export function sessionActivityLabel(session: Session) {
  // 作用：将运行、排队和停止状态转换为侧栏可读提示。
  const runs = session.active_runs || [];
  if (runs.some(/* 作用：检查是否存在符合当前条件的记录。 */ (run) => run.status === "cancelling")) return "正在停止任务";
  const running = runs.filter(/* 作用：按所属任务、消息角色或状态筛选当前需要的记录。 */ (run) => run.status === "running").length;
  const queued = runs.filter(/* 作用：按所属任务、消息角色或状态筛选当前需要的记录。 */ (run) => run.status === "queued").length;
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
  // 作用：检查模型配置是否就绪，返回阻止发送的具体原因。
  // 提交前的页面提示与后端容量检查保持一致；最终是否接受请求仍以后端为准。
  if (status === "loading") return "正在读取模型与运行配置，请稍候。";
  if (status !== "ready")
    return "未能读取运行配置，请重试或前往全局设置检查连接。";
  for (const [label, id] of [
    ["对话", settings.default_profile_id],
    [
      "摘要",
      settings.summary_profile_id || settings.default_profile_id,
    ],
  ] as const) {
    const profile = profiles.find(/* 作用：按当前标识或状态定位匹配记录，避免引用其他任务或会话。 */ (item) => item.id === id);
    if (!profile) return `请先在全局设置中配置并选择${label}模型。`;
    if (!profile.base_url?.trim() || !profile.model?.trim())
      return `${label}模型缺少地址或模型 ID，请补全配置。`;
    if (profile.test_status !== "connected")
      return `${label}模型连接测试未通过，请重新测试。`;
    const capacity = profile.context_capacity;
    const output = Math.max(64, Math.floor(capacity * 0.1));
    if (
      !Number.isFinite(capacity) ||
      capacity <= output + Math.max(256, Math.floor(capacity * 0.05)) + 256
    )
      return `${label}模型容量不足，请检查模型容量配置。`;
  }
  return "";
}

/** 作用：聊天区显示的一条正文消息或一组工具交互。 */
export interface ConversationItem {
  id: string;
  kind: "message" | "tools";
  rows: Message[];
}

export function conversationItems(messages: Message[]): ConversationItem[] {
  // 作用：把协议消息整理为正文气泡和可折叠工具步骤，并保留思考元数据。
  // 将原始协议消息转换成文本气泡和工具步骤，避免直接展示 role=tool 的 JSON。
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
    // 保留 assistant 正文的原始位置，不把用户可读内容藏进工具折叠区域。
    if (!calls.length || row.message.content?.trim() || row.reasoning) {
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
            reasoning: undefined,
            message: { ...row.message, content: null, tool_calls: [call] },
          },
        ],
      };
      pending.set(`${row.run_id}:${call.id}`, item);
      result.push(item);
    }
  }
  const grouped: ConversationItem[] = [];
  // 同一任务相邻的工具条目合并为步骤组，但不能跨任务混在一起。
  for (const item of result) {
    const last = grouped[grouped.length - 1];
    if (
      item.kind === "tools" &&
      last?.kind === "tools" &&
      last.rows[0]?.run_id === item.rows[0]?.run_id
    )
      last.rows.push(...item.rows);
    else grouped.push(item);
  }
  return grouped;
}

export function contextSnapshot(events: TraceEvent[]) {
  // 作用：按事件顺序还原上下文估算，压缩后使用新的用量。
  // 按事件顺序还原最后一次用量估算，压缩完成后用 after 更新显示值。
  let usage: Record<string, any> | undefined;
  for (const event of events) {
    if (event.type === "context.usage") usage = { ...event.data };
    if (event.type === "context.compacted" && usage)
      usage = { ...usage, estimated_tokens: event.data.after };
  }
  return usage;
}

export function eventLabel(type: string) {
  // 作用：将执行事件类型转换为中文名称，未知类型保留原值。
  return (
    (
      {
        "run.updated": "任务状态",
        "model.started": "开始调用模型",
        "model.context": "记录模型输入",
        "logging.status": "本地日志状态",
        "model.finished": "模型返回",
        "model.failed": "模型调用失败",
        "model.retry": "等待重试",
        "tool.started": "开始执行工具",
        "tool.finished": "工具执行结果",
        "context.usage": "上下文用量",
        "context.compacting": "开始压缩上下文",
        "context.compacted": "上下文压缩完成",
        "context.compaction_failed": "压缩未完成",
        "context.compaction_skipped": "无需压缩",
        "steering.updated": "用户引导",
        "message.created": "保存消息",
      } as Record<string, string>
    )[type] || type
  );
}

export function runStatus(status: string, reason?: string | null) {
  // 作者：LHF；时间：2026-10-21；作用：兼容 Run 契约中尚无原因时的 null。
  // 作用：将任务状态和排队转引导原因转换为可读标签。
  if (reason === "converted_to_steering") return "已转为引导";
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
  // 作用：按任务及调用 ID 聚合链路步骤，并标出失败事件。
  // 按任务、事件类别和调用 ID 聚合开始/结束事件，便于逐步查看完整执行链路。
  const steps = new Map<
    string,
    { id: string; label: string; events: TraceEvent[]; failed: boolean }
  >();
  for (const event of events) {
    // 正文已由聊天区展示，链路抽屉忽略逐字输出和消息事件，减少重复信息。
    if (["model.delta", "model.reasoning.delta", "message.created"].includes(event.type)) continue;
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

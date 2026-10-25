// 作者：LHF。
// 注释维护时间：2026-10-20。
// 文件作用：前端共享状态、HTTP 请求、SSE 连接与事件归并。
import { reactive } from "vue";
import { SSEParser } from "@/lib/sse";
import { mentionedTools } from "@/lib/tool-mentions";
import {
  configurationIssue,
  updateSessionActivity,
} from "@/lib/chat-presentation";
import type {
  Message,
  Profile,
  Run,
  Session,
  Summary,
  Todo,
  TraceEvent,
  AvailableTool,
} from "@/types/harness";

// 页面共用的响应式状态；消息和事件仅存当前会话，待办与模型配置可跨页面共享。
export const state = reactive({
  user: sessionStorage.getItem("harness-user") || "A",
  clientId: "",
  loggingError: "",
  connected: false,
  connecting: false,
  error: "",
  sessions: [] as Session[],
  selected: "",
  messages: [] as Message[],
  runs: [] as Run[],
  events: [] as TraceEvent[],
  todos: [] as Todo[],
  tools: [] as AvailableTool[],
  profiles: [] as Profile[],
  settings: {} as Record<string, any>,
  settingsStatus: "loading",
  sessionLoading: false,
  summary: null as Summary | null,
  live: {} as Record<string, { callId: string; text: string; reasoning: string }>,
});
let controller: AbortController | undefined;
// 每次初始化或切换用户增加代次，旧连接及部分旧请求的回调据此放弃更新状态。
let generation = 0;
let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
// 同一次删除可能同时收到 HTTP 返回和 SSE 通知，合并刷新以免重复创建或切换会话。
const deletionRefreshes = new Map<string, Promise<void>>();
// 记录列表请求期间到达的任务事件，防止较旧的 HTTP 快照覆盖实时状态。
const sessionSnapshots = new Set<Run[]>();
const disconnectedNotice =
  "连接已断开，当前执行和排队消息会被取消；重新连接不会自动重跑。";
let sessionsRequest = 0;

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    // 作用：保存 API 错误提示及 HTTP 状态，供界面分类处理。
    super(message);
    this.name = "ApiError";
  }
}

export async function api<T = any>(
  path: string,
  method = "GET",
  body?: unknown,
  headers?: Record<string, string>,
): Promise<T> {
  // 作用：封装带演示用户身份的 JSON 请求，将失败响应转换为包含 HTTP 状态的异常。
  // 统一补充演示用户头和 JSON 编解码；保留 HTTP 状态码供页面区分错误原因。
  const response = await fetch(`/api${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      "X-Demo-User": state.user,
      ...headers,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(/* 作用：错误响应无法解析为 JSON 时回退到 HTTP 状态提示。 */ () => ({ detail: `HTTP ${response.status}` }));
    throw new ApiError(
      typeof error.detail === "string"
        ? error.detail
        : JSON.stringify(error.detail),
      response.status,
    );
  }
  return response.json();
}

export async function safely(action: () => Promise<unknown>) {
  // 作用：执行界面异步操作，将错误统一显示到全局提示。
  // 事件回调统一把异常展示到全局提示，避免未处理的 Promise 拒绝。
  try {
    await action();
  } catch (error) {
    state.error = error instanceof Error ? error.message : String(error);
  }
}

export async function loadSessions() {
  // 作用：读取会话列表，并合并请求期间收到的任务事件，避免旧快照覆盖新状态。
  // 只接受当前用户代次中最后发起的列表请求，较早请求晚返回时直接丢弃。
  const request = ++sessionsRequest;
  const epoch = generation;
  const updates: Run[] = [];
  sessionSnapshots.add(updates);
  try {
    const sessions = await api<Session[]>("/sessions");
    if (request !== sessionsRequest || epoch !== generation) return;
    // 请求期间收到的实时事件优先于 HTTP 快照，需重新应用到新列表。
    for (const run of updates) updateSessionActivity(sessions, run);
    state.sessions = sessions;
  } finally {
    sessionSnapshots.delete(updates);
  }
}
export async function loadTodos() {
  // 作用：读取当前用户的共享待办并更新响应式列表。
  state.todos = (await api("/todos")).items;
}
export async function loadSettings() {
  // 作用：同时读取模型与运行配置，并维护配置加载状态。
  // 设置和连接配置一起就绪才开放发送，避免尚未加载时误判模型可用性。
  state.settingsStatus = "loading";
  try {
    const [settings, profiles] = await Promise.all([
      api("/settings"),
      api<Profile[]>("/models"),
    ]);
    state.settings = settings;
    state.profiles = profiles;
    state.settingsStatus = "ready";
  } catch (error) {
    state.settingsStatus = "error";
    throw error;
  }
}

export async function selectSession(id: string) {
  // 作用：切换当前会话，清空旧视图并加载消息、任务、事件和摘要。
  // 先清空旧会话视图，再恢复持久化详情；响应返回时再次确认用户仍选中此会话。
  state.selected = id;
  state.live = {};
  state.messages = [];
  state.runs = [];
  state.events = [];
  state.summary = null;
  state.sessionLoading = true;
  sessionStorage.setItem(`harness-session:${state.user}`, id);
  try {
    const result = await api(`/sessions/${id}`);
    if (state.selected !== id) return;
    state.messages = result.messages;
    state.runs = result.runs;
    state.events = result.events;
    state.summary = result.summary;
  } finally {
    if (state.selected === id) state.sessionLoading = false;
  }
}

function refreshDeletedSession(id: string): Promise<void> {
  // 作用：合并同一会话删除后的刷新请求，必要时选择或创建下一会话。
  const existing = deletionRefreshes.get(id);
  if (existing) return existing;
  const refresh = (/* 作用：刷新删除后的会话列表，再选择已有会话或创建新会话。 */ async () => {
    await loadSessions();
    if (state.selected !== id) return;
    const next = state.sessions[0];
    if (next) await selectSession(next.id);
    else await newSession();
  })();
  deletionRefreshes.set(id, refresh);
  return refresh.finally(/* 作用：异步刷新结束后清理去重索引，允许后续重新发起请求。 */ () => deletionRefreshes.delete(id));
}

export async function deleteSession(id: string) {
  // 作用：请求删除会话，并同步当前窗口的会话列表与选择。
  await api(`/sessions/${id}`, "DELETE");
  // 本窗口也会收到删除事件，只在列表尚未刷新时补做刷新。
  if (state.sessions.some(/* 作用：检查是否存在符合当前条件的记录。 */ (session) => session.id === id))
    await refreshDeletedSession(id);
}

export async function newSession() {
  // 作用：创建当前用户的新对话，刷新列表并选中它。
  const session = await api<Session>("/sessions", "POST", {
    title: `对话 ${state.sessions.length + 1}`,
  });
  await loadSessions();
  await selectSession(session.id);
}

function receive(event: TraceEvent) {
  // 作用：将 SSE 事件归并到共享状态、当前会话历史和临时流式输出。
  if (event.type === "logging.status") {
    state.loggingError = String(event.data.message || "本地日志写入异常");
    return;
  }
  // 用户级通知先更新共享状态；会话内消息、输出与链路事件仅应用到当前选中会话。
  if (event.type === "run.updated") {
    const run = event.data as unknown as Run;
    for (const updates of sessionSnapshots) updates.push(run);
    updateSessionActivity(state.sessions, run);
  }
  if (event.type === "todo.changed") void safely(loadTodos);
  if (event.type === "session.created") void safely(loadSessions);
  if (event.type === "session.deleted") {
    void safely(/* 作用：收到会话删除事件后刷新列表并切换到有效会话。 */ () => refreshDeletedSession(event.data.id));
    return;
  }
  if (event.type === "models.changed" || event.type === "settings.changed")
    void safely(loadSettings);
  if (event.session_id !== state.selected) return;
  state.events.push(event);
  if (state.events.length > 2000)
    state.events.splice(0, state.events.length - 2000);
  if (event.type === "run.updated") {
    const run = event.data as unknown as Run;
    const index = state.runs.findIndex(/* 作用：按当前标识或状态定位匹配记录，避免引用其他任务或会话。 */ (item) => item.id === run.id);
    if (index === -1) state.runs.push(run);
    else state.runs[index] = run;
    if (
      ["completed", "cancelled", "failed", "limited", "interrupted"].includes(
        run.status,
      )
    )
      delete state.live[run.id];
  }
  if (["model.delta", "model.reasoning.delta"].includes(event.type) && event.run_id) {
    // 每次模型调用独立累积流式文本，重试或下一轮调用不会接到上一轮末尾。
    const existing = state.live[event.run_id];
    const callId = String(event.data.call_id);
    if (!existing || existing.callId !== callId)
      state.live[event.run_id] = { callId, text: "", reasoning: "" };
    const field = event.type === "model.reasoning.delta" ? "reasoning" : "text";
    state.live[event.run_id]![field] += event.data.text;
  }
  if (event.type === "message.created") {
    // 正式消息落库后取代临时输出；按消息 ID 去重，避免重复展示。
    const message = event.data as unknown as Message;
    if (!state.messages.some(/* 作用：检查是否存在符合当前条件的记录。 */ (item) => item.id === message.id))
      state.messages.push(message);
    if (message.message.role === "assistant") delete state.live[message.run_id];
  }
  if (event.type === "context.compacted") {
    state.summary = {
      text: event.data.summary,
      before: event.data.before,
      after: event.data.after,
      covered: [],
    };
  }
}

async function connect(epoch: number) {
  // 作用：注册客户端并增量读取 SSE，连接断开后按当前代次重连。
  // 先登记客户端再订阅事件；收到 ready 后才允许发送，断开后按当前代次重连。
  if (epoch !== generation) return;
  state.connecting = true;
  try {
    const { client_id: clientId } = await api("/clients", "POST");
    if (epoch !== generation) return;
    state.clientId = clientId;
    controller = new AbortController();
    const response = await fetch(
      `/api/events?client_id=${encodeURIComponent(clientId)}`,
      {
        headers: { "X-Demo-User": state.user },
        signal: controller.signal,
      },
    );
    if (!response.ok || !response.body) throw new Error("执行事件连接失败");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    const parser = new SSEParser();
    while (epoch === generation) {
      const { value, done } = await reader.read();
      if (done) break;
      for (const frame of parser.push(
        decoder.decode(value, { stream: true }),
      )) {
        if (frame.event === "ready") {
          const ready = JSON.parse(frame.data || "{}");
          state.loggingError = ready.logging_error?.message || "";
          // 重连不自动重跑任务，而是重新读取服务端快照恢复最终执行状态。
          state.connected = true;
          state.connecting = false;
          await loadSessions();
          if (state.selected) await selectSession(state.selected);
          if (state.error === disconnectedNotice) state.error = "";
        } else if (frame.data) receive(JSON.parse(frame.data));
      }
    }
  } catch (error) {
    if (
      epoch === generation &&
      !(error instanceof DOMException && error.name === "AbortError")
    ) {
      state.error = disconnectedNotice;
    }
  } finally {
    if (epoch === generation) {
      state.connected = false;
      state.connecting = false;
      reconnectTimer = setTimeout(/* 作用：在重连间隔结束后仅恢复当前用户代次的事件连接。 */ () => void connect(epoch), 2000);
    }
  }
}

export async function boot() {
  // 作用：初始化共享数据，恢复用户上次选中的会话并建立事件连接。
  // 初始化共享数据、恢复当前用户上次选中的会话，最后在后台建立事件连接。
  const epoch = ++generation;
  clearTimeout(reconnectTimer);
  controller?.abort();
  state.connected = false;
  await Promise.all([loadSessions(), loadTodos(), loadSettings(), loadTools()]);
  const saved = sessionStorage.getItem(`harness-session:${state.user}`);
  if (saved && state.sessions.some(/* 作用：检查是否存在符合当前条件的记录。 */ (item) => item.id === saved))
    await selectSession(saved);
  else if (state.sessions.length) await selectSession(state.sessions[0]!.id);
  else await newSession();
  void connect(epoch);
}

export async function switchUser(user: string) {
  // 作用：关闭旧用户连接、清理旧会话状态，再加载新用户的数据。
  // 主动断开旧客户端让后端取消其任务，再清空视图并初始化新用户的数据。
  if (user === state.user) return;
  if (state.clientId)
    await safely(/* 作用：切换用户前主动断开旧客户端，并由后端取消其任务。 */ () => api(`/clients/${state.clientId}/disconnect`, "POST"));
  generation++;
  controller?.abort();
  clearTimeout(reconnectTimer);
  state.user = user;
  state.selected = "";
  state.messages = [];
  state.runs = [];
  state.events = [];
  state.live = {};
  sessionStorage.setItem("harness-user", user);
  await boot();
}

export async function send(content: string, steeringRunId?: string) {
  // 作用：校验发送条件，提取工具提及，并提交聊天任务或运行引导。
  // 发送前检查配置与连接；普通消息入队，带任务 ID 的消息作为运行中的引导提交。
  const issue = configurationIssue(
    state.settingsStatus,
    state.settings,
    state.profiles,
  );
  if (issue) throw new Error(issue);
  if (!state.selected || state.sessionLoading)
    throw new Error("请等待对话加载完成");
  if (!state.connected) throw new Error("请等待事件连接就绪");
  const requestId = crypto.randomUUID();
  const toolNames = mentionedTools(content, state.tools);
  if (steeringRunId)
    await api(`/runs/${steeringRunId}/steering`, "POST", {
      content,
      request_id: requestId,
      tool_names: toolNames,
    });
  else
    await api(`/sessions/${state.selected}/messages`, "POST", {
      content,
      client_id: state.clientId,
      request_id: requestId,
      tool_names: toolNames,
    });
}

export async function changeTodo(body: Record<string, unknown>) {
  // 作用：使用唯一幂等键提交手动待办操作，成功后重新读取列表。
  // 每次手动操作生成幂等键；成功后读取服务端结果，不在本地猜测写入结果。
  await api("/todos", "POST", body, { "Idempotency-Key": crypto.randomUUID() });
  await loadTodos();
}

async function loadTools() {
  // 作用：从后端注册表读取可调用工具，供输入框提及菜单使用。
  // 不硬编码工具清单，菜单与服务端实际可执行能力保持一致。
  state.tools = await api<AvailableTool[]>("/tools");
}

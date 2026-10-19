import { reactive } from "vue";
import { SSEParser } from "@/lib/sse";
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
} from "@/types/harness";

export const state = reactive({
  user: sessionStorage.getItem("harness-user") || "A",
  clientId: "",
  connected: false,
  connecting: false,
  error: "",
  sessions: [] as Session[],
  selected: "",
  messages: [] as Message[],
  runs: [] as Run[],
  events: [] as TraceEvent[],
  todos: [] as Todo[],
  profiles: [] as Profile[],
  settings: {} as Record<string, any>,
  settingsStatus: "loading",
  sessionLoading: false,
  summary: null as Summary | null,
  live: {} as Record<string, { callId: string; text: string }>,
});
let controller: AbortController | undefined;
let generation = 0;
let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
const deletionRefreshes = new Map<string, Promise<void>>();
const sessionSnapshots = new Set<Run[]>();
let sessionsRequest = 0;

export async function api<T = any>(
  path: string,
  method = "GET",
  body?: unknown,
  headers?: Record<string, string>,
): Promise<T> {
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
      .catch(() => ({ detail: `HTTP ${response.status}` }));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : JSON.stringify(error.detail),
    );
  }
  return response.json();
}

export async function safely(action: () => Promise<unknown>) {
  try {
    await action();
  } catch (error) {
    state.error = error instanceof Error ? error.message : String(error);
  }
}

export async function loadSessions() {
  const request = ++sessionsRequest;
  const epoch = generation;
  const updates: Run[] = [];
  sessionSnapshots.add(updates);
  try {
    const sessions = await api<Session[]>("/sessions");
    if (request !== sessionsRequest || epoch !== generation) return;
    // Events received while fetching must win over an older HTTP snapshot.
    for (const run of updates) updateSessionActivity(sessions, run);
    state.sessions = sessions;
  } finally {
    sessionSnapshots.delete(updates);
  }
}
export async function loadTodos() {
  state.todos = (await api("/todos")).items;
}
export async function loadSettings() {
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
  const existing = deletionRefreshes.get(id);
  if (existing) return existing;
  const refresh = (async () => {
    await loadSessions();
    if (state.selected !== id) return;
    const next = state.sessions[0];
    if (next) await selectSession(next.id);
    else await newSession();
  })();
  deletionRefreshes.set(id, refresh);
  return refresh.finally(() => deletionRefreshes.delete(id));
}

export async function deleteSession(id: string) {
  await api(`/sessions/${id}`, "DELETE");
  // The SSE notification also reaches this window; refresh only once after removal.
  if (state.sessions.some((session) => session.id === id))
    await refreshDeletedSession(id);
}

export async function newSession() {
  const session = await api<Session>("/sessions", "POST", {
    title: `对话 ${state.sessions.length + 1}`,
  });
  await loadSessions();
  await selectSession(session.id);
}

function receive(event: TraceEvent) {
  if (event.type === "run.updated") {
    const run = event.data as unknown as Run;
    for (const updates of sessionSnapshots) updates.push(run);
    updateSessionActivity(state.sessions, run);
  }
  if (event.type === "todo.changed") void safely(loadTodos);
  if (event.type === "session.created") void safely(loadSessions);
  if (event.type === "session.deleted") {
    void safely(() => refreshDeletedSession(event.data.id));
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
    const index = state.runs.findIndex((item) => item.id === run.id);
    if (index === -1) state.runs.push(run);
    else state.runs[index] = run;
    if (
      ["completed", "cancelled", "failed", "limited", "interrupted"].includes(
        run.status,
      )
    )
      delete state.live[run.id];
  }
  if (event.type === "model.delta" && event.run_id) {
    const existing = state.live[event.run_id];
    const callId = String(event.data.call_id);
    if (!existing || existing.callId !== callId)
      state.live[event.run_id] = { callId, text: "" };
    state.live[event.run_id]!.text += event.data.text;
  }
  if (event.type === "message.created") {
    const message = event.data as unknown as Message;
    if (!state.messages.some((item) => item.id === message.id))
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
          state.connected = true;
          state.connecting = false;
          await loadSessions();
          if (state.selected) await selectSession(state.selected);
        } else if (frame.data) receive(JSON.parse(frame.data));
      }
    }
  } catch (error) {
    if (
      epoch === generation &&
      !(error instanceof DOMException && error.name === "AbortError")
    ) {
      state.error =
        "连接已断开，当前执行和排队消息会被取消；重新连接不会自动重跑。";
    }
  } finally {
    if (epoch === generation) {
      state.connected = false;
      state.connecting = false;
      reconnectTimer = setTimeout(() => void connect(epoch), 2000);
    }
  }
}

export async function boot() {
  const epoch = ++generation;
  clearTimeout(reconnectTimer);
  controller?.abort();
  state.connected = false;
  await Promise.all([loadSessions(), loadTodos(), loadSettings()]);
  const saved = sessionStorage.getItem(`harness-session:${state.user}`);
  if (saved && state.sessions.some((item) => item.id === saved))
    await selectSession(saved);
  else if (state.sessions.length) await selectSession(state.sessions[0]!.id);
  else await newSession();
  void connect(epoch);
}

export async function switchUser(user: string) {
  if (user === state.user) return;
  if (state.clientId)
    await safely(() => api(`/clients/${state.clientId}/disconnect`, "POST"));
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
  if (steeringRunId)
    await api(`/runs/${steeringRunId}/steering`, "POST", {
      content,
      request_id: requestId,
    });
  else
    await api(`/sessions/${state.selected}/messages`, "POST", {
      content,
      client_id: state.clientId,
      request_id: requestId,
    });
}

export async function changeTodo(body: Record<string, unknown>) {
  await api("/todos", "POST", body, { "Idempotency-Key": crypto.randomUUID() });
  await loadTodos();
}

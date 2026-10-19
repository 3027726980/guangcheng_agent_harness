<template>
  <div class="chat-shell">
    <aside class="session-panel">
      <n-button block type="primary" secondary @click="safely(newSession)"
        >＋ 新对话</n-button
      >
      <div class="section-label">当前用户的独立会话</div>
      <button
        v-for="session in state.sessions"
        :key="session.id"
        class="session-row"
        :class="{ selected: state.selected === session.id }"
        @click="safely(() => selectSession(session.id))"
      >
        {{ session.title }}<small>{{ session.id.slice(0, 8) }}</small>
      </button>
      <p class="hint">不同会话可同时执行；聊天独立，待办共享。</p>
    </aside>

    <section class="conversation">
      <div class="conversation-toolbar">
        <div>
          <strong>{{ currentTitle }}</strong
          ><small>从零实现的 Agent Runtime</small>
        </div>
        <n-space
          ><n-tag
            :type="state.connected ? 'success' : 'warning'"
            size="small"
            >{{ state.connected ? "已连接" : "正在连接" }}</n-tag
          >
          <n-button size="small" @click="traceOpen = true"
            >查看完整链路</n-button
          >
          <n-button size="small" @click="todosOpen = !todosOpen">{{
            todosOpen ? "收起待办" : "共享待办"
          }}</n-button></n-space
        >
      </div>
      <div v-if="contextUsage" class="context-strip">
        Context 估算 {{ number(contextUsage.estimated_tokens) }} /
        {{ number(contextUsage.capacity) }}
        <span
          >{{
            String(contextUsage.source).startsWith("default")
              ? "默认容量 256K"
              : "供应商容量"
          }}
          · 保守估算</span
        >
        <n-button text size="tiny" @click="summaryOpen = !summaryOpen">{{
          summaryOpen ? "收起摘要" : "查看摘要"
        }}</n-button>
      </div>
      <n-alert
        v-if="summaryOpen"
        type="info"
        :show-icon="false"
        class="summary-box"
        >{{
          state.summary?.text ||
          "尚未生成摘要。达到阈值后自动整理，原历史保留。"
        }}</n-alert
      >
      <div ref="scrollArea" class="messages">
        <div v-if="!state.messages.length" class="empty-chat">
          <div class="eyebrow">AGENT HARNESS</div>
          <h1>把任务交给 Agent。</h1>
          <p>它会自行决定是否调用工具。每一步都有记录。</p>
          <div class="prompt-examples">
            <button
              v-for="example in examples"
              :key="example"
              @click="input = example"
            >
              {{ example }}
            </button>
          </div>
        </div>
        <article
          v-for="row in state.messages"
          :key="row.id"
          class="message"
          :class="row.message.role"
        >
          <div class="message-label">
            {{
              row.message.role === "user"
                ? row.input_kind === "steering"
                  ? "你 · 引导"
                  : "你"
                : row.message.role === "tool"
                  ? "工具结果"
                  : "Agent"
            }}
          </div>
          <template v-if="row.message.role === 'tool'">
            <details class="tool-result">
              <summary>{{ toolLabel(row.message.content) }}</summary>
              <pre>{{ pretty(row.message.content) }}</pre>
            </details>
          </template>
          <template v-else>
            <div v-if="row.message.content" class="message-text">
              {{ row.message.content }}
            </div>
            <details v-if="row.message.tool_calls?.length" class="tool-result">
              <summary>请求 {{ row.message.tool_calls.length }} 个工具</summary>
              <pre>{{ JSON.stringify(row.message.tool_calls, null, 2) }}</pre>
            </details>
          </template>
        </article>
        <article
          v-for="(live, runId) in state.live"
          :key="runId"
          class="message assistant"
        >
          <div class="message-label">Agent · 正在输出</div>
          <div class="message-text">
            {{ live.text }}<span class="cursor">▍</span>
          </div>
        </article>
        <div v-if="activeRun" class="activity-line">
          <span class="activity-dot" />{{ activityText }}
        </div>
        <div v-for="run in historicalProblems" :key="run.id" class="run-note">
          <strong>{{ statusLabel(run.status) }}</strong> · {{ run.content
          }}<br /><small>{{ reasonLabel(run.reason) }}</small>
        </div>
      </div>
      <div v-if="queued.length" class="queue-strip">
        <strong>等待执行 {{ queued.length }} 条</strong>
        <div v-for="run in queued" :key="run.id">{{ run.content }}</div>
      </div>
      <div v-if="pendingSteering.length" class="queue-strip steering-strip">
        等待生效的引导：
        <div v-for="item in pendingSteering" :key="item.id">
          {{ item.data.content }}
        </div>
      </div>
      <form class="composer" @submit.prevent="submit(false)">
        <n-input
          v-model:value="input"
          type="textarea"
          placeholder="输入任务。运行时普通消息排队，也可以选择引导当前任务。"
          :autosize="{ minRows: 2, maxRows: 8 }"
          :disabled="sending"
          @keydown="onKeydown"
        />
        <div class="composer-actions">
          <span>Enter 发送 · Shift+Enter 换行</span
          ><n-space>
            <n-button
              v-if="activeRun"
              type="error"
              secondary
              :disabled="activeRun.status === 'cancelling'"
              @click="stop"
              >停止</n-button
            >
            <n-button
              v-if="activeRun?.status === 'running'"
              :disabled="!input.trim() || !state.connected || sending"
              @click="submit(true)"
              >引导</n-button
            >
            <n-button
              type="primary"
              attr-type="submit"
              :loading="sending"
              :disabled="!input.trim() || !state.connected"
              >{{ activeRun ? "加入队列" : "发送" }}</n-button
            >
          </n-space>
        </div>
      </form>
    </section>

    <aside v-if="todosOpen" class="todo-panel">
      <div class="panel-title">
        <strong>共享待办</strong
        ><n-tag size="small">用户 {{ state.user }}</n-tag>
      </div>
      <p class="hint">同一用户跨会话共享，Agent 与手动操作使用同一份数据。</p>
      <n-input
        v-model:value="todoTitle"
        placeholder="新增待办标题"
        @keyup.enter="addTodo"
      />
      <n-button
        block
        secondary
        type="primary"
        :disabled="!todoTitle.trim()"
        @click="addTodo"
        >添加待办</n-button
      >
      <div v-if="!state.todos.length" class="todo-empty">
        还没有待办，试试让 Agent 帮你记录。
      </div>
      <div v-for="todo in state.todos" :key="todo.id" class="todo-item">
        <n-checkbox
          :checked="todo.status === 'completed'"
          @update:checked="(checked) => toggleTodo(todo, checked)"
        />
        <div>
          <span :class="{ done: todo.status === 'completed' }">{{
            todo.title
          }}</span
          ><small>v{{ todo.version }} · {{ todo.id.slice(0, 8) }}</small>
          <p v-if="todo.notes">{{ todo.notes }}</p>
          <n-space size="small"
            ><n-button text size="tiny" @click="editTodo(todo)">编辑</n-button
            ><n-button text size="tiny" type="error" @click="removeTodo(todo)"
              >删除</n-button
            ></n-space
          >
        </div>
      </div>
    </aside>
  </div>
  <n-drawer
    v-model:show="traceOpen"
    width="min(720px, 100vw)"
    placement="right"
  >
    <n-drawer-content title="完整执行链路" closable>
      <p class="hint">
        模型调用、工具、重试、Context 压缩、引导与取消。参数按实际执行记录展示。
      </p>
      <div v-for="event in traceEvents" :key="event.id" class="trace-event">
        <div>
          <strong>{{ event.type }}</strong
          ><small
            >{{ new Date(event.timestamp * 1000).toLocaleTimeString() }} ·
            {{ event.run_id?.slice(0, 8) }}</small
          >
        </div>
        <pre>{{ JSON.stringify(event.data, null, 2) }}</pre>
      </div>
    </n-drawer-content>
  </n-drawer>
  <n-modal
    v-model:show="editOpen"
    preset="card"
    title="编辑待办"
    style="width: min(460px, 95vw)"
  >
    <n-space vertical
      ><n-input v-model:value="editTitle" placeholder="标题" /><n-input
        v-model:value="editNotes"
        type="textarea"
        placeholder="备注"
      /><n-button type="primary" @click="saveTodo">保存修改</n-button></n-space
    >
  </n-modal>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import {
  NAlert,
  NButton,
  NCheckbox,
  NDrawer,
  NDrawerContent,
  NInput,
  NModal,
  NSpace,
  NTag,
} from "naive-ui";
import {
  api,
  changeTodo,
  loadTodos,
  newSession,
  safely,
  selectSession,
  send,
  state,
} from "@/api/harness";
import type { Todo } from "@/types/harness";

const input = ref(""),
  sending = ref(false),
  traceOpen = ref(false),
  todosOpen = ref(true),
  summaryOpen = ref(false);
const todoTitle = ref(""),
  editOpen = ref(false),
  editTitle = ref(""),
  editNotes = ref("");
const editing = ref<Todo | null>(null),
  scrollArea = ref<HTMLElement | null>(null);
const examples = [
  "计算 128 × 36，并把结果记入待办。",
  "搜索 Python 学习资料，制定每天30分钟的计划并记入待办。",
  "查看我的待办。",
];
const currentTitle = computed(
  () =>
    state.sessions.find((item) => item.id === state.selected)?.title ||
    "新对话",
);
const activeRun = computed(() =>
  state.runs.find((run) => ["running", "cancelling"].includes(run.status)),
);
const queued = computed(() =>
  state.runs.filter((run) => run.status === "queued"),
);
const historicalProblems = computed(() =>
  state.runs.filter((run) =>
    ["cancelled", "failed", "limited", "interrupted"].includes(run.status),
  ),
);
const traceEvents = computed(() =>
  state.events.filter((event) => event.type !== "model.delta"),
);
const contextUsage = computed(
  () =>
    [...state.events].reverse().find((event) => event.type === "context.usage")
      ?.data,
);
const pendingSteering = computed(() => {
  const latest = new Map<string, (typeof state.events)[number]>();
  state.events
    .filter((event) => event.type === "steering.updated")
    .forEach((event) => latest.set(event.data.id, event));
  return [...latest.values()].filter(
    (event) =>
      event.data.status === "pending" && event.run_id === activeRun.value?.id,
  );
});
const activityText = computed(() => {
  const event = [...state.events]
    .reverse()
    .find(
      (item) =>
        item.run_id === activeRun.value?.id && item.type !== "model.delta",
    );
  if (activeRun.value?.status === "cancelling")
    return "正在停止并核对已执行结果…";
  if (event?.type === "model.retry")
    return `等待 ${event.data.delay_seconds} 秒后重试（第 ${event.data.retry} 次）`;
  if (event?.type === "context.compacting") return "正在整理上下文…";
  if (event?.type === "tool.started") return `正在执行 ${event.data.name}…`;
  return "Agent 正在处理…";
});
function number(value: unknown) {
  return Number(value || 0).toLocaleString();
}
function pretty(content: string | null) {
  try {
    return JSON.stringify(JSON.parse(content || "{}"), null, 2);
  } catch {
    return content;
  }
}
function toolLabel(content: string | null) {
  try {
    const result = JSON.parse(content || "{}");
    return result.ok
      ? "工具执行成功 · 展开结果"
      : `工具未成功 · ${result.error?.message || "查看详情"}`;
  } catch {
    return "查看工具结果";
  }
}
function statusLabel(status: string) {
  return (
    (
      {
        cancelled: "已取消",
        failed: "执行失败",
        limited: "达到限制",
        interrupted: "执行中断",
      } as Record<string, string>
    )[status] || status
  );
}
function reasonLabel(reason?: string) {
  return (
    (
      {
        user_stop: "已被用户手动停止",
        client_disconnect: "连接断开，执行与队列已取消",
        server_restart: "服务重启，未自动重放",
      } as Record<string, string>
    )[reason || ""] || reason
  );
}
async function submit(steering: boolean) {
  const content = input.value.trim();
  if (!content || sending.value) return;
  sending.value = true;
  await safely(async () => {
    await send(content, steering ? activeRun.value?.id : undefined);
    input.value = "";
  });
  sending.value = false;
}
function onKeydown(event: KeyboardEvent) {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    void submit(false);
  }
}
function stop() {
  if (activeRun.value)
    void safely(() => api(`/runs/${activeRun.value!.id}/cancel`, "POST"));
}
async function addTodo() {
  if (!todoTitle.value.trim()) return;
  await safely(async () => {
    await changeTodo({ action: "add", title: todoTitle.value.trim() });
    todoTitle.value = "";
  });
}
function toggleTodo(todo: Todo, checked: boolean) {
  void safely(async () => {
    try {
      await changeTodo({
        action: "update",
        todo_id: todo.id,
        expected_version: todo.version,
        status: checked ? "completed" : "pending",
      });
    } finally {
      await loadTodos();
    }
  });
}
function removeTodo(todo: Todo) {
  void safely(async () => {
    try {
      await changeTodo({
        action: "delete",
        todo_id: todo.id,
        expected_version: todo.version,
      });
    } finally {
      await loadTodos();
    }
  });
}
function editTodo(todo: Todo) {
  editing.value = todo;
  editTitle.value = todo.title;
  editNotes.value = todo.notes;
  editOpen.value = true;
}
async function saveTodo() {
  if (!editing.value) return;
  await safely(async () => {
    try {
      await changeTodo({
        action: "update",
        todo_id: editing.value!.id,
        expected_version: editing.value!.version,
        title: editTitle.value,
        notes: editNotes.value,
      });
      editOpen.value = false;
    } finally {
      await loadTodos();
    }
  });
}
watch(
  () => [
    state.messages.length,
    Object.values(state.live)
      .map((item) => item.text)
      .join(""),
  ],
  async () => {
    await nextTick();
    if (scrollArea.value)
      scrollArea.value.scrollTop = scrollArea.value.scrollHeight;
  },
);
</script>

<style scoped>
.chat-shell {
  display: flex;
  height: calc(100dvh - 105px);
  min-height: 500px;
  gap: 16px;
}
.session-panel {
  width: 175px;
  flex-shrink: 0;
  padding-top: 8px;
}
.section-label {
  font-size: 11px;
  color: #82908d;
  margin: 22px 8px 10px;
  letter-spacing: 0.07em;
}
.session-row {
  display: block;
  width: 100%;
  border: 0;
  background: transparent;
  text-align: left;
  padding: 12px;
  border-radius: 9px;
  color: #47564f;
  cursor: pointer;
  margin-bottom: 4px;
}
.session-row.selected {
  background: #e2eee7;
  color: #176143;
  font-weight: 600;
}
small {
  display: block;
  color: #84918b;
  font-size: 11px;
  margin-top: 4px;
}
.conversation {
  background: white;
  border: 1px solid #e2e8e3;
  border-radius: 16px;
  display: flex;
  flex: 1;
  min-width: 0;
  flex-direction: column;
  overflow: hidden;
}
.conversation-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #edf0ed;
  gap: 12px;
}
.messages {
  flex: 1;
  overflow: auto;
  padding: 24px;
}
.empty-chat {
  max-width: 580px;
  margin: 8vh auto;
  text-align: center;
}
.eyebrow {
  font-size: 11px;
  letter-spacing: 0.2em;
  color: #558b71;
  margin-bottom: 14px;
}
.empty-chat h1 {
  font-size: 30px;
  font-weight: 600;
  letter-spacing: -0.04em;
  color: #223b2d;
}
.empty-chat p {
  color: #819087;
  margin: 12px 0 28px;
}
.prompt-examples {
  display: flex;
  flex-direction: column;
  gap: 9px;
}
.prompt-examples button {
  border: 1px solid #e1e8e2;
  border-radius: 10px;
  background: #f8faf7;
  padding: 13px 18px;
  text-align: left;
  color: #4b6052;
  cursor: pointer;
}
.message {
  max-width: 90%;
  margin-bottom: 22px;
}
.message.user {
  margin-left: auto;
  background: #edf4ee;
  border-radius: 13px;
  padding: 13px 16px;
}
.message-label {
  font-size: 11px;
  color: #829188;
  margin-bottom: 7px;
}
.message-text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.85;
  font-size: 14px;
  color: #263d30;
}
.tool-result {
  border: 1px solid #e0e7e2;
  border-radius: 8px;
  background: #f8faf8;
  padding: 10px;
  margin-top: 8px;
  font-size: 12px;
}
.tool-result summary {
  cursor: pointer;
  color: #51745c;
}
pre {
  font-size: 11px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.65;
  max-height: 360px;
  overflow: auto;
  margin-top: 8px;
}
.composer {
  padding: 16px 20px;
  border-top: 1px solid #edf0ed;
}
.composer-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
  gap: 8px;
}
.composer-actions > span {
  font-size: 11px;
  color: #95a097;
}
.todo-panel {
  width: 245px;
  flex-shrink: 0;
  padding: 12px 0;
}
.panel-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.hint {
  font-size: 11px;
  color: #829087;
  line-height: 1.8;
  margin: 12px 0;
}
.todo-panel > .n-button {
  margin-top: 8px;
}
.todo-empty {
  padding: 30px 5px;
  color: #93a095;
  font-size: 12px;
  line-height: 1.8;
}
.todo-item {
  display: flex;
  gap: 10px;
  padding: 15px 0;
  border-bottom: 1px solid #e3e9e3;
}
.todo-item > div {
  min-width: 0;
  overflow-wrap: anywhere;
  font-size: 13px;
}
.todo-item p {
  color: #829087;
  font-size: 11px;
  margin: 6px 0;
}
.done {
  text-decoration: line-through;
  color: #99a39b;
}
.context-strip {
  padding: 8px 20px;
  background: #f7f9f4;
  color: #78906e;
  font-size: 11px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.context-strip span {
  color: #96a08e;
}
.summary-box {
  margin: 8px 20px;
  white-space: pre-wrap;
}
.queue-strip {
  font-size: 12px;
  padding: 10px 20px;
  background: #fff8e9;
  color: #8b733e;
  max-height: 110px;
  overflow: auto;
}
.queue-strip div {
  margin-top: 4px;
}
.steering-strip {
  background: #edf5f4;
  color: #497d75;
}
.run-note {
  font-size: 12px;
  padding: 12px;
  background: #faf4ed;
  border-radius: 8px;
  margin: 12px 0;
  color: #8b725a;
}
.trace-event {
  padding: 15px 0;
  border-bottom: 1px solid #e7ebe7;
}
.trace-event strong {
  font-size: 12px;
  color: #52725c;
}
.activity-line {
  font-size: 12px;
  color: #738b7b;
  display: flex;
  align-items: center;
  gap: 8px;
}
.activity-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #56a174;
}
.cursor {
  color: #56866b;
  animation: blink 1s infinite;
}
@keyframes blink {
  50% {
    opacity: 0;
  }
}
@media (max-width: 1200px) {
  .todo-panel {
    width: 210px;
  }
  .session-panel {
    width: 145px;
  }
}
@media (max-width: 900px) {
  .chat-shell {
    flex-wrap: wrap;
    height: auto;
  }
  .conversation {
    min-height: 70dvh;
  }
  .todo-panel {
    width: 100%;
  }
  .session-panel {
    width: 100%;
    display: flex;
    gap: 8px;
    overflow: auto;
  }
  .session-panel > .n-button {
    width: auto;
  }
  .session-row {
    min-width: 130px;
  }
  .session-panel .hint,
  .section-label {
    display: none;
  }
  .conversation-toolbar {
    flex-wrap: wrap;
  }
  .composer-actions > span {
    display: none;
  }
  .message {
    max-width: 100%;
  }
  .messages {
    max-height: 60dvh;
  }
}
</style>

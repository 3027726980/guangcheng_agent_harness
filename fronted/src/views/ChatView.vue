<template>
  <div class="chat-shell">
    <aside class="session-panel">
      <n-button block type="primary" secondary @click="safely(newSession)"
        >＋ 新对话</n-button
      >
      <div class="section-label">当前用户的独立会话</div>
      <div
        v-for="session in state.sessions"
        :key="session.id"
        class="session-row"
        :class="{ selected: state.selected === session.id }"
      >
        <button
          class="session-select"
          @click="safely(() => selectSession(session.id))"
        >
          {{ session.title }}<small>{{ session.id.slice(0, 8) }}</small>
        </button>
        <span
          v-if="sessionActivityLabel(session)"
          class="session-spinner"
          role="status"
          :aria-label="`${session.title}：${sessionActivityLabel(session)}`"
          :title="sessionActivityLabel(session)"
        />
        <n-popconfirm
          @positive-click="safely(() => deleteSession(session.id))"
          positive-text="删除"
          negative-text="保留"
        >
          <template #trigger
            ><button
              class="session-delete"
              :aria-label="`删除对话 ${session.title}`"
              title="删除对话"
            >
              ×
            </button></template
          >
          删除此对话？共享待办会保留；运行或排队中的任务需要先停止。
        </n-popconfirm>
      </div>
      <p class="hint">不同会话可同时执行；聊天独立，待办共享。</p>
    </aside>

    <section class="conversation">
      <div class="conversation-toolbar">
        <div>
          <strong>{{ currentTitle }}</strong
          ><small>从零实现的 Agent Runtime</small>
        </div>
        <n-space
          ><ConnectionStatus
            :connected="state.connected"
            :connecting="state.connecting"
            :settings-status="state.settingsStatus"
            :model-issue="setupIssue"
          />
          <n-button size="small" @click="traceOpen = true"
            >查看完整链路</n-button
          >
          <n-button size="small" @click="todosOpen = !todosOpen">{{
            todosOpen ? "收起待办" : "共享待办"
          }}</n-button></n-space
        >
      </div>
      <n-alert
        v-if="setupIssue"
        type="warning"
        class="setup-alert"
        :show-icon="false"
      >
        {{ setupIssue }}
        <div class="setup-actions">
          <n-button size="small" @click="router.push('/settings')"
            >前往设置</n-button
          >
          <n-button
            v-if="state.settingsStatus === 'error'"
            size="small"
            @click="safely(boot)"
            >重试读取</n-button
          >
        </div>
      </n-alert>
      <n-alert
        v-if="summaryOpen"
        type="info"
        title="历史摘要"
        closable
        @close="summaryOpen = false"
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
        <template v-for="item in visibleMessages" :key="item.id">
          <ToolSteps v-if="item.kind === 'tools'" :rows="item.rows" />
          <article v-else class="message" :class="item.rows[0]!.message.role">
            <div class="message-label">
              {{
                item.rows[0]!.message.role === "user"
                  ? item.rows[0]!.input_kind === "steering"
                    ? "你 · 引导"
                    : "你"
                  : "Agent"
              }}
            </div>
            <div v-if="item.rows[0]!.message.content" class="message-text">
              {{ item.rows[0]!.message.content }}
            </div>
          </article>
        </template>
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
        <n-alert
          v-for="run in historicalProblems"
          :key="run.id"
          class="run-note"
          type="warning"
          :show-icon="false"
          closable
          @close="dismissProblem(run.id)"
        >
          <strong>{{ statusLabel(run.status) }}</strong> · {{ run.content
          }}<br /><small>{{ reasonLabel(run.reason) }}</small>
        </n-alert>
      </div>
      <div v-if="queued.length || pendingSteering.length" class="queue-strip">
        <template v-if="queued.length">
          <strong>等待执行 {{ queued.length }} 条</strong>
          <div v-for="run in queued" :key="run.id" class="queue-row">
            <div class="queue-content">{{ run.content }}</div>
            <div class="queue-actions">
              <n-button
                size="tiny"
                :loading="promoting === run.id"
                :disabled="
                  activeRun?.status !== 'running' ||
                  !state.connected ||
                  !!promoting
                "
                @click="promoteQueued(run.id)"
                >引导</n-button
              >
              <n-button
                text
                size="tiny"
                @click="safely(() => api(`/runs/${run.id}/cancel`, 'POST'))"
                >取消排队</n-button
              >
            </div>
          </div>
        </template>
        <div
          v-for="item in pendingSteering"
          :key="item.id"
          class="queue-row steering-row"
        >
          <div class="queue-content">{{ item.data.content }}</div>
          <span class="queue-status">引导待生效</span>
        </div>
      </div>
      <form class="composer" @submit.prevent="submit()">
        <n-input
          v-model:value="input"
          type="textarea"
          placeholder="输入任务。运行中发送会排队，可在队列消息旁点击引导。"
          :autosize="{ minRows: 2, maxRows: 8 }"
          :disabled="sending"
          @keydown="onKeydown"
        />
        <div class="composer-actions">
          <span>Enter 发送 · Shift+Enter 换行</span
          ><n-space align="center" :size="8">
            <n-button
              v-if="activeRun"
              type="error"
              secondary
              :disabled="activeRun.status === 'cancelling'"
              @click="stop"
              >停止</n-button
            >
            <ContextMeter
              :usage="contextUsage"
              :capacity="selectedProfile?.context_capacity || 0"
              :source="selectedProfile?.capacity_source || ''"
              @summary="summaryOpen = true"
            />
            <n-button
              type="primary"
              attr-type="submit"
              :loading="sending"
              :disabled="!canSend || !input.trim() || sending"
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
        :input-props="{ 'aria-label': '新增待办标题' }"
        :maxlength="200"
        :disabled="todoSaving"
        @keyup.enter="addTodo"
      />
      <n-input
        v-model:value="todoNotes"
        type="textarea"
        placeholder="待办内容（可选）"
        :input-props="{ 'aria-label': '待办内容' }"
        :autosize="{ minRows: 2, maxRows: 5 }"
        :maxlength="4000"
        :disabled="todoSaving"
        show-count
        class="todo-content-input"
      />
      <n-button
        block
        secondary
        type="primary"
        :disabled="!todoTitle.trim() || todoSaving"
        :loading="todoSaving"
        @click="addTodo"
        >添加待办</n-button
      >
      <div v-if="!state.todos.length" class="todo-empty">
        还没有待办，试试让 Agent 帮你记录。
      </div>
      <div v-for="todo in state.todos" :key="todo.id" class="todo-item">
        <n-checkbox
          class="todo-checkbox"
          :aria-label="`完成待办：${todo.title}`"
          :checked="todo.status === 'completed'"
          @update:checked="(checked) => toggleTodo(todo, checked)"
        />
        <div class="todo-body">
          <span
            class="todo-title"
            :class="{ done: todo.status === 'completed' }"
            >{{ todo.title }}</span
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
      <TracePanel
        v-if="traceOpen"
        :key="state.selected"
        :runs="state.runs"
        :events="state.events"
      />
    </n-drawer-content>
  </n-drawer>
  <n-modal
    v-model:show="editOpen"
    preset="card"
    title="编辑待办"
    style="width: min(460px, 95vw)"
  >
    <n-space vertical
      ><n-input
        v-model:value="editTitle"
        placeholder="标题"
        :maxlength="200"
      /><n-input
        v-model:value="editNotes"
        type="textarea"
        placeholder="内容（可选）"
        :input-props="{ 'aria-label': '编辑待办内容' }"
        :maxlength="4000"
      /><n-button type="primary" @click="saveTodo">保存修改</n-button></n-space
    >
  </n-modal>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  NAlert,
  NButton,
  NCheckbox,
  NDrawer,
  NDrawerContent,
  NInput,
  NModal,
  NPopconfirm,
  NSpace,
  NTag,
} from "naive-ui";
import {
  api,
  boot,
  changeTodo,
  deleteSession,
  loadTodos,
  newSession,
  safely,
  selectSession,
  send,
  state,
} from "@/api/harness";
import type { Todo } from "@/types/harness";
import ContextMeter from "@/components/ContextMeter.vue";
import ConnectionStatus from "@/components/ConnectionStatus.vue";
import ToolSteps from "@/components/ToolSteps.vue";
import TracePanel from "@/components/TracePanel.vue";
import {
  configurationIssue,
  contextSnapshot,
  conversationItems,
  sessionActivityLabel,
} from "@/lib/chat-presentation";

const router = useRouter();
const input = ref(""),
  sending = ref(false),
  promoting = ref(""),
  traceOpen = ref(false),
  todosOpen = ref(true),
  summaryOpen = ref(false);
const todoTitle = ref(""),
  todoNotes = ref(""),
  todoSaving = ref(false),
  editOpen = ref(false),
  editTitle = ref(""),
  editNotes = ref("");
const editing = ref<Todo | null>(null),
  scrollArea = ref<HTMLElement | null>(null);
const dismissedProblems = ref<string[]>([]);
const problemStorageKey = () =>
  `harness-dismissed-runs:${state.user}:${state.selected}`;
function dismissProblem(id: string) {
  dismissedProblems.value = [...new Set([...dismissedProblems.value, id])];
  try {
    sessionStorage.setItem(
      problemStorageKey(),
      JSON.stringify(dismissedProblems.value),
    );
  } catch {
    /* Dismissal still works if storage is unavailable. */
  }
}
watch(
  () => [state.user, state.selected],
  () => {
    try {
      const saved = JSON.parse(
        sessionStorage.getItem(problemStorageKey()) || "[]",
      );
      dismissedProblems.value = Array.isArray(saved)
        ? saved.filter((id): id is string => typeof id === "string")
        : [];
    } catch {
      dismissedProblems.value = [];
    }
  },
  { immediate: true },
);
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
  state.runs.filter(
    (run) =>
      ["cancelled", "failed", "limited", "interrupted"].includes(run.status) &&
      run.reason !== "converted_to_steering" &&
      !dismissedProblems.value.includes(run.id),
  ),
);
const setupIssue = computed(() =>
  configurationIssue(state.settingsStatus, state.settings, state.profiles),
);
const canSend = computed(
  () =>
    !setupIssue.value &&
    state.connected &&
    !!state.selected &&
    !state.sessionLoading,
);
const selectedProfile = computed(() =>
  state.profiles.find(
    (profile) => profile.id === state.settings.default_profile_id,
  ),
);
const contextUsage = computed(() => contextSnapshot(state.events));
const visibleMessages = computed(() => conversationItems(state.messages));
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
        item.run_id === activeRun.value?.id &&
        !["model.delta", "steering.updated"].includes(item.type),
    );
  if (activeRun.value?.status === "cancelling")
    return "正在停止并核对已执行结果…";
  if (event?.type === "model.retry")
    return `${event.data.reason || "模型请求暂时失败"}，${event.data.delay_seconds} 秒后重试（${event.data.retry}/${event.data.max_retries || activeRun.value?.settings?.retries || "—"}）`;
  if (event?.type === "context.compacting") return "正在整理上下文…";
  if (event?.type === "tool.started") return `正在执行 ${event.data.name}…`;
  return "Agent 正在处理…";
});
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
async function promoteQueued(id: string) {
  if (
    promoting.value ||
    activeRun.value?.status !== "running" ||
    !state.connected
  )
    return;
  promoting.value = id;
  try {
    await safely(() => api(`/runs/${id}/steer-queued`, "POST"));
  } finally {
    promoting.value = "";
  }
}
async function submit() {
  const content = input.value.trim();
  if (!content || sending.value || !canSend.value) return;
  sending.value = true;
  await safely(async () => {
    await send(content);
    input.value = "";
  });
  sending.value = false;
}
function onKeydown(event: KeyboardEvent) {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    void submit();
  }
}
function stop() {
  if (activeRun.value)
    void safely(() => api(`/runs/${activeRun.value!.id}/cancel`, "POST"));
}
async function addTodo() {
  if (!todoTitle.value.trim() || todoSaving.value) return;
  todoSaving.value = true;
  try {
    await safely(async () => {
      await changeTodo({
        action: "add",
        title: todoTitle.value.trim(),
        notes: todoNotes.value.trim(),
      });
      todoTitle.value = "";
      todoNotes.value = "";
    });
  } finally {
    todoSaving.value = false;
  }
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
  () => state.selected,
  () => {
    summaryOpen.value = false;
  },
);
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
  display: flex;
  align-items: center;
  width: 100%;
  border: 0;
  background: transparent;
  text-align: left;
  padding: 0 6px 0 0;
  border-radius: 9px;
  color: #47564f;
  cursor: pointer;
  margin-bottom: 4px;
}
.session-select {
  flex: 1;
  min-width: 0;
  padding: 12px;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  overflow-wrap: anywhere;
}
.session-delete {
  border: 0;
  background: transparent;
  color: #8a988f;
  cursor: pointer;
  font-size: 20px;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  flex-shrink: 0;
}
.session-delete:hover {
  background: #f5e9e4;
  color: #a65d46;
}
.session-spinner {
  width: 13px;
  height: 13px;
  border: 2px solid #cfdfd4;
  border-top-color: #358160;
  border-radius: 50%;
  flex-shrink: 0;
  margin-right: 5px;
  animation: session-loading 0.8s linear infinite;
}
@keyframes session-loading {
  to {
    transform: rotate(360deg);
  }
}
@media (prefers-reduced-motion: reduce) {
  .session-spinner {
    animation: none;
  }
}
.setup-alert {
  margin: 12px 20px 0;
  flex-shrink: 0;
}
.setup-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
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
.todo-content-input {
  margin-top: 8px;
}
.todo-empty {
  padding: 30px 5px;
  color: #93a095;
  font-size: 12px;
  line-height: 1.8;
}
.todo-item {
  display: grid;
  grid-template-columns: 20px minmax(0, 1fr);
  align-items: start;
  gap: 10px;
  padding: 15px 0;
  border-bottom: 1px solid #e3e9e3;
}
.todo-checkbox {
  justify-self: start;
  align-self: start;
  margin-top: 2px;
}
.todo-title {
  display: block;
  line-height: 1.6;
}
.todo-body {
  min-width: 0;
  overflow-wrap: anywhere;
  font-size: 13px;
}
.todo-item p {
  white-space: pre-wrap;
  color: #829087;
  font-size: 11px;
  margin: 6px 0;
}
.done {
  text-decoration: line-through;
  color: #99a39b;
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
.queue-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  margin-top: 8px;
}
.queue-content {
  flex: 1;
  min-width: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.queue-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.steering-row {
  color: #497d75;
}
.queue-status {
  flex-shrink: 0;
  font-size: 11px;
}
.run-note {
  font-size: 12px;
  padding: 12px;
  background: #faf4ed;
  border-radius: 8px;
  margin: 12px 0;
  color: #8b725a;
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

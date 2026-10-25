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
          @click="safely(/* 作用：加载点击的会话并切换聊天视图。 */ () => selectSession(session.id))"
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
          @positive-click="safely(/* 作用：确认后删除该会话并刷新选择。 */ () => deleteSession(session.id))"
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
            <ReasoningBlock :text="item.rows[0]!.reasoning" />
            <div v-if="item.rows[0]!.original_content ?? item.rows[0]!.message.content" class="message-text">
              {{ item.rows[0]!.original_content ?? item.rows[0]!.message.content }}
            </div>
          </article>
        </template>
        <article
          v-for="(live, runId) in state.live"
          :key="runId"
          class="message assistant"
        >
          <div class="message-label">Agent · 正在输出</div>
          <ReasoningBlock :text="live.reasoning" streaming />
          <div v-if="live.text" class="message-text">
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
            <div class="queue-content">
              {{ run.content }}
              <small v-if="steeringErrors[run.id]" class="queue-error" role="alert">
                {{ steeringErrors[run.id] }}
              </small>
            </div>
            <div class="queue-actions">
              <n-button
                size="tiny"
                :loading="promoting === run.id"
                :disabled="
                  activeRun?.status !== 'running' ||
                  activeRun?.purpose === 'context_compaction' ||
                  !state.connected ||
                  !!promoting
                "
                @click="promoteQueued(run.id)"
                >引导</n-button
              >
              <n-button
                text
                size="tiny"
                @click="safely(/* 作用：请求取消当前排队项。 */ () => api(`/runs/${run.id}/cancel`, 'POST'))"
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
        <n-mention
          v-model:value="input"
          type="textarea"
          placeholder="输入任务，使用 @ 选择工具。运行中发送会加入队列。"
          :options="toolOptions"
          :filter="filterTool"
          :autosize="{ minRows: 2, maxRows: 8 }"
          :disabled="sending"
          @update:show="/* 作用：同步工具菜单是否展开，防止选择时误发送。 */ (show) => (mentionOpen = show)"
          @keydown="onKeydown"
        />
        <div v-if="selectedTools.length" class="selected-tools" aria-live="polite">
          <span>本次偏好工具</span>
          <n-tag v-for="name in selectedTools" :key="name" size="small" type="success">
            @{{ name }}
          </n-tag>
          <small>模型会优先考虑，信息不足时先询问；删除 @名称 可取消偏好。</small>
        </div>
        <div class="composer-actions">
          <span>@ 选择工具 · Enter 发送 · Shift+Enter 换行</span
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
              :compacting="compacting"
              :compact-disabled="compactDisabled"
              :compact-message="compactMessage"
              @summary="summaryOpen = true"
              @compact="compactContext"
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
      <div v-for="todo in visibleTodos" :key="todo.id" class="todo-item">
        <n-checkbox
          class="todo-checkbox"
          :aria-label="`完成待办：${todo.title}`"
          :checked="todo.status === 'completed'"
          @update:checked="/* 作用：将勾选状态提交为待办完成状态。 */ (checked) => toggleTodo(todo, checked)"
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
      <div v-if="state.todos.length" class="todo-pagination">
        <span>共 {{ state.todos.length }} 条 · 每页 {{ todoPageSize }} 条</span>
        <n-pagination
          v-if="state.todos.length > todoPageSize"
          v-model:page="todoPage"
          :item-count="state.todos.length"
          :page-size="todoPageSize"
          simple
          size="small"
        />
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
    v-model:show="summaryOpen"
    preset="card"
    title="历史摘要"
    role="dialog"
    aria-label="历史摘要"
    class="summary-modal"
    style="width: min(720px, 95vw)"
    closable
  >
    <div class="summary-content">{{
      state.summary?.text ||
      "尚未生成摘要。可手动压缩或等待达到阈值后自动整理，原历史保留。"
    }}</div>
    <template #footer>
      <n-button @click="summaryOpen = false">关闭</n-button>
    </template>
  </n-modal>
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
// 作者：LHF。
// 注释维护时间：2026-10-20。
// 文件作用：会话聊天、任务队列、引导、压缩与共享待办交互。
import { computed, nextTick, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  NAlert,
  NButton,
  NCheckbox,
  NDrawer,
  NDrawerContent,
  NInput,
  NMention,
  NModal,
  NPagination,
  NPopconfirm,
  NSpace,
  NTag,
} from "naive-ui";
import {
  ApiError,
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
import ReasoningBlock from "@/components/ReasoningBlock.vue";
import { mentionedTools } from "@/lib/tool-mentions";
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
// 采用组件自带的光标定位与键盘选择，候选项直接取自后端工具注册表。
const mentionOpen = ref(false);
const toolOptions = computed(/* 作用：生成包含工具名称及描述的提及候选项。 */ () => state.tools.map(/* 作用：生成包含工具名称及描述的提及候选项。 */ (tool) => ({
  value: tool.name,
  label: `${tool.name} · ${tool.description}`,
})));
const selectedTools = computed(/* 作用：根据当前草稿提取已选择的工具。 */ () => mentionedTools(input.value, state.tools));
function filterTool(pattern: string, option: { label?: unknown; value?: unknown }) {
  // 作用：按工具名和描述筛选提及菜单，兼容中文关键词。
  return String(option.label || option.value).toLowerCase().includes(pattern.toLowerCase());
}
const todoTitle = ref(""),
  todoNotes = ref(""),
  todoSaving = ref(false),
  editOpen = ref(false),
  editTitle = ref(""),
  editNotes = ref("");
const editing = ref<Todo | null>(null),
  scrollArea = ref<HTMLElement | null>(null);
const todoPage = ref(1);
const compactSubmitting = ref(false);
const compactError = ref("");
const steeringErrors = ref<Record<string, string>>({});
watch(
  /* 作用：读取监听所依赖的状态，变化后触发界面同步。 */ () => [state.user, state.selected],
  /* 作用：切换用户或会话后重置对应的临时提示或恢复已隐藏记录。 */ () => {
    steeringErrors.value = {};
  },
);
const todoPageSize = 5;
// 共享待办在当前页分页展示；数据变少时将页码收回有效范围。
const visibleTodos = computed(/* 作用：截取共享待办的当前页数据。 */ () =>
  state.todos.slice(
    (todoPage.value - 1) * todoPageSize,
    todoPage.value * todoPageSize,
  ),
);
watch(
  /* 作用：读取监听所依赖的状态，变化后触发界面同步。 */ () => state.todos.length,
  /* 作用：待办数量变化后将当前页码收回有效范围。 */ (count) => {
    todoPage.value = Math.min(
      todoPage.value,
      Math.max(1, Math.ceil(count / todoPageSize)),
    );
  },
);
watch(
  /* 作用：读取监听所依赖的状态，变化后触发界面同步。 */ () => state.user,
  /* 作用：切换用户后重置待办分页位置。 */ () => {
    todoPage.value = 1;
  },
);
const dismissedProblems = ref<string[]>([]);
const problemStorageKey = /* 作用：生成按用户和会话隔离的异常提示存储键。 */ () =>
  `harness-dismissed-runs:${state.user}:${state.selected}`;
function dismissProblem(id: string) {
  // 作用：在当前用户和会话范围内隐藏历史任务异常提示。
  // 仅隐藏当前用户、当前会话的历史提示，不修改服务端任务状态。
  dismissedProblems.value = [...new Set([...dismissedProblems.value, id])];
  try {
    sessionStorage.setItem(
      problemStorageKey(),
      JSON.stringify(dismissedProblems.value),
    );
  } catch {
    /* 浏览器存储不可用时，本次页面内仍可隐藏提示。 */
  }
}
watch(
  /* 作用：读取监听所依赖的状态，变化后触发界面同步。 */ () => [state.user, state.selected],
  /* 作用：切换用户或会话后重置对应的临时提示或恢复已隐藏记录。 */ () => {
    try {
      const saved = JSON.parse(
        sessionStorage.getItem(problemStorageKey()) || "[]",
      );
      dismissedProblems.value = Array.isArray(saved)
        ? saved.filter(/* 作用：按所属任务、消息角色或状态筛选当前需要的记录。 */ (id): id is string => typeof id === "string")
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
  /* 作用：读取当前会话标题，无匹配时使用默认名称。 */ () =>
    state.sessions.find(/* 作用：按当前标识或状态定位匹配记录，避免引用其他任务或会话。 */ (item) => item.id === state.selected)?.title ||
    "新对话",
);
const activeRun = computed(/* 作用：查找正在运行或等待取消收尾的任务。 */ () =>
  // cancelling 仍占用执行通道，等后端完成收尾后才能当成空闲。
  state.runs.find(/* 作用：按当前标识或状态定位匹配记录，避免引用其他任务或会话。 */ (run) => ["running", "cancelling"].includes(run.status)),
);
const queued = computed(/* 作用：筛选尚未开始执行的排队任务。 */ () =>
  state.runs.filter(/* 作用：按所属任务、消息角色或状态筛选当前需要的记录。 */ (run) => run.status === "queued"),
);
const lastCompaction = computed(/* 作用：定位最近一次手动压缩任务。 */ () =>
  [...state.runs].reverse().find(/* 作用：按当前标识或状态定位匹配记录，避免引用其他任务或会话。 */ (run) => run.purpose === "context_compaction"),
);
const compacting = computed(/* 作用：判断当前是否正在提交或执行压缩。 */ () =>
  compactSubmitting.value || state.runs.some(
    /* 作用：检查是否存在符合当前条件的记录。 */ (run) => run.purpose === "context_compaction" &&
      ["queued", "running", "cancelling"].includes(run.status),
  ),
);
const compactDisabled = computed(/* 作用：计算阻止手动压缩的首个原因。 */ () =>
  // 手动压缩必须在会话空闲时提交，避免和排队消息争用上下文。
  setupIssue.value ||
  (!state.connected ? "后端未连接" : "") ||
  (state.sessionLoading || !state.selected ? "请等待会话加载" : "") ||
  (activeRun.value || queued.value.length ? "请等待当前任务和排队消息完成" : "") ||
  (!state.messages.length ? "当前会话还没有可压缩的历史" : ""),
);
const compactMessage = computed(/* 作用：生成最近压缩任务的进度、结果或失败说明。 */ () => {
  if (compactError.value) return compactError.value;
  if (compacting.value) return "正在压缩上下文，可用对话页的停止按钮取消。";
  const run = lastCompaction.value;
  if (!run) return "";
  if (run.status === "completed")
    return run.compaction_result === "compacted"
      ? "压缩完成，完整原始历史已保留。"
      : run.compaction_message || "没有可压缩的较早历史。";
  return `压缩未完成：${reasonLabel(run.reason) || statusLabel(run.status)}`;
});
const historicalProblems = computed(/* 作用：筛选尚未隐藏的历史异常任务。 */ () =>
  state.runs.filter(
    /* 作用：按所属任务、消息角色或状态筛选当前需要的记录。 */ (run) =>
      ["cancelled", "failed", "limited", "interrupted"].includes(run.status) &&
      run.reason !== "converted_to_steering" &&
      !dismissedProblems.value.includes(run.id),
  ),
);
const setupIssue = computed(/* 作用：检查模型及运行配置是否满足发送条件。 */ () =>
  configurationIssue(state.settingsStatus, state.settings, state.profiles),
);
const canSend = computed(
  /* 作用：检查会话、配置和事件连接是否允许提交消息。 */ () =>
    !setupIssue.value &&
    state.connected &&
    !!state.selected &&
    !state.sessionLoading,
);
const selectedProfile = computed(/* 作用：查找全局设置选中的对话模型。 */ () =>
  state.profiles.find(
    /* 作用：按当前标识或状态定位匹配记录，避免引用其他任务或会话。 */ (profile) => profile.id === state.settings.default_profile_id,
  ),
);
const contextUsage = computed(/* 作用：从历史事件还原当前上下文用量。 */ () => contextSnapshot(state.events));
const visibleMessages = computed(/* 作用：将原始历史整理为聊天展示条目。 */ () => conversationItems(state.messages));
const pendingSteering = computed(/* 作用：按引导 ID 取最新状态并筛选当前任务未消费的引导。 */ () => {
  // 每条引导可能有多次状态事件，按 ID 取最新状态后筛选尚未应用的内容。
  const latest = new Map<string, (typeof state.events)[number]>();
  state.events
    .filter(/* 作用：按所属任务、消息角色或状态筛选当前需要的记录。 */ (event) => event.type === "steering.updated")
    .forEach(/* 作用：按标识保存最新引导事件，后续状态覆盖同一引导的旧状态。 */ (event) => latest.set(event.data.id, event));
  return [...latest.values()].filter(
    /* 作用：按所属任务、消息角色或状态筛选当前需要的记录。 */ (event) =>
      event.data.status === "pending" && event.run_id === activeRun.value?.id,
  );
});
const activityText = computed(/* 作用：从当前任务的关键事件生成进度提示。 */ () => {
  // 从当前任务最近的关键事件生成进度提示，逐字输出不覆盖工具或重试状态。
  const event = [...state.events]
    .reverse()
    .find(
      /* 作用：按当前标识或状态定位匹配记录，避免引用其他任务或会话。 */ (item) =>
        item.run_id === activeRun.value?.id &&
        !["model.delta", "model.reasoning.delta", "steering.updated"].includes(item.type),
    );
  if (activeRun.value?.status === "cancelling")
    return "正在停止并核对已执行结果…";
  if (activeRun.value?.purpose === "context_compaction")
    return "正在手动压缩上下文…";
  if (event?.type === "model.retry")
    return `${event.data.reason || "模型请求暂时失败"}，${event.data.delay_seconds} 秒后重试（${event.data.retry}/${event.data.max_retries || activeRun.value?.settings?.retries || "—"}）`;
  if (event?.type === "context.compacting") return "正在整理上下文…";
  if (event?.type === "tool.started") return `正在执行 ${event.data.name}…`;
  return "Agent 正在处理…";
});
function statusLabel(status: string) {
  // 作用：把聊天区需要提示的异常任务状态转换成中文。
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
function reasonLabel(reason?: string | null) {
  // 作者：LHF；时间：2026-10-21；作用：接收 Run 尚无取消或失败原因时的 null。
  // 作用：翻译已知停止原因，其他原因保留后端说明。
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
  // 作用：将排队消息转为当前任务引导，失败提示仅写回原会话。
  // 请求后端原子转换排队消息；失败时保留原队列项，并在该条消息旁展示原因。
  if (
    promoting.value ||
    activeRun.value?.status !== "running" ||
    activeRun.value?.purpose === "context_compaction" ||
    !state.connected
  )
    return;
  promoting.value = id;
  const session = state.selected;
  delete steeringErrors.value[id];
  try {
    await api(`/runs/${id}/steer-queued`, "POST");
  } catch (error) {
    if (state.selected !== session) return;
    steeringErrors.value[id] =
      error instanceof ApiError && [404, 405].includes(error.status)
        ? "引导未生效：后端接口不可用，请重启后端加载最新代码后重试；原消息仍在队列中。"
        : `引导未生效：${error instanceof Error ? error.message : String(error)}`;
  } finally {
    promoting.value = "";
  }
}
async function compactContext() {
  // 作用：提交手动压缩任务，合并重复通知并记录当前会话的提交错误。
  // HTTP 返回和 SSE 都可能先到，按任务 ID 去重；错误仅写回原会话。
  if (compacting.value || compactDisabled.value) return;
  const session = state.selected;
  compactSubmitting.value = true;
  compactError.value = "";
  try {
    const run = await api(`/sessions/${session}/compact`, "POST", {
      client_id: state.clientId,
      request_id: crypto.randomUUID(),
    });
    if (state.selected === session && !state.runs.some(/* 作用：检查是否存在符合当前条件的记录。 */ (item) => item.id === run.id))
      state.runs.push(run);
  } catch (error) {
    if (state.selected === session)
      compactError.value = error instanceof ApiError && [404, 405].includes(error.status)
        ? "压缩接口尚未加载，请重启后端后重试。"
        : `压缩未开始：${error instanceof Error ? error.message : String(error)}`;
  } finally {
    compactSubmitting.value = false;
  }
}
async function submit() {
  // 作用：校验输入并提交任务，仅在请求成功后清空草稿。
  // 请求被接受后才清空输入；发送中的新消息排队，不自动当作运行引导。
  const content = input.value.trim();
  if (!content || sending.value || !canSend.value) return;
  sending.value = true;
  await safely(/* 作用：校验输入并提交任务，仅在请求成功后清空草稿。 */ async () => {
    await send(content);
    input.value = "";
  });
  sending.value = false;
}
function onKeydown(event: KeyboardEvent) {
  // 作用：处理 Enter 发送，同时避开输入法选词、换行和工具菜单选择。
  // 输入法组合期间的 Enter 用于选词，Shift+Enter 用于换行，都不触发发送。
  // 菜单处理过的 Enter 不能再次提交，否则选择工具就会意外发送消息。
  if (event.defaultPrevented || mentionOpen.value) return;
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    void submit();
  }
}
function stop() {
  // 作用：请求停止当前活跃任务，最终结果由后端事件驱动。
  // 仅发起停止请求；按钮和界面等待后端 cancelling/终态事件更新。
  if (activeRun.value)
    void safely(/* 作用：请求停止当前活跃任务，最终结果由后端事件驱动。 */ () => api(`/runs/${activeRun.value!.id}/cancel`, "POST"));
}
async function addTodo() {
  // 作用：防止重复提交新增待办，保存成功后清空输入。
  // 防止连续点击重复新增，只有服务端确认成功后才清空表单。
  if (!todoTitle.value.trim() || todoSaving.value) return;
  todoSaving.value = true;
  try {
    await safely(/* 作用：防止重复提交新增待办，保存成功后清空输入。 */ async () => {
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
  // 作用：携带当前版本更新待办完成状态，并重新读取服务端结果。
  // 提交当前版本防止覆盖其他窗口的修改；无论成败都重新读取最新待办。
  void safely(/* 作用：携带当前版本更新待办完成状态，并重新读取服务端结果。 */ async () => {
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
  // 作用：携带当前版本删除待办，并刷新列表以处理并发修改。
  // 删除同样校验版本，不在前端先移除条目，以后端实际结果为准。
  void safely(/* 作用：携带当前版本删除待办，并刷新列表以处理并发修改。 */ async () => {
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
  // 作用：将待办复制到编辑表单，保留原版本用于并发校验。
  // 表单只编辑副本字段，保留打开时的版本供保存时检查并发修改。
  editing.value = todo;
  editTitle.value = todo.title;
  editNotes.value = todo.notes;
  editOpen.value = true;
}
async function saveTodo() {
  // 作用：保存待办表单，成功后关闭弹窗并重新获取列表。
  // 成功才关闭编辑框；版本冲突后刷新列表，避免继续展示过期状态。
  if (!editing.value) return;
  await safely(/* 作用：保存待办表单，成功后关闭弹窗并重新获取列表。 */ async () => {
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
  /* 作用：读取监听所依赖的状态，变化后触发界面同步。 */ () => state.selected,
  /* 作用：切换会话后关闭摘要弹窗并清理压缩错误。 */ () => {
    summaryOpen.value = false;
    compactError.value = "";
  },
);
watch(
  /* 作用：读取监听所依赖的状态，变化后触发界面同步。 */ () => [
    state.messages.length,
    Object.values(state.live)
      .map(/* 作用：把每条输入记录转换成当前展示或断言需要的结构。 */ (item) => item.text + item.reasoning)
      .join(""),
  ],
  /* 作用：等待消息 DOM 更新后滚动聊天区域，覆盖正式消息和流式片段。 */ async () => {
    await nextTick();
    // 等 Vue 完成消息 DOM 更新后滚动，覆盖落库消息和流式文本两种更新。
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
.selected-tools {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
  color: #718077;
  font-size: 12px;
}
.selected-tools small { width: 100%; }
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
.todo-pagination {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 12px;
  color: #829087;
  font-size: 11px;
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
.summary-content {
  max-height: min(60vh, 560px);
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.8;
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
.queue-error {
  display: block;
  margin-top: 4px;
  color: #b14335;
  line-height: 1.6;
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

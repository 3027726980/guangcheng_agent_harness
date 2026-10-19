<template>
  <div class="trace-controls">
    <label>选择任务</label>
    <n-select
      v-model:value="selectedRun"
      :options="options"
      placeholder="暂无执行任务"
    />
    <div class="trace-overview" v-if="currentRun">
      <n-tag size="small">{{ runStatus(currentRun.status) }}</n-tag>
      <span
        >模型 {{ currentRun.model_calls }} 次 · 工具
        {{ currentRun.tool_calls }} 次</span
      >
      <span>{{ steps.length }} 个步骤 · 每页 {{ pageSize }} 个</span>
    </div>
    <p class="trace-hint">
      调用与结果合并为步骤。点击展开原始记录；文本增量和聊天消息在对话区查看。
    </p>
  </div>
  <p v-if="!steps.length" class="trace-hint">此任务暂无可展示的执行步骤。</p>
  <details
    v-for="(step, index) in visibleSteps"
    :key="step.id"
    class="trace-step"
  >
    <summary>
      <span class="step-number">{{ (page - 1) * pageSize + index + 1 }}</span>
      <span
        ><strong>{{ step.label }}</strong
        ><small>{{
          describe(step.events[step.events.length - 1]!)
        }}</small></span
      >
      <span class="step-result" :class="{ failed: step.failed }">{{
        step.failed ? "需关注" : `${step.events.length} 条记录`
      }}</span>
    </summary>
    <div v-for="event in step.events" :key="event.id" class="event-detail">
      <strong>{{ eventLabel(event.type) }}</strong>
      <span
        >{{ new Date(event.timestamp * 1000).toLocaleTimeString() }} · #{{
          event.id
        }}</span
      >
      <pre>{{ JSON.stringify(event.data, null, 2) }}</pre>
    </div>
  </details>
  <div class="trace-pagination" v-if="steps.length > pageSize">
    <n-pagination
      v-model:page="page"
      :item-count="steps.length"
      :page-size="pageSize"
      :page-slot="5"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { NPagination, NSelect, NTag } from "naive-ui";
import { eventLabel, runStatus, traceSteps } from "@/lib/chat-presentation";
import type { Run, TraceEvent } from "@/types/harness";
const props = defineProps<{ runs: Run[]; events: TraceEvent[] }>();
const selectedRun = ref<string | null>(null),
  page = ref(1),
  pageSize = 8;
const options = computed(() =>
  [...props.runs].reverse().map((run) => ({
    label: `${runStatus(run.status)} · ${run.content.slice(0, 42)}`,
    value: run.id,
  })),
);
watch(
  options,
  (options) => {
    if (!options.some((item) => item.value === selectedRun.value))
      selectedRun.value = options[0]?.value || null;
  },
  { immediate: true },
);
watch(selectedRun, () => {
  page.value = 1;
});
const currentRun = computed(() =>
  props.runs.find((run) => run.id === selectedRun.value),
);
const steps = computed(() =>
  traceSteps(
    props.events.filter((event) => event.run_id === selectedRun.value),
  ),
);
watch(
  () => steps.value.length,
  (length) => {
    page.value = Math.min(
      page.value,
      Math.max(1, Math.ceil(length / pageSize)),
    );
  },
);
const visibleSteps = computed(() =>
  steps.value.slice((page.value - 1) * pageSize, page.value * pageSize),
);
function describe(event: TraceEvent) {
  if (event.type === "run.updated") return runStatus(event.data.status);
  if (event.type === "tool.finished")
    return event.data.ok
      ? `执行成功 · ${event.data.elapsed_ms ?? 0} ms`
      : event.data.error?.message || "未成功";
  if (event.type === "model.finished")
    return `结束原因：${event.data.finish_reason}`;
  if (event.type === "context.usage")
    return `估算 ${Number(event.data.estimated_tokens).toLocaleString()} tokens`;
  if (event.type === "model.retry")
    return `${event.data.delay_seconds} 秒后重试`;
  return eventLabel(event.type);
}
</script>

<style scoped>
.trace-controls {
  position: sticky;
  top: 0;
  z-index: 1;
  background: white;
  padding: 4px 0 12px;
}
label {
  display: block;
  color: #718278;
  font-size: 12px;
  margin-bottom: 6px;
}
.trace-overview {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  font-size: 12px;
  margin-top: 12px;
  color: #637c6c;
}
.trace-hint {
  font-size: 11px;
  line-height: 1.8;
  color: #8a978e;
  margin: 10px 0 0;
}
.trace-step {
  border: 1px solid #e4eae5;
  border-radius: 10px;
  margin-bottom: 10px;
  padding: 13px;
}
summary {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 10px;
  list-style: none;
}
summary::after {
  content: "+";
  color: #8a978e;
}
details[open] > summary::after {
  content: "−";
}
.step-number {
  width: 25px;
  height: 25px;
  border-radius: 50%;
  background: #edf3ee;
  color: #65826e;
  display: grid;
  place-items: center;
  font-size: 11px;
  flex-shrink: 0;
}
summary > span:nth-child(2) {
  flex: 1;
  min-width: 0;
}
summary strong {
  font-size: 12px;
  color: #42634d;
}
small {
  display: block;
  font-size: 11px;
  color: #89968d;
  margin-top: 4px;
  overflow-wrap: anywhere;
}
.step-result {
  font-size: 10px;
  color: #889b8b;
  flex-shrink: 0;
}
.failed {
  color: #bd8433;
}
.event-detail {
  padding: 14px 0 0;
  font-size: 11px;
  color: #67816e;
}
.event-detail > span {
  color: #95a096;
  margin-left: 8px;
}
pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 280px;
  overflow: auto;
  font-size: 11px;
  line-height: 1.7;
  color: #657468;
}
.trace-pagination {
  display: flex;
  justify-content: center;
  padding: 14px 0;
}
</style>

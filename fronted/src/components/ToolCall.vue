<template>
  <details class="tool-call">
    <summary>
      <span>调用工具 · {{ calls[0]?.function.name || "工具结果" }}</span>
      <span class="outcome" :class="{ failed: failures > 0 }"
        >{{
          failures ? `${failures} 次未成功` : pending ? "执行中" : "已完成"
        }}</span
      >
    </summary>
    <div v-for="row in rows" :key="row.id" class="tool-step">
      <p v-if="row.message.role === 'assistant' && row.message.content">
        {{ row.message.content }}
      </p>
      <div v-for="call in row.message.tool_calls" :key="call.id">
        <strong>{{ call.function.name }}</strong
        ><span class="step-label">调用参数</span>
        <pre>{{ pretty(call.function.arguments) }}</pre>
      </div>
      <template v-if="row.message.role === 'tool'">
        <strong>{{
          calls.find((call) => call.id === row.message.tool_call_id)?.function
            .name || "工具"
        }}</strong>
        <span class="step-label">执行结果</span>
        <pre>{{ pretty(row.message.content) }}</pre>
      </template>
    </div>
  </details>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { Message } from "@/types/harness";
const props = defineProps<{ rows: Message[] }>();
const calls = computed(() =>
  props.rows.flatMap((row) => row.message.tool_calls || []),
);
const results = computed(() =>
  props.rows.filter((row) => row.message.role === "tool"),
);
const pending = computed(() => results.value.length < calls.value.length);
const failures = computed(
  () =>
    results.value.filter((row) => {
      try {
        return JSON.parse(row.message.content || "{}").ok === false;
      } catch {
        return true;
      }
    }).length,
);
function pretty(content: string | null) {
  try {
    return JSON.stringify(JSON.parse(content || "{}"), null, 2);
  } catch {
    return content;
  }
}
</script>

<style scoped>
.tool-call {
  border: 1px solid #e4eae5;
  background: #f8faf8;
  border-radius: 9px;
  padding: 11px 13px;
  margin-top: 8px;
  font-size: 12px;
  color: #587360;
}
summary {
  cursor: pointer;
  line-height: 1.8;
}
.outcome {
  color: #8a988e;
  font-size: 11px;
  margin-left: 12px;
}
.failed {
  color: #b17c30;
}
.tool-step {
  border-top: 1px solid #e5ebe6;
  padding: 12px 0 0;
  margin-top: 10px;
  overflow-wrap: anywhere;
}
.tool-step p {
  white-space: pre-wrap;
  line-height: 1.8;
}
.step-label {
  font-size: 10px;
  margin-left: 10px;
  color: #8a988e;
}
pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 240px;
  overflow: auto;
  font-size: 11px;
  line-height: 1.7;
  color: #57635b;
}
</style>

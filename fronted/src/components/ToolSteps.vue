<template>
  <details class="tool-process">
    <summary>
      <span>执行过程 · {{ steps.length }} 次工具调用</span>
      <span class="outcome" :class="{ failed: failures > 0 }">{{
        failures
          ? `${failures} 次未成功${pending ? ' · 执行中' : ''}`
          : pending ? "执行中" : "已完成"
      }}</span>
    </summary>
    <div class="tool-list">
      <ToolCall v-for="step in steps" :key="step.id" :rows="step.rows" />
    </div>
  </details>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { Message } from "@/types/harness";
import ToolCall from "./ToolCall.vue";
const props = defineProps<{ rows: Message[] }>();
const steps = computed(() => {
  const items: { id: string; rows: Message[] }[] = [];
  const paired = new Set<string>();
  for (const row of props.rows) {
    for (const call of row.message.tool_calls || []) {
      const result = props.rows.find(
        (candidate) =>
          candidate.run_id === row.run_id &&
          candidate.message.role === "tool" &&
          candidate.message.tool_call_id === call.id,
      );
      if (result) paired.add(result.id);
      items.push({
        id: `${row.id}:${call.id}`,
        rows: [
          { ...row, message: { ...row.message, tool_calls: [call] } },
          ...(result ? [result] : []),
        ],
      });
    }
  }
  for (const row of props.rows) {
    if (row.message.role === "tool" && !paired.has(row.id))
      items.push({ id: row.id, rows: [row] });
  }
  return items;
});
const pending = computed(() =>
  steps.value.some((step) => !step.rows.some((row) => row.message.role === "tool")),
);
const failures = computed(() =>
  props.rows.filter((row) => {
    if (row.message.role !== "tool") return false;
    try {
      return JSON.parse(row.message.content || "{}").ok === false;
    } catch {
      return true;
    }
  }).length,
);
</script>

<style scoped>
.tool-process {
  margin-bottom: 20px;
  color: #587360;
  font-size: 12px;
}
summary {
  cursor: pointer;
  line-height: 1.8;
  overflow-wrap: anywhere;
}
.outcome {
  margin-left: 12px;
  color: #8a988e;
  font-size: 11px;
}
.failed {
  color: #b17c30;
}
.tool-list {
  max-height: 360px;
  overflow: auto;
  padding-left: 12px;
}
</style>

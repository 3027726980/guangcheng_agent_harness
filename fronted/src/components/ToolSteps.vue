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
// 作者：LHF。
// 注释维护时间：2026-10-20。
// 文件作用：配对工具声明与结果并组织执行步骤。
import { computed } from "vue";
import type { Message } from "@/types/harness";
import ToolCall from "./ToolCall.vue";
const props = defineProps<{ rows: Message[] }>();
const steps = computed(/* 作用：按任务和调用 ID 整理工具或链路步骤。 */ () => {
  // 用 run_id 和 tool_call_id 配对，避免不同任务中同名调用发生误配。
  const items: { id: string; rows: Message[] }[] = [];
  const paired = new Set<string>();
  for (const row of props.rows) {
    for (const call of row.message.tool_calls || []) {
      const result = props.rows.find(
        /* 作用：按当前标识或状态定位匹配记录，避免引用其他任务或会话。 */ (candidate) =>
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
      // 历史数据中找不到对应声明的结果仍保留展示，不静默丢弃。
      items.push({ id: row.id, rows: [row] });
  }
  return items;
});
const pending = computed(/* 作用：判断是否还有工具调用等待结果。 */ () =>
  steps.value.some(/* 作用：检查是否存在符合当前条件的记录。 */ (step) => !step.rows.some(/* 作用：检查是否存在符合当前条件的记录。 */ (row) => row.message.role === "tool")),
);
const failures = computed(/* 作用：统计工具执行失败或无法解析的结果。 */ () =>
  props.rows.filter(/* 作用：按所属任务、消息角色或状态筛选当前需要的记录。 */ (row) => {
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

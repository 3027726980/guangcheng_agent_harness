<template>
  <n-popover v-model:show="detailsOpen" trigger="click" placement="top-end">
    <template #trigger>
      <button
        type="button"
        class="context-meter"
        :class="{ warning: percent >= 80 }"
        :aria-label="label"
        :title="label"
      >
        <svg viewBox="0 0 36 36" aria-hidden="true">
          <circle class="track" cx="18" cy="18" r="14" />
          <circle
            class="fill"
            cx="18"
            cy="18"
            r="14"
            :stroke-dasharray="`${Math.min(100, percent) * 0.87965} 87.965`"
          />
        </svg>
        <span>{{ known ? `${Math.round(percent)}%` : "—" }}</span>
      </button>
    </template>
    <div class="context-details">
      <strong>上下文容量</strong>
      <p v-if="known">
        估算已用 {{ formatTokenCount(used) }} /
        {{ formatTokenCount(capacity) }} tokens
      </p>
      <p v-else>
        {{
          capacity
            ? `容量 ${formatTokenCount(capacity)} tokens，尚未估算用量。`
            : "配置模型后显示容量。"
        }}
      </p>
      <p v-if="capacity">
        {{
          String(source).startsWith("default") ? "默认容量" : "供应商提供的容量"
        }}
        · 用量为估算值
      </p>
      <p v-if="known">
        约剩余
        {{
          formatTokenCount(Math.max(0, capacity - used))
        }}
        tokens（包含自动输出预留）
      </p>
      <n-button text type="primary" @click="showSummary">查看历史摘要</n-button>
      <div class="compact-action">
        <n-button
          size="small"
          :loading="compacting"
          :disabled="!!compactDisabled || compacting"
          @click="emit('compact')"
        >立即压缩</n-button>
        <p v-if="compactDisabled">{{ compactDisabled }}</p>
        <p v-else>调用摘要模型，保留最近一轮对话和完整原始历史。</p>
        <p v-if="compactMessage" role="status">{{ compactMessage }}</p>
      </div>
    </div>
  </n-popover>
</template>

<script setup lang="ts">
// 作者：LHF。
// 注释维护时间：2026-10-20。
// 文件作用：展示上下文容量、用量及摘要和压缩入口。
import { computed, ref } from "vue";
import { NButton, NPopover } from "naive-ui";
import { formatTokenCount } from "@/lib/token-format";
const props = defineProps<{
  usage?: Record<string, any>;
  capacity: number;
  source: string;
  compacting?: boolean;
  compactDisabled?: string;
  compactMessage?: string;
}>();
const emit = defineEmits<{ summary: []; compact: [] }>();
const detailsOpen = ref(false);
function showSummary() {
  // 作用：关闭容量浮层，再通知父页面展示历史摘要。
  // 关闭容量浮层后再通知父页面打开摘要，避免两个浮层重叠。
  detailsOpen.value = false;
  emit("summary");
}
const capacity = computed(/* 作用：优先使用执行快照中的上下文容量。 */ () =>
  // 已有执行用量事件时使用任务快照容量，否则回退到当前模型配置。
  Number(props.usage?.capacity ?? props.capacity),
);
const source = computed(/* 作用：显示容量估算的数据来源。 */ () => props.usage?.source ?? props.source);
const known = computed(/* 作用：区分未知用量和有效估算。 */ () => Number.isFinite(props.usage?.estimated_tokens));
// 尚未估算和确实使用 0 tokens 分开处理，避免把未知用量显示成已确认值。
const used = computed(/* 作用：读取最后一次有效的上下文用量。 */ () => Number(props.usage?.estimated_tokens || 0));
const percent = computed(/* 作用：计算上下文用量占容量的百分比。 */ () =>
  capacity.value > 0 ? Math.max(0, (used.value / capacity.value) * 100) : 0,
);
const label = computed(/* 作用：生成上下文容量入口的无障碍说明。 */ () =>
  known.value
    ? `上下文已使用约 ${Math.round(percent.value)}%，点击查看容量和摘要`
    : "上下文用量尚未估算，点击查看容量",
);
</script>

<style scoped>
.context-meter {
  width: 36px;
  height: 36px;
  border: 0;
  padding: 0;
  background: transparent;
  cursor: pointer;
  position: relative;
  color: #56816b;
  border-radius: 50%;
  flex-shrink: 0;
}
.context-meter:focus-visible {
  outline: 2px solid #56816b;
  outline-offset: 3px;
}
svg {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}
circle {
  fill: none;
  stroke-width: 3;
}
.track {
  stroke: #e5ece7;
}
.fill {
  stroke: currentColor;
  stroke-linecap: round;
  transition: stroke-dasharray 0.3s;
}
.context-meter span {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  font-size: 8px;
  font-weight: 600;
}
.warning {
  color: #b17c30;
}
.context-details {
  max-width: 280px;
  font-size: 12px;
  line-height: 1.7;
}
.context-details p {
  margin: 6px 0;
  color: #75847b;
}
.compact-action {
  margin-top: 12px;
  border-top: 1px solid #e5ece7;
  padding-top: 10px;
}
</style>

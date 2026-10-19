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
    </div>
  </n-popover>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { NButton, NPopover } from "naive-ui";
import { formatTokenCount } from "@/lib/token-format";
const props = defineProps<{
  usage?: Record<string, any>;
  capacity: number;
  source: string;
}>();
const emit = defineEmits<{ summary: [] }>();
const detailsOpen = ref(false);
function showSummary() {
  detailsOpen.value = false;
  emit("summary");
}
const capacity = computed(() =>
  Number(props.usage?.capacity ?? props.capacity),
);
const source = computed(() => props.usage?.source ?? props.source);
const known = computed(() => Number.isFinite(props.usage?.estimated_tokens));
const used = computed(() => Number(props.usage?.estimated_tokens || 0));
const percent = computed(() =>
  capacity.value > 0 ? Math.max(0, (used.value / capacity.value) * 100) : 0,
);
const label = computed(() =>
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
</style>

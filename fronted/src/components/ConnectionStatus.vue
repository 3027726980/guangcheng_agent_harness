<template>
  <n-popover trigger="hover" placement="bottom-end">
    <template #trigger>
      <span class="connection-trigger" tabindex="0" :aria-label="description">
        <n-tag :type="ready ? 'success' : 'warning'" size="small">
          {{ ready ? "后端已链接" : checking ? "连接检查中" : "连接未就绪" }}
        </n-tag>
      </span>
    </template>
    <div class="connection-details">
      <div class="connection-row">
        <span
          class="connection-mark"
          :class="{ ok: connected }"
          aria-hidden="true"
          >{{ connected ? "✓" : "✕" }}</span
        >
        <div>
          <strong>后端实时连接</strong>
          <p>
            {{
              connected
                ? "已链接，可接收输出和执行进度"
                : connecting
                  ? "正在建立连接"
                  : "未链接，无法接收执行进度"
            }}
          </p>
        </div>
      </div>
      <div class="connection-row">
        <span
          class="connection-mark"
          :class="{ ok: modelReady }"
          aria-hidden="true"
          >{{ modelReady ? "✓" : "✕" }}</span
        >
        <div>
          <strong>模型配置与连接测试</strong>
          <p>{{ modelReady ? "已配置，连接测试通过" : modelIssue }}</p>
        </div>
      </div>
      <p class="connection-hint">模型状态依据最近一次保存或连接测试结果。</p>
    </div>
  </n-popover>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { NPopover, NTag } from "naive-ui";
const props = defineProps<{
  connected: boolean;
  connecting: boolean;
  settingsStatus: string;
  modelIssue: string;
}>();
const modelReady = computed(
  () => props.settingsStatus === "ready" && !props.modelIssue,
);
const ready = computed(() => props.connected && modelReady.value);
const checking = computed(
  () => props.connecting || props.settingsStatus === "loading",
);
const description = computed(
  () =>
    `后端${props.connected ? "已链接" : "未链接"}；模型${modelReady.value ? "已配置且连接测试通过" : "未就绪：" + props.modelIssue}`,
);
</script>

<style scoped>
.connection-trigger {
  display: inline-flex;
  cursor: help;
  border-radius: 4px;
}
.connection-trigger:focus-visible {
  outline: 2px solid #56816b;
  outline-offset: 3px;
}
.connection-details {
  max-width: 290px;
  font-size: 12px;
  line-height: 1.7;
}
.connection-row {
  display: flex;
  align-items: flex-start;
  gap: 9px;
}
.connection-row + .connection-row {
  margin-top: 12px;
}
.connection-mark {
  color: #bc5a4c;
  font-size: 16px;
  line-height: 1.5;
}
.connection-mark.ok {
  color: #28815b;
}
.connection-row strong {
  color: #485d50;
  font-weight: 600;
}
.connection-row p {
  margin: 2px 0 0;
  color: #75847b;
}
.connection-hint {
  margin: 12px 0 0;
  color: #95a096;
  font-size: 11px;
}
</style>

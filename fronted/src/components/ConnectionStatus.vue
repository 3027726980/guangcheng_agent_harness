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
// 作者：LHF。
// 注释维护时间：2026-10-20。
// 文件作用：综合展示后端事件连接与模型配置就绪状态。
import { computed } from "vue";
import { NPopover, NTag } from "naive-ui";
const props = defineProps<{
  connected: boolean;
  connecting: boolean;
  settingsStatus: string;
  modelIssue: string;
}>();
const modelReady = computed(
  // 后端事件连接可用与模型配置可用是两件事，发送就绪必须同时满足。
  /* 作用：判断模型配置是否已加载并通过连接测试。 */ () => props.settingsStatus === "ready" && !props.modelIssue,
);
const ready = computed(/* 作用：同时检查模型与后端连接就绪状态。 */ () => props.connected && modelReady.value);
const checking = computed(
  /* 作用：判断是否仍在连接后端或加载配置。 */ () => props.connecting || props.settingsStatus === "loading",
);
const description = computed(
  /* 作用：生成后端连接与模型就绪状态说明。 */ () =>
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

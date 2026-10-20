<template>
  <details v-if="text" class="reasoning-block">
    <summary>思考过程{{ streaming ? " · 接收中" : "" }}</summary>
    <div class="reasoning-text">{{ text }}</div>
  </details>
</template>

<script setup lang="ts">
// 作者：LHF。
// 时间：2026-10-20。
// 作用：折叠展示模型实际返回的思考文本，不将其作为回答正文或 HTML 执行。
defineProps<{ text?: string; streaming?: boolean }>();
</script>

<style scoped>
.reasoning-block {
  border-left: 2px solid #dce6df;
  color: #718077;
  padding: 4px 12px;
  margin: 8px 0 12px;
  font-size: 12px;
}
summary { cursor: pointer; }
.reasoning-text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.8;
  max-height: 280px;
  overflow: auto;
  margin-top: 8px;
}
</style>

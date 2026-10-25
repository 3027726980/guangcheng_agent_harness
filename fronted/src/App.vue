<template>
  <n-config-provider :locale="zhCN" :date-locale="dateZhCN">
    <n-alert
      v-if="state.error"
      type="error"
      closable
      class="global-error"
      @close="state.error = ''"
      >{{ state.error }}</n-alert
    >
    <router-view />
  </n-config-provider>
</template>

<script setup lang="ts">
// 作者：LHF。
// 注释维护时间：2026-10-20。
// 文件作用：应用根组件、全局提示与业务初始化。
import { onMounted } from "vue";
import { NAlert, NConfigProvider, zhCN, dateZhCN } from "naive-ui";
import { boot, safely, state } from "@/api/harness";
// 应用挂载后统一加载数据和建立事件连接，初始化错误进入全局提示。
onMounted(/* 作用：组件挂载后初始化业务或注册媒体查询监听。 */ () => safely(boot));
</script>

<style>
.global-error {
  position: fixed;
  top: 10px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 3000;
  max-width: min(700px, 95vw);
  box-shadow: 0 4px 25px #22332218;
}
</style>

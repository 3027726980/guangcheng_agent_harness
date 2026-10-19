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
import { onMounted } from "vue";
import { NAlert, NConfigProvider, zhCN, dateZhCN } from "naive-ui";
import { boot, safely, state } from "@/api/harness";
onMounted(() => safely(boot));
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

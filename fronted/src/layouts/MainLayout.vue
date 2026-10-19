<template>
  <n-layout has-sider class="main-layout">
    <n-layout-sider
      bordered
      collapse-mode="width"
      :collapsed-width="64"
      :width="220"
      :collapsed="collapsed"
    >
      <div class="logo-area">
        <span class="logo-text">{{ collapsed ? "H" : "Agent Harness" }}</span>
      </div>
      <n-menu
        :collapsed="collapsed"
        :collapsed-width="64"
        :value="route.path"
        :options="menuOptions"
        @update:value="router.push($event)"
      />
    </n-layout-sider>

    <n-layout class="workspace">
      <n-layout-header bordered class="header">
        <div class="header-left">
          <n-button
            text
            :aria-label="collapsed ? '展开侧边栏' : '收起侧边栏'"
            :aria-expanded="!collapsed"
            @click="collapsed = !collapsed"
          >
            <n-icon size="20">
              <MenuOutline v-if="collapsed" />
              <ChevronBackOutline v-else />
            </n-icon>
          </n-button>
          <span>{{ route.meta.title }}</span>
        </div>
        <div class="identity">
          <span>演示用户</span
          ><n-select
            :value="state.user"
            :options="[
              { label: '用户 A', value: 'A' },
              { label: '用户 B', value: 'B' },
            ]"
            style="width: 110px"
            @update:value="(value) => safely(() => switchUser(value))"
          />
        </div>
      </n-layout-header>
      <n-layout-content class="content">
        <router-view />
      </n-layout-content>
    </n-layout>
  </n-layout>
</template>

<script setup lang="ts">
import { h, onMounted, onUnmounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NButton,
  NIcon,
  NLayout,
  NLayoutContent,
  NLayoutHeader,
  NLayoutSider,
  NMenu,
  NSelect,
} from "naive-ui";
import {
  GridOutline,
  DocumentOutline,
  InformationCircleOutline,
  MenuOutline,
  ChevronBackOutline,
} from "@vicons/ionicons5";
import { pages } from "@/router";
import { safely, state, switchUser } from "@/api/harness";

const route = useRoute();
const router = useRouter();
const narrow = window.matchMedia("(max-width: 640px)");
const collapsed = ref(narrow.matches);
const updateNarrow = (event: MediaQueryListEvent) => {
  collapsed.value = event.matches;
};
onMounted(() => narrow.addEventListener("change", updateNarrow));
onUnmounted(() => narrow.removeEventListener("change", updateNarrow));
const icons = [GridOutline, DocumentOutline, InformationCircleOutline];
const menuOptions = pages.map((page, index) => ({
  label: page.meta.title,
  key: `/${page.path}`,
  icon: () =>
    h(NIcon, null, { default: () => h(icons[index] ?? DocumentOutline) }),
}));
</script>

<style scoped>
.main-layout {
  height: 100dvh;
}
.logo-area {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid var(--n-border-color);
}
.logo-text {
  font-size: 17px;
  font-weight: 700;
  white-space: nowrap;
}
.workspace {
  min-width: 0;
}
.identity {
  display: flex;
  gap: 12px;
  align-items: center;
  font-size: 12px;
  color: #8b978e;
}
.header {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  gap: 16px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  white-space: nowrap;
}
.header-brand {
  color: #767c86;
  font-size: 13px;
}
.content {
  height: calc(100dvh - 56px);
  padding: 24px;
  background: #f5f6f8;
}
@media (max-width: 640px) {
  .content {
    padding: 16px;
  }
  .header-brand {
    display: none;
  }
  .identity > span {
    display: none;
  }
  .header {
    padding: 0 10px;
    gap: 8px;
  }
}
</style>

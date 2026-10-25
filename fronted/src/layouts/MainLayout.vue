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
            @update:value="/* 作用：响应用户身份选择。 */ (value) => safely(/* 作用：切换演示用户并重新加载数据。 */ () => switchUser(value))"
          />
        </div>
      </n-layout-header>
      <n-layout-content class="content">
        <div v-if="state.loggingError" role="alert" class="logging-warning">{{ state.loggingError }}</div>
        <router-view />
      </n-layout-content>
    </n-layout>
  </n-layout>
</template>

<script setup lang="ts">
// 作者：LHF。
// 注释维护时间：2026-10-20。
// 文件作用：导航布局、响应式侧栏与演示用户切换。
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
// 小屏默认收起导航，卸载时移除媒体查询监听，避免重复挂载累积回调。
const collapsed = ref(narrow.matches);
const updateNarrow = /* 作用：根据媒体查询结果切换侧栏折叠状态。 */ (event: MediaQueryListEvent) => {
  collapsed.value = event.matches;
};
onMounted(/* 作用：组件挂载后初始化业务或注册媒体查询监听。 */ () => narrow.addEventListener("change", updateNarrow));
onUnmounted(/* 作用：组件卸载时移除媒体查询监听，防止重复回调。 */ () => narrow.removeEventListener("change", updateNarrow));
const icons = [GridOutline, DocumentOutline, InformationCircleOutline];
const menuOptions = pages.map(/* 作用：将页面路由转换为导航菜单。 */ (page, index) => ({
  // 导航菜单直接读取路由配置，页面标题和链接统一维护。
  label: page.meta.title,
  key: `/${page.path}`,
  icon: /* 作用：生成当前导航项的图标容器。 */ () =>
    h(NIcon, null, { default: /* 作用：渲染路由对应的图标，缺省时使用文档图标。 */ () => h(icons[index] ?? DocumentOutline) }),
}));
</script>

<style scoped>
.logging-warning { padding: 10px 16px; color: #933b23; background: #fff1dc; }
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

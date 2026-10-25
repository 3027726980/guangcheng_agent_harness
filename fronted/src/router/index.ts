// 作者：LHF。
// 注释维护时间：2026-10-20。
// 文件作用：配置页面路由与导航菜单元信息。
import { createRouter, createWebHashHistory } from "vue-router";
import MainLayout from "@/layouts/MainLayout.vue";
const ChatView = /* 作用：按需加载聊天页面组件。 */ () => import("@/views/ChatView.vue");
const SettingsView = /* 作用：按需加载全局设置页面组件。 */ () => import("@/views/SettingsView.vue");

// 菜单读取这些路由的 meta.title；新增页面只需在此添加路由。
export const pages = [
  { path: "chat", component: ChatView, meta: { title: "Agent 对话" } },
  { path: "settings", component: SettingsView, meta: { title: "全局设置" } },
];

export default createRouter({
  // 使用 hash 路由，部署静态文件时不依赖服务端对页面路径做回退重写。
  history: createWebHashHistory(),
  routes: [
    { path: "/", component: MainLayout, redirect: "/chat", children: pages },
    { path: "/:pathMatch(.*)*", redirect: "/chat" },
  ],
});

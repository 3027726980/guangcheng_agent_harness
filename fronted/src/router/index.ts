import { createRouter, createWebHashHistory } from "vue-router";
import MainLayout from "@/layouts/MainLayout.vue";
const ChatView = () => import("@/views/ChatView.vue");
const SettingsView = () => import("@/views/SettingsView.vue");

// 菜单读取这些路由的 meta.title；新增页面只需在此添加路由。
export const pages = [
  { path: "chat", component: ChatView, meta: { title: "Agent 对话" } },
  { path: "settings", component: SettingsView, meta: { title: "全局设置" } },
];

export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", component: MainLayout, redirect: "/chat", children: pages },
    { path: "/:pathMatch(.*)*", redirect: "/chat" },
  ],
});

// 作者：LHF。
// 注释维护时间：2026-10-20。
// 文件作用：创建 Vue 应用并注册路由。
import { createApp } from "vue";
import App from "./App.vue";
import router from "./router";
import "./styles/global.css";

// 注册路由后挂载根组件，业务初始化由 App.vue 的挂载钩子触发。
createApp(App).use(router).mount("#app");

// 作者：LHF。
// 注释维护时间：2026-10-20。
// 文件作用：前端构建配置、路径别名与本地 API 代理。
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  base: "./",
  plugins: [vue()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    // 浏览器统一请求同源 /api，开发服务器再转发到本地后端 8000 端口。
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  preview: { host: "127.0.0.1", proxy: { "/api": "http://127.0.0.1:8000" } },
  // @ 指向源码目录，避免组件层级变化后出现大量相对路径。
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
});

import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  base: "./",
  plugins: [vue()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  preview: { host: "127.0.0.1", proxy: { "/api": "http://127.0.0.1:8000" } },
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
});

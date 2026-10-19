# Agent Harness 前端

基于 [PinLayout](https://github.com/3027726980/PinLayout) 的 Vue 3 + TypeScript + Naive UI 布局；保留原 MIT 声明于 `LICENSE`。

```powershell
npm ci
npm run dev
```

访问 `http://127.0.0.1:5173`，`/api` 代理到后端 `http://127.0.0.1:8000`。静态预览也提供相同代理，需要单独运行后端。

```powershell
npm test
npm run build
```

需要 Node.js 22.6 或以上。测试使用 Node 原生测试运行器，验证 SSE 在任意分块边界、CRLF 和多行数据下的解析。构建先做类型检查，再打包。

聊天、共享待办与设置在 `src/views/`；事件和请求状态在 `src/api/harness.ts`；SSE 增量解析在 `src/lib/sse.ts`。

页面不持久保存密钥。当前演示用户与选中会话仅使用窗口级 sessionStorage；不同窗口不会因选择会话而互相跳转。服务端是真实身份与业务归属检查的边界，演示身份不等同真实认证。

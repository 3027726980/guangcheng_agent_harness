// 作者：LHF；时间：2026-10-22；作用：离线挂载真实组件，验证调用分页、按需详情和切换竞争。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parse, compileScript } from "@vue/compiler-sfc";
import ts from "typescript";
import { createRenderer, nextTick } from "vue";

async function flush() {
  // 作用：等待模拟 API Promise 和 Vue 更新完成，不启动浏览器或 HTTP 服务。
  for (let index = 0; index < 5; index++) await nextTick();
}

async function mountComponent(api, props) {
  // 作用：编译仓库中的真实组件，注入模拟 API 并用无 DOM 渲染器运行 setup。
  const source = readFileSync(new URL("../src/components/ModelCallContext.vue", import.meta.url), "utf8");
  const { descriptor } = parse(source);
  const compiled = compileScript(descriptor, { id: "context-test" });
  let code = ts.transpileModule(compiled.content, {
    compilerOptions: { target: ts.ScriptTarget.ESNext, module: ts.ModuleKind.ESNext },
  }).outputText;
  code = code.replace(/from ["']vue["']/g, `from ${JSON.stringify(import.meta.resolve("vue"))}`);
  code = code.replace(/import \{ api \} from ["']@\/api\/harness["'];?/, "const api = globalThis.__modelCallTestApi;");
  globalThis.__modelCallTestApi = api;
  const { default: component } = await import(`data:text/javascript;base64,${Buffer.from(code).toString("base64")}#${Math.random()}`);
  delete globalThis.__modelCallTestApi;
  component.render = () => null;
  const renderer = createRenderer({
    // 作用：组件逻辑测试只需要空节点，所有内容读取直接检查真实响应状态。
    createComment: () => ({}), insert: () => {}, remove: () => {}, parentNode: () => null,
    nextSibling: () => null, createElement: () => ({}), createText: () => ({}),
    setText: () => {}, setElementText: () => {}, patchProp: () => {},
  });
  const app = renderer.createApp(component, props);
  const instance = app.mount({});
  await flush();
  return { state: instance.$.setupState, app };
}

test("actual context component paginates and loads full input only when opened", async () => {
  // 作用：列表不请求完整输入，下一页使用游标，展开后才读取详情。
  const requests = [];
  const { state, app } = await mountComponent(async (path) => {
    requests.push(path);
    if (path.endsWith("/c1")) return { call_id: "c1", request: { messages: [{ role: "user", content: "完整输入" }] } };
    if (path.includes("after=7")) return { items: [{ call_id: "c2" }], next_cursor: null };
    return { items: [{ call_id: "c1" }], next_cursor: 7 };
  }, { sessionId: "s", runId: "r", revision: 0 });
  try {
    assert.equal(requests.length, 1);
    assert.equal(state.detail, null);
    state.loadMore();
    await flush();
    assert.equal(state.calls.length, 2);
    assert.equal(state.cursor, null);
    await state.open("c1");
    assert.equal(state.detail.request.messages[0].content, "完整输入");
    assert.equal(requests[2], "/sessions/s/model-calls/c1");
  } finally { app.unmount(); }
});

test("late requests cannot overwrite another run and old runs have no fabricated snapshots", async () => {
  // 作用：切换任务后迟到的列表不会显示在新任务，旧调用保持无快照状态。
  let finish;
  const delayed = new Promise((resolve) => { finish = resolve; });
  const { state, app } = await mountComponent((path) => path.includes("run_id=old")
    ? delayed : Promise.resolve({ items: [], next_cursor: null }),
  { sessionId: "s", runId: "old", revision: 0 });
  try {
    // 根属性通过实例更新，触发组件实际的 watch。
    app._instance.props.runId = "new";
    await flush();
    finish({ items: [{ call_id: "stale" }], next_cursor: null });
    await flush();
    assert.deepEqual(state.calls, []);
    assert.equal(state.detail, null);
    assert.equal(state.loading, false);
  } finally { app.unmount(); }
});

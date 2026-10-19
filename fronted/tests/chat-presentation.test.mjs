import test from "node:test";
import assert from "node:assert/strict";
import {
  configurationIssue,
  conversationItems,
  contextSnapshot,
  traceSteps,
  updateSessionActivity,
  sessionActivityLabel,
} from "../src/lib/chat-presentation.ts";

const profile = {
  id: "p",
  base_url: "http://example.invalid/v1",
  model: "fixture",
  test_status: "connected",
  context_capacity: 262144,
};
const settings = {
  default_profile_id: "p",
  summary_profile_id: null,
};

test("session activity survives another run finishing and stays isolated across sessions", () => {
  const sessions = [
    { id: "a" },
    { id: "b", active_runs: [{ id: "other", status: "running" }] },
  ];
  updateSessionActivity(sessions, {
    id: "first",
    session_id: "a",
    status: "running",
  });
  updateSessionActivity(sessions, {
    id: "next",
    session_id: "a",
    status: "queued",
  });
  assert.match(sessionActivityLabel(sessions[0]), /执行中，1 条排队/);
  updateSessionActivity(sessions, {
    id: "first",
    session_id: "a",
    status: "completed",
  });
  assert.equal(sessionActivityLabel(sessions[0]), "1 条任务排队中");
  updateSessionActivity(sessions, {
    id: "next",
    session_id: "a",
    status: "cancelling",
  });
  assert.equal(sessionActivityLabel(sessions[0]), "正在停止任务");
  updateSessionActivity(sessions, {
    id: "next",
    session_id: "a",
    status: "cancelled",
  });
  assert.equal(sessionActivityLabel(sessions[0]), "");
  assert.equal(sessionActivityLabel(sessions[1]), "任务执行中");
});

test("send readiness rejects missing, untested, incomplete and oversized configuration", () => {
  assert.match(configurationIssue("loading", settings, [profile]), /正在读取/);
  assert.match(configurationIssue("error", settings, [profile]), /未能读取/);
  assert.match(configurationIssue("ready", {}, []), /选择对话模型/);
  assert.match(
    configurationIssue("ready", settings, [
      { ...profile, test_status: "failed" },
    ]),
    /测试未通过/,
  );
  assert.match(
    configurationIssue("ready", settings, [{ ...profile, model: " " }]),
    /模型 ID/,
  );
  assert.match(
    configurationIssue(
      "ready",
      { ...settings, summary_profile_id: "missing" },
      [profile],
    ),
    /摘要模型/,
  );
  assert.match(
    configurationIssue("ready", settings, [
      { ...profile, context_capacity: 512 },
    ]),
    /容量不足/,
  );
  assert.equal(configurationIssue("ready", settings, [profile]), "");
  assert.equal(configurationIssue("ready", settings, [
    { ...profile, context_capacity: 2048 },
  ]), "");
});

test("tool calls remain inline with assistant text and pair only their own results", () => {
  const message = (id, role, run = "r", calls) => ({
    id,
    run_id: run,
    message: {
      role,
      content: id,
      tool_calls: calls,
      tool_call_id: role === "tool" ? "call" : undefined,
    },
  });
  const call = {
    id: "call",
    function: { name: "calculator", arguments: "{}" },
  };
  const rows = [
    message("request", "user"),
    message("a", "assistant", "r", [call]),
    message("b", "tool"),
    message("c", "assistant", "r", [call]),
    message("d", "tool"),
    message("answer", "assistant"),
    message("next", "assistant", "r2", [call]),
    message("last", "tool", "r3"),
  ];
  const items = conversationItems(rows);
  assert.deepEqual(
    items.map((item) => [item.kind, item.rows.length]),
    [
      ["message", 1],
      ["message", 1],
      ["tools", 2],
      ["message", 1],
      ["tools", 2],
      ["message", 1],
      ["message", 1],
      ["tools", 1],
      ["tools", 1],
    ],
  );
  assert.deepEqual(
    items.map((item) => item.rows[0].id),
    ["request", "a", "a", "c", "c", "answer", "next", "next", "last"],
  );
  assert.equal(items[2].rows[1].id, "b");
  assert.equal(items[4].rows[1].id, "d");
  assert.equal(items[1].rows[0].message.tool_calls, undefined);
  assert.equal(items[2].rows[0].message.content, null);
  assert.equal(rows[1].message.content, "a");
});

test("same-batch calls share one group and a later user message stays in sequence", () => {
  const call = (id) => ({ id, function: { name: id, arguments: "{}" } });
  const row = (id, message) => ({ id, run_id: "r", message });
  const items = conversationItems([
    row("calls", {
      role: "assistant",
      content: null,
      tool_calls: [call("search"), call("calculator")],
    }),
    row("calc-result", {
      role: "tool",
      tool_call_id: "calculator",
      content: "{}",
    }),
    row("search-result", {
      role: "tool",
      tool_call_id: "search",
      content: "{}",
    }),
    row("steering", { role: "user", content: "补充条件" }),
    row("late", { role: "tool", tool_call_id: "calculator", content: "{}" }),
  ]);
  assert.deepEqual(
    items.map((item) => item.id),
    ["calls:search", "steering", "late"],
  );
  assert.equal(items[0].rows[1].id, "search-result");
  assert.equal(items[0].rows[3].id, "calc-result");
  assert.equal(items[2].rows.length, 1);
});

test("consecutive tool rounds merge without crossing text or run boundaries", () => {
  const rows = [];
  for (let index = 0; index < 4; index++) {
    const run_id = index === 3 ? "other" : "r";
    if (index === 2) rows.push({id:"text",run_id,message:{role:"assistant",content:"下一步"}});
    rows.push({id:`call-${index}`,run_id,message:{role:"assistant",content:null,
      tool_calls:[{id:`c${index}`,function:{name:"calculator",arguments:"{}"}}]}});
    rows.push({id:`result-${index}`,run_id,message:{role:"tool",tool_call_id:`c${index}`,content:'{"ok":true}'}});
  }
  const groups=conversationItems(rows);
  assert.deepEqual(groups.map(item=>[item.kind,item.rows.length]),[
    ["tools",4],["message",1],["tools",2],["tools",2],
  ]);
  assert.deepEqual(groups[0].rows.map(row=>row.id),["call-0","result-0","call-1","result-1"]);
});

test("context ring uses the post-compaction estimate until a newer usage sample", () => {
  const event = (id, type, data) => ({ id, type, data });
  assert.equal(contextSnapshot([]), undefined);
  assert.equal(
    contextSnapshot([
      event(1, "context.usage", { estimated_tokens: 8000, capacity: 10000 }),
      event(2, "context.compacted", { after: 4000 }),
    ]).estimated_tokens,
    4000,
  );
  assert.equal(
    contextSnapshot([
      event(1, "context.usage", { estimated_tokens: 8000 }),
      event(2, "context.compacted", { after: 4000 }),
      event(3, "context.usage", { estimated_tokens: 4500 }),
    ]).estimated_tokens,
    4500,
  );
});

test("trace groups start/result pairs per run and keeps failures visible", () => {
  const event = (id, type, data, run_id = "r") => ({ id, type, data, run_id });
  const steps = traceSteps([
    event(1, "tool.started", { call_id: "same", name: "todo" }),
    event(2, "tool.finished", { call_id: "same", name: "todo", ok: false }),
    event(3, "tool.started", { call_id: "same", name: "todo" }, "r2"),
    event(4, "model.delta", { text: "hello" }),
    event(5, "message.created", {}),
    event(6, "run.updated", { status: "running" }),
    event(7, "run.updated", { status: "completed" }),
  ]);
  assert.equal(steps.length, 3);
  assert.equal(steps[0].events.length, 2);
  assert.equal(steps[0].failed, true);
  assert.equal(steps[1].events.length, 1);
  assert.equal(steps[2].events.length, 2);
});

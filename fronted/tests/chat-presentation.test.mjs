import test from "node:test";
import assert from "node:assert/strict";
import {
  configurationIssue,
  conversationItems,
  contextSnapshot,
  traceSteps,
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
  max_output_tokens: 2000,
  summary_tokens: 1000,
};

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
      { ...profile, context_capacity: 2048 },
    ]),
    /容量不足/,
  );
  assert.equal(configurationIssue("ready", settings, [profile]), "");
});

test("tool process groups dependent calls and results without hiding final replies or mixing runs", () => {
  const message = (id, role, run = "r", calls) => ({
    id,
    run_id: run,
    message: { role, content: id, tool_calls: calls },
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
      ["tools", 4],
      ["message", 1],
      ["tools", 1],
      ["tools", 1],
    ],
  );
  assert.equal(items[2].rows[0].id, "answer");
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

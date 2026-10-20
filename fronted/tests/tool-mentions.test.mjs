// 作者：LHF。
// 时间：2026-10-20。
// 作用：验证工具提及与思考展示的数据转换，不启动浏览器或模型。
import test from "node:test";
import assert from "node:assert/strict";
import { mentionedTools } from "../src/lib/tool-mentions.ts";
import { conversationItems } from "../src/lib/chat-presentation.ts";

test("mentions use known exact tool names, deduplicate and ignore email addresses", /* 作用：验证工具提及必须精确匹配已注册名称，去重并排除邮箱。 */ () => {
  const tools = [{ name: "calculator" }, { name: "search" }, { name: "todo" }];
  assert.deepEqual(mentionedTools("@calculator 计算，再用 @todo 记录 @calculator", tools), ["calculator", "todo"]);
  assert.deepEqual(mentionedTools("a@search.com @searching @unknown", tools), []);
  assert.deepEqual(mentionedTools("@search，查询", tools), ["search"]);
  assert.deepEqual(mentionedTools("帮我@calculator 计算，并用（@todo）", tools), ["calculator"]);
  assert.deepEqual(mentionedTools("@search查询", tools), []);
});

test("reasoning remains visible when assistant emits only tool calls", /* 作用：验证模型只返回工具调用时，思考内容仍能独立展示。 */ () => {
  const items = conversationItems([{ id: "a", run_id: "r", reasoning: "模型返回的思考",
    message: { role: "assistant", content: null, tool_calls: [{ id: "c", function: { name: "calculator" } }] },
  }]);
  assert.equal(items[0].kind, "message");
  assert.equal(items[0].rows[0].reasoning, "模型返回的思考");
  assert.equal(items[1].kind, "tools");
  assert.equal(items[1].rows[0].reasoning, undefined);
});

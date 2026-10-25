// 作者：LHF。
// 时间：2026-10-20。
// 作用：离线验证前端消息呈现、事件解析及边界行为。
import test from "node:test";
import assert from "node:assert/strict";
import { SSEParser } from "../src/lib/sse.ts";

test("SSE frames survive every network split boundary", /* 作用：验证 SSE 帧在每一个可能的网络分割位置都能正确解析。 */ () => {
  const input = 'event: ready\ndata: {}\n\nid: 7\ndata: {"text":"你好"}\n\n';
  for (let split = 0; split <= input.length; split++) {
    const parser = new SSEParser();
    const frames = [
      ...parser.push(input.slice(0, split)),
      ...parser.push(input.slice(split)),
    ];
    assert.equal(frames.length, 2);
    assert.equal(frames[0].event, "ready");
    assert.equal(JSON.parse(frames[1].data).text, "你好");
    assert.equal(frames[1].id, "7");
  }
});

test("CRLF, comments, multiline data and individual byte-sized text chunks", /* 作用：验证换行格式、心跳注释、多行数据和逐字符分片。 */ () => {
  const parser = new SSEParser();
  const input =
    ": keepalive\r\n\r\nevent: sample\r\ndata: first\r\ndata: second\r\n\r\n";
  const frames = [...input].flatMap(/* 作用：提取并展开每条记录对应的工具调用或 SSE 帧。 */ (character) => parser.push(character));
  assert.deepEqual(frames, [
    { event: "sample", data: "first\nsecond", id: "" },
  ]);
});

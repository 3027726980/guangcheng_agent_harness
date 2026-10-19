import test from "node:test";
import assert from "node:assert/strict";
import { SSEParser } from "../src/lib/sse.ts";

test("SSE frames survive every network split boundary", () => {
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

test("CRLF, comments, multiline data and individual byte-sized text chunks", () => {
  const parser = new SSEParser();
  const input =
    ": keepalive\r\n\r\nevent: sample\r\ndata: first\r\ndata: second\r\n\r\n";
  const frames = [...input].flatMap((character) => parser.push(character));
  assert.deepEqual(frames, [
    { event: "sample", data: "first\nsecond", id: "" },
  ]);
});

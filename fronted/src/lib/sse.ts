// 作者：LHF。
// 注释维护时间：2026-10-20。
// 文件作用：跨网络分块增量解析 SSE 事件帧。
/** 作用：一帧 SSE 的事件名称、数据和事件 ID。 */
export interface SSEFrame {
  event: string;
  data: string;
  id: string;
}

/** 增量解析 SSE；网络分块可能截断行或事件，不能把一次 read 当成完整事件。 */
export class SSEParser {
  private buffer = "";
  private pendingCR = false;

  push(chunk: string): SSEFrame[] {
    // 作用：缓存跨网络分块的残留文本，并解析完整 SSE 帧。
    const frames: SSEFrame[] = [];
    // CRLF 本身也可能跨网络分块；上一块已将 CR 转为换行时跳过本块开头的 LF。
    if (this.pendingCR) {
      if (chunk.startsWith("\n")) chunk = chunk.slice(1);
      this.pendingCR = false;
    }
    if (chunk.endsWith("\r")) {
      chunk = chunk.slice(0, -1) + "\n";
      this.pendingCR = true;
    }
    this.buffer += chunk.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    let boundary: number;
    while ((boundary = this.buffer.indexOf("\n\n")) !== -1) {
      // 空行表示一帧结束，不完整的尾部继续留在 buffer 中等待下次输入。
      const block = this.buffer.slice(0, boundary);
      this.buffer = this.buffer.slice(boundary + 2);
      const frame: SSEFrame = { event: "message", data: "", id: "" };
      const data: string[] = [];
      for (const line of block.split("\n")) {
        // 冒号开头的行是心跳注释；多行 data 最后按协议用换行拼接。
        if (!line || line.startsWith(":")) continue;
        const colon = line.indexOf(":");
        const key = colon === -1 ? line : line.slice(0, colon);
        let value = colon === -1 ? "" : line.slice(colon + 1);
        if (value.startsWith(" ")) value = value.slice(1);
        if (key === "event") frame.event = value;
        if (key === "id") frame.id = value;
        if (key === "data") data.push(value);
      }
      frame.data = data.join("\n");
      if (data.length) frames.push(frame);
    }
    return frames;
  }
}

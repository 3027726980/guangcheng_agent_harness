export interface SSEFrame {
  event: string;
  data: string;
  id: string;
}

/** Incremental SSE decoder; no assumptions about network chunk boundaries. */
export class SSEParser {
  private buffer = "";
  private pendingCR = false;

  push(chunk: string): SSEFrame[] {
    const frames: SSEFrame[] = [];
    // A CRLF pair can itself be split across network chunks.
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
      const block = this.buffer.slice(0, boundary);
      this.buffer = this.buffer.slice(boundary + 2);
      const frame: SSEFrame = { event: "message", data: "", id: "" };
      const data: string[] = [];
      for (const line of block.split("\n")) {
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

# 作者：LHF。
# 时间：2026-10-20。
# 作用：增量分离供应商公开返回的思考标签与回答正文，不推测未返回的思考。


def native_reasoning(message):
    """读取供应商公开返回的思考文本，用于前端展示。"""
    # 兼容常见扩展字段，只接受文本，避免把其他供应商结构误显示成思考。
    for field in ("reasoning_content", "reasoning"):
        value = getattr(message, field, None)
        if isinstance(value, str) and value:
            return value
    return ""


def protocol_reasoning(message):
    """保留原始协议思考，区分缺失与空字符串，不混入正文中的 think 标签。"""
    value = getattr(message, "reasoning_content", None)
    return value if isinstance(value, str) else None


class ReasoningParser:
    # 暂存可能属于标签前缀的尾部，确保 <think> 即使逐字到达也不会泄漏到正文。
    def __init__(self):
        """初始化标签缓冲区和当前文本所属区域。"""
        self.buffer = ""
        self.thinking = False

    def push(self, text):
        """消费一个文本分片并返回已确定归属的正文或思考片段。"""
        self.buffer += text
        output = []
        while self.buffer:
            marker = "</think>" if self.thinking else "<think>"
            index = self.buffer.find(marker)
            kind = "reasoning" if self.thinking else "text"
            if index >= 0:
                if index:
                    output.append((kind, self.buffer[:index]))
                self.buffer = self.buffer[index + len(marker) :]
                self.thinking = not self.thinking
                continue
            held = 0
            for size in range(1, min(len(marker), len(self.buffer) + 1)):
                if self.buffer.endswith(marker[:size]):
                    held = size
            ready = self.buffer[:-held] if held else self.buffer
            if ready:
                output.append((kind, ready))
            self.buffer = self.buffer[-held:] if held else ""
            break
        return output

    def finish(self):
        """流结束时输出残留文本，保持未闭合思考块的归属。"""
        # 未闭合的思考块仍属于思考，不能在结束或截断时混入最终答案。
        tail, self.buffer = self.buffer, ""
        return [("reasoning" if self.thinking else "text", tail)] if tail else []

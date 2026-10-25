# 作者：LHF；时间：2026-10-23；作用：验证思考标签逐字解析与未闭合边界。

import pytest

PROFILE = {"base_url": "https://fixture.invalid/v1", "model": "fixture"}


def test_think_tags_split_at_every_character_and_unclosed_reasoning():
    # 作用：验证逐字分片的 think 标签正确解析，未闭合思考不泄漏到正文。
    from app.response_parser import ReasoningParser

    parser = ReasoningParser()
    fragments = [piece for char in "<think>先计算</think>答案是2" for piece in parser.push(char)]
    fragments.extend(parser.finish())
    assert "".join(text for kind, text in fragments if kind == "reasoning") == "先计算"
    assert "".join(text for kind, text in fragments if kind == "text") == "答案是2"
    parser = ReasoningParser()
    assert parser.push("<think>尚未结束") + parser.finish() == [("reasoning", "尚未结束")]


@pytest.mark.parametrize(
    "text,answer,reasoning",
    [
        ("", "", ""),
        ("普通回答", "普通回答", ""),
        ("<think>一</think>中间<think>二</think>结束", "中间结束", "一二"),
        ("前缀<thi", "前缀<thi", ""),
    ],
)
def test_parser_handles_empty_multiple_and_incomplete_tags(text, answer, reasoning):
    # 作者：LHF；时间：2026-10-23；作用：检查空文本、多思考段和流结束残留标签前缀。
    from app.response_parser import ReasoningParser

    parser = ReasoningParser()
    fragments = parser.push(text) + parser.finish()
    assert "".join(value for kind, value in fragments if kind == "text") == answer
    assert "".join(value for kind, value in fragments if kind == "reasoning") == reasoning

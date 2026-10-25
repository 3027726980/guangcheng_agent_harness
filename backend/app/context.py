# 作者：LHF。
# 注释维护时间：2026-10-20。
# 文件作用：上下文估算、完整工具交互分组与历史摘要压缩。
"""Protocol-aware compaction with immutable full history and explicit coverage."""

# 上下文压缩只更新摘要及其覆盖的消息 ID，数据库中的原始消息始终保留。

import json
from functools import lru_cache

import tiktoken

from app.llm import ModelFailure
from app.model_protocol import deepseek_thinking
from app.prompts import PromptMessages, PromptStore
from app.session_context import ContextState
from app.token_budget import output_reserve


class ContextFailure(Exception):
    pass


@lru_cache(maxsize=32)
def tokenizer_for(model):
    # 按模型缓存编码器；未知模型返回 None，交给 tokens 使用保守估算。
    try:
        return tiktoken.encoding_for_model(model)
    except Exception:
        return None


def tokens(value, model=None) -> int:
    # 作用：估算消息和工具结构的 token 用量，未知模型采用 UTF-8 字节数保守估算。
    """Include serialized tool/message overhead; unknown tokenizers use UTF-8 bytes."""
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    # 工具结构也参与序列化；额外加 64 作为协议开销，估算值不等于供应商实际计费。
    encoder = tokenizer_for(model) if model else None
    count = len(encoder.encode(text, disallowed_special=())) if encoder else len(text.encode("utf-8"))
    return count + 64


def tool_groups(messages):
    # 作用：将工具调用声明和全部结果组成不可拆分的完整消息块。
    """Keep an assistant request and all its tool results in one indivisible block."""
    groups = []
    index = 0
    while index < len(messages):
        current = messages[index]
        group = [current]
        index += 1
        if current.get("tool_calls"):
            # 一条 assistant 工具请求与后续全部 tool 结果必须作为整体保留或摘要。
            expected = {call["id"] for call in current["tool_calls"]}
            found = set()
            while index < len(messages) and messages[index].get("role") == "tool":
                result = messages[index]
                found.add(result["tool_call_id"])
                group.append(result)
                index += 1
            if expected != found:
                raise ContextFailure("工具调用与结果未完整配对")
        elif current.get("role") == "tool":
            raise ContextFailure("发现没有对应调用的工具结果")
        groups.append(group)
    return groups


class ContextManager:
    def __init__(self, db):
        # 作用：绑定保存完整消息和摘要的数据库仓储。
        self.db = db
        self.state = ContextState(db)
        self.prompts = PromptStore()

    async def build(
        self,
        session_id,
        current_run_id,
        settings,
        profile,
        summary_profile,
        schemas,
        system,
        invoke_summary,
        emit,
        force=False,
    ):
        """按预算组装协议完整的历史，必要时压缩旧内容并保留原始记录。"""
        # 从内存可见视图复制本次输入，不重新扫描历史或修改共享消息。
        snapshot = await self.state.snapshot(session_id)
        bundle = self.prompts.load()
        dynamic_system = system is None
        if system is None:
            system = bundle.render("system")
        prior = snapshot.summary
        covered = set(prior.get("covered", [])) if prior else set()
        rows = snapshot.rows
        # 用户请求和引导在写入时已固定工具偏好，直接复用正文，不再遍历历史重新拼接。
        if deepseek_thinking(profile):
            # 旧版本只保存展示思考；回放时尽量利用已有内容补字段，不改写旧数据库。
            # 无历史思考可恢复时使用空串，不根据回答补造内容。新记录始终使用原生字段。
            for row in rows:
                if row["message"]["role"] == "assistant" and "reasoning_content" not in row["message"]:
                    row["message"]["reasoning_content"] = row.get("reasoning", "")
        messages = [row["message"] for row in rows]
        groups = tool_groups(messages)
        reserve = output_reserve(profile)
        capacity = profile.get("context_capacity", 262144)

        def count(value):
            # 作用：按当前对话模型的编码器估算输入用量。
            return tokens(value, profile["model"])

        def summary_count(value):
            # 作用：按摘要模型的编码器估算摘要输入用量。
            return tokens(value, summary_profile["model"])

        margin = max(256, int(capacity * 0.05))
        # 输入预算扣除输出预留和安全余量，系统提示与工具 schema 同样占用输入空间。
        available = capacity - reserve - margin
        if available <= count([system, schemas]) + 256:
            raise ContextFailure("模型容量不足以容纳系统信息和自动预留空间")

        def assemble(summary, suffix):
            # 历史摘要作为资料加入 user 消息，明确其不能覆盖系统指令。
            result = [{"role": "system", "content": system}]
            if summary:
                result.append({"role": "user", "content": bundle.render("summary_prefix", summary=summary)})
            return PromptMessages(
                result + suffix, prompt_versions=bundle.versions, context_version=snapshot.version
            )

        old_summary = prior.get("text", "") if prior else ""
        full = assemble(old_summary, messages)
        initial = count(full) + count(schemas)
        await emit(
            "context.usage",
            {
                "estimated_tokens": initial,
                "capacity": capacity,
                "available_input": available,
                "output_reserve": reserve,
                "budget_source": "automatic",
                "source": profile.get("capacity_source", "default:256K"),
                "estimator": "tiktoken_with_overhead"
                if tokenizer_for(profile["model"])
                else "conservative_utf8_bytes",
                "approximate": True,
            },
        )
        if not force and initial < available * settings.context_trigger:
            return full

        # 固定保留当前任务原请求和已应用引导，较早的工具步骤仍可纳入摘要。
        pinned = [
            row
            for row in rows
            if row.get("run_id") == current_run_id and row.get("input_kind") in {"request", "steering"}
        ]
        pinned_ids = {row["id"] for row in pinned}
        if force:
            # 手动压缩没有新聊天请求，改为保护最近一条用户消息及其后的完整交互。
            latest_user = next(
                (index for index in range(len(rows) - 1, -1, -1) if rows[index]["message"]["role"] == "user"),
                len(rows) - 1,
            )
            pinned_ids.update(row["id"] for row in rows[max(0, latest_user) :])
        selected, selected_ids, kept = [], [], []
        row_index = 0
        for group in groups:
            group_rows = rows[row_index : row_index + len(group)]
            row_index += len(group)
            selected.append((group, group_rows))
        # 至少保留最新完整块，并从后向前扩展，尽量靠近压缩目标预算。
        suffix_budget = available * settings.context_target - count([system, schemas])
        if force:
            suffix_budget = 0
        retained = 0
        for group, group_rows in reversed(selected):
            is_pinned = any(row["id"] in pinned_ids for row in group_rows)
            size = count(group)
            if not kept or is_pinned or retained + size <= max(0, suffix_budget):
                kept.insert(0, (group, group_rows))
                retained += size
            else:
                break
        keep_ids = {row["id"] for _, group_rows in kept for row in group_rows} | pinned_ids
        # 只压缩连续旧前缀，保护点之后的消息全部保留，避免跨越引导导致顺序改变。
        to_summarize = []
        preserve_suffix = False
        for group, group_rows in selected:
            if any(row["id"] in keep_ids for row in group_rows):
                preserve_suffix = True
            if preserve_suffix:
                keep_ids.update(row["id"] for row in group_rows)
            else:
                to_summarize.append((group, group_rows))
        if not to_summarize:
            if initial > available:
                raise ContextFailure("当前请求和必要工具交互已超出容量，无法安全压缩")
            if force:
                await emit("context.compaction_skipped", {"reason": "没有可压缩的较早历史"})
            return full

        await emit("context.compacting", {"before": initial, "groups": len(to_summarize)})
        summary = old_summary
        summary_capacity = summary_profile.get("context_capacity", 262144)
        chunk_budget = int(summary_capacity * 0.65) - 1024
        # 摘要模型可能比对话模型容量小，旧历史需要按完整交互块分批归纳。
        instruction = bundle.render("summary")
        chunks = []
        chunk, chunk_ids = [], []
        for group, group_rows in to_summarize:
            if summary_count([instruction, summary, group]) > chunk_budget:
                await emit("context.compaction_failed", {"retained_original": True})
                if initial <= available:
                    return full
                raise ContextFailure("完整工具步骤超过摘要模型容量，无法无损选择摘要边界")
            if chunk and summary_count([instruction, summary, chunk, group]) > chunk_budget:
                chunks.append((chunk, chunk_ids))
                chunk, chunk_ids = [], []
            chunk.extend(group)
            chunk_ids.extend(row["id"] for row in group_rows)
        if chunk:
            chunks.append((chunk, chunk_ids))
        try:
            for chunk, ids in chunks:
                # 每个分块是一次新请求；读取最新摘要模板，重试由 _invoke 固定本次版本。
                summary_bundle = self.prompts.load()
                prompt = [
                    {"role": "system", "content": summary_bundle.render("summary")},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {"previous_summary": summary, "history": chunk}, ensure_ascii=False
                        ),
                    },
                ]
                if (
                    summary_count(prompt)
                    + output_reserve(summary_profile)
                    + max(256, int(summary_capacity * 0.05))
                    > summary_capacity
                ):
                    raise ContextFailure("摘要输入超过摘要模型容量，原历史未修改")
                # 不传固定摘要输出上限，由供应商决定长度；被截断的摘要不能提交。
                prompt = PromptMessages(
                    prompt, prompt_versions=summary_bundle.versions, context_version=snapshot.version
                )
                reply = await invoke_summary(summary_profile, prompt, None)
                if reply.finish_reason == "length":
                    raise ContextFailure("摘要生成被供应商输出上限截断，未提交不完整摘要")
                if not reply.text.strip() or reply.calls or reply.finish_reason not in {"stop", "end_turn"}:
                    raise ContextFailure("摘要不完整，原历史未修改")
                summary = reply.text.strip()
                selected_ids.extend(ids)
        except (ContextFailure, ModelFailure, TimeoutError) as error:
            await emit(
                "context.compaction_failed",
                {
                    "retained_original": True,
                    "reason": str(error) or "摘要请求超时",
                },
            )
            if initial <= available:
                return full
            raise ContextFailure("上下文压缩失败，已保留原摘要及完整历史") from None
        result = assemble(summary, [row["message"] for row in rows if row["id"] in keep_ids])
        final = count(result) + count(schemas)
        if force and final >= initial:
            await emit("context.compaction_skipped", {"reason": "摘要未减少上下文用量，已保留原摘要与历史"})
            return full
        if final > available:
            await emit("context.compaction_failed", {"retained_original": True})
            if initial <= available:
                return full
            raise ContextFailure("压缩后必要内容仍然超出容量，原摘要与历史未修改")
        summary_record = {
            "id": "summary:" + session_id,
            "text": summary,
            "covered": sorted(covered | set(selected_ids)),
            "before": initial,
            "after": final,
            "model": summary_profile["model"],
        }
        if not await self.state.compact(session_id, snapshot.version, selected_ids, summary_record):
            # 摘要生成期间有新消息：丢弃过时结果，从最新状态重新构建，绝不覆盖追加。
            await emit("context.compaction_skipped", {"reason": "上下文版本已变化，重新构建"})
            return await self.build(
                session_id,
                current_run_id,
                settings,
                profile,
                summary_profile,
                schemas,
                None if dynamic_system else system,
                invoke_summary,
                emit,
                force=force,
            )
        result.context_version = snapshot.version + 1
        await emit(
            "context.compacted",
            {"before": initial, "after": final, "summary": summary, "covered_messages": len(selected_ids)},
        )
        # 摘要等待期间模板可能被修改，随后对话输入应使用新模板重新组装和验算容量。
        if self.prompts.load().versions != bundle.versions:
            return await self.build(
                session_id,
                current_run_id,
                settings,
                profile,
                summary_profile,
                schemas,
                None if dynamic_system else system,
                invoke_summary,
                emit,
            )
        return result

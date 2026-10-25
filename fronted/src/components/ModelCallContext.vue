<template>
  <section class="call-context" aria-label="模型调用输入">
    <div class="call-toolbar">
      <strong>模型调用输入</strong>
      <button type="button" @click="reload">刷新</button>
    </div>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="!loading && !calls.length">未记录输入快照；旧调用不会补造历史输入。</p>
    <p v-if="loading" role="status">正在读取调用记录…</p>
    <div v-for="call in calls" :key="call.call_id" class="call-row">
      <button type="button" @click="open(call.call_id)">
        {{ call.purpose === 'summary' ? '摘要' : '对话' }} · {{ call.model }} ·
        尝试 {{ call.attempt }} · {{ statusLabel(call.status) }} ·
        {{ new Date(call.timestamp * 1000).toLocaleTimeString() }}
      </button>
      <div v-if="selected === call.call_id && detail" class="call-detail">
        <p>上下文版本 {{ detail.context_version ?? '未记录' }} · 调用 {{ call.call_id }}</p>
        <button type="button" @click="copy">复制完整 JSON</button>
        <span role="status">{{ copied }}</span>
        <article v-for="(message, index) in detail.request.messages" :key="index">
          <strong>{{ index + 1 }} · {{ message.role }}</strong>
          <pre>{{ typeof message.content === 'string' ? message.content : JSON.stringify(message.content, null, 2) }}</pre>
          <details v-if="message.tool_calls || message.tool_call_id || message.reasoning_content !== undefined">
            <summary>工具协议及思考字段</summary>
            <pre>{{ JSON.stringify(message, null, 2) }}</pre>
          </details>
        </article>
        <details><summary>工具定义</summary><pre>{{ JSON.stringify(detail.request.tools || [], null, 2) }}</pre></details>
        <details><summary>请求参数与提示词版本</summary><pre>{{ JSON.stringify(parameters, null, 2) }}</pre></details>
        <details><summary>响应 / 失败信息</summary><pre>{{ JSON.stringify({ status: detail.status, response: detail.response, error: detail.error, partial_response: detail.partial_response }, null, 2) }}</pre></details>
        <details><summary>完整原始 JSON</summary><pre>{{ JSON.stringify(detail, null, 2) }}</pre></details>
      </div>
    </div>
    <button v-if="cursor !== null" type="button" :disabled="loading" @click="loadMore">加载更多调用</button>
  </section>
</template>

<script setup lang="ts">
// 作者：LHF；时间：2026-10-22；作用：按需分页读取并展示每次模型实际输入快照。
import { computed, ref, watch } from "vue";
import { api } from "@/api/harness";
import type { ModelCall, ModelCallDetail } from "@/types/harness";

const props = defineProps<{ sessionId: string; runId: string; revision: number }>();
const calls = ref<ModelCall[]>([]), detail = ref<ModelCallDetail | null>(null);
const selected = ref(""), error = ref(""), copied = ref("");
const cursor = ref<number | null>(null), loading = ref(false);
let generation = 0;
const parameters = computed(() => {
  // 作用：将消息与工具之外的请求参数单独呈现。
  if (!detail.value) return {};
  const { messages: _messages, tools: _tools, ...rest } = detail.value.request;
  return { ...rest, prompt_versions: detail.value.prompt_versions };
});

function statusLabel(status: string) {
  // 作用：将快照调用状态转换为界面文案。
  return ({ sending: "已准备发送", completed: "已返回", failed: "失败", cancelled: "已取消" } as Record<string, string>)[status] || status;
}

async function load(reset: boolean) {
  // 作用：分页获取独立调用列表，用代次隔离切换会话和迟到响应。
  const epoch = generation;
  if (!props.sessionId || !props.runId) return;
  const after = reset ? 0 : cursor.value;
  if (after === null) return;
  loading.value = true;
  error.value = "";
  try {
    const result = await api<{ items: ModelCall[]; next_cursor: number | null }>(
      `/sessions/${encodeURIComponent(props.sessionId)}/model-calls?run_id=${encodeURIComponent(props.runId)}&after=${after}`,
    );
    if (epoch !== generation) return;
    calls.value = reset ? result.items : [...calls.value, ...result.items];
    cursor.value = result.next_cursor;
  } catch (failure) {
    if (epoch === generation) error.value = failure instanceof Error ? failure.message : String(failure);
  } finally {
    if (epoch === generation) loading.value = false;
  }
}

function reload() {
  // 作用：刷新当前任务的第一页和已展开调用的最新状态。
  generation++;
  loading.value = false;
  void load(true);
  if (selected.value) void open(selected.value);
}

function loadMore() {
  // 作用：保留已有条目，继续读取下一页。
  if (!loading.value) void load(false);
}

async function open(id: string) {
  // 作用：点击调用后才读取完整正文，防止大上下文进入常规 SSE 更新。
  const epoch = generation;
  selected.value = id;
  detail.value = null;
  copied.value = "";
  try {
    const result = await api<ModelCallDetail>(`/sessions/${encodeURIComponent(props.sessionId)}/model-calls/${encodeURIComponent(id)}`);
    if (epoch === generation && selected.value === id) detail.value = result;
  } catch (failure) {
    if (epoch === generation && selected.value === id) error.value = failure instanceof Error ? failure.message : String(failure);
  }
}

async function copy() {
  // 作用：复制完整脱敏快照，并反馈剪贴板不可用等失败。
  try {
    await navigator.clipboard.writeText(JSON.stringify(detail.value, null, 2));
    copied.value = "已复制";
  } catch {
    copied.value = "复制失败，可展开原始 JSON 手动复制";
  }
}

watch(() => [props.sessionId, props.runId], () => {
  // 作用：切换任务清空旧详情，避免跨会话内容残留。
  selected.value = "";
  detail.value = null;
  calls.value = [];
  cursor.value = null;
  reload();
}, { immediate: true });
watch(() => props.revision, reload);
</script>

<style scoped>
.call-context { margin: 12px 0; padding: 12px; border: 1px solid #dce6df; border-radius: 8px; }
.call-toolbar { display: flex; justify-content: space-between; }
.call-row { margin-top: 10px; }
button { cursor: pointer; padding: 5px 9px; border: 1px solid #d1ddd5; background: #f5f9f6; border-radius: 4px; color: #244c35; text-align: left; }
.call-detail { margin-top: 8px; }
article { margin: 12px 0; padding: 9px; background: #f6f8f7; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 12px; max-height: 480px; overflow: auto; }
details { margin: 8px 0; }
</style>

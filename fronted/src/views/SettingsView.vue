<template>
  <div class="settings-page">
    <div class="page-heading">
      <div class="eyebrow">CONFIGURATION</div>
      <h1>全局设置</h1>
      <p>所有演示用户共用。修改仅影响之后开始执行的任务。</p>
    </div>
    <n-card title="模型连接" class="settings-card" :bordered="false">
      <div class="model-grid">
        <div class="model-list">
          <button
            v-for="profile in state.profiles"
            :key="profile.id"
            class="model-row"
            :class="{ selected: editingId === profile.id }"
            @click="editProfile(profile)"
          >
            <strong>{{ profile.name }}</strong
            ><small>{{ profile.model }}</small>
            <n-tag
              size="small"
              :type="
                profile.test_status === 'connected' ? 'success' : 'warning'
              "
              >{{
                profile.test_status === "connected" ? "连接已验证" : "连接失败"
              }}</n-tag
            >
            <small
              >Context {{ formatTokenCount(profile.context_capacity) }} ·
              {{
                profile.capacity_source.startsWith("default")
                  ? "默认值"
                  : "供应商读取"
              }}</small
            >
          </button>
          <n-button block dashed @click="resetProfile">＋ 新增连接</n-button>
        </div>
        <n-form label-placement="top" class="model-form" @submit.prevent>
          <n-form-item label="连接名称"
            ><n-input
              v-model:value="modelForm.name"
              placeholder="例如：我的模型服务"
          /></n-form-item>
          <n-form-item label="Base URL"
            ><n-input
              v-model:value="modelForm.base_url"
              placeholder="https://api.openai.com/v1"
          /></n-form-item>
          <n-form-item label="API Key"
            ><n-input
              v-model:value="modelForm.api_key"
              type="password"
              show-password-on="click"
              :placeholder="
                editingId ? '留空保留已保存的密钥' : '本地无密钥服务可留空'
              "
          /></n-form-item>
          <n-form-item label="模型 ID"
            ><n-input
              v-model:value="modelForm.model"
              placeholder="填写供应商的模型 ID"
          /></n-form-item>
          <n-form-item label="输出限制参数"
            ><n-select
              v-model:value="modelForm.output_token_parameter"
              :options="[
                { label: 'max_tokens（常见兼容接口）', value: 'max_tokens' },
                {
                  label: 'max_completion_tokens',
                  value: 'max_completion_tokens',
                },
              ]"
          /></n-form-item>
          <n-form-item label="思考模式">
            <div>
              <n-switch v-model:value="modelForm.thinking_enabled" aria-label="开启思考模式">
                <template #checked>已开启</template>
                <template #unchecked>已关闭</template>
              </n-switch>
              <p class="field-help">
                请自行查阅所用模型的 API 开发文档，确认该模型是否支持思考模式及其调用方式。
              </p>
            </div>
          </n-form-item>
          <p class="field-help">
            保存时自动测试连接并读取容量；读取不到使用默认
            {{
              formatTokenCount(262144)
            }}
            tokens。连接测试不代表所有工具能力均已验证。
          </p>
          <n-space
            ><n-button
              type="primary"
              :loading="testing"
              :disabled="!modelForm.name || !modelForm.model"
              @click="saveProfile"
              >保存并测试连接</n-button
            >
            <n-button v-if="editingId" :loading="testing" @click="testProfile"
              >重新测试</n-button
            >
            <n-button
              v-if="editingId"
              type="error"
              secondary
              @click="deleteProfile"
              >删除</n-button
            ></n-space
          >
          <n-alert
            v-if="testMessage"
            :type="testSuccess ? 'success' : 'warning'"
            style="margin-top: 16px"
            >{{ testMessage }}</n-alert
          >
        </n-form>
      </div>
    </n-card>

    <n-card title="执行与上下文" class="settings-card" :bordered="false">
      <n-form label-placement="top">
        <div class="fields-grid">
          <n-form-item label="对话模型"
            ><n-select
              v-model:value="form.default_profile_id"
              :options="modelOptions"
              placeholder="选择已验证连接的模型"
              clearable
          /></n-form-item>
          <n-form-item label="摘要模型"
            ><n-select
              v-model:value="form.summary_profile_id"
              :options="modelOptions"
              placeholder="留空复用对话模型"
              clearable
          /></n-form-item>
          <n-form-item
            v-for="field in fields"
            :key="field.key"
            :label="field.label"
          >
            <div class="number-field">
              <n-input-number
                :value="Number(form[field.key])"
                :min="field.min"
                :step="field.step || 1"
                @update:value="
                  /* 作用：更新对应预算字段，清空时恢复该字段的最小值。 */ (value) => (form[field.key] = value ?? field.min)
                "
              /><small>{{ field.help }}</small>
            </div>
          </n-form-item>
        </div>
        <n-alert type="info" :show-icon="false" style="margin-bottom: 20px"
          >摘要和重试计入模型调用预算，等待时间计入总时长。达到硬限制不会额外调用模型收尾。Context
          按容量的触发比例压缩，完整历史仍保留。对话输出上限使用供应商默认值，Context
          预留自动管理，摘要长度由模型决定。</n-alert
        >
        <n-button type="primary" :loading="saving" @click="saveSettings"
          >保存全局运行设置</n-button
        >
        <span v-if="settingsSaved" class="saved-label"
          >已保存，后续任务生效</span
        >
      </n-form>
    </n-card>
  </div>
</template>

<script setup lang="ts">
// 作者：LHF。
// 注释维护时间：2026-10-20。
// 文件作用：编辑模型连接及全局运行预算。
import { computed, reactive, ref, watch } from "vue";
import { formatTokenCount } from "@/lib/token-format";
import {
  NAlert,
  NButton,
  NCard,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NSelect,
  NSwitch,
  NSpace,
  NTag,
} from "naive-ui";
import { api, loadSettings, safely, state } from "@/api/harness";
import type { Profile } from "@/types/harness";

const editingId = ref(""),
  testing = ref(false),
  saving = ref(false),
  settingsSaved = ref(false);
const testMessage = ref(""),
  testSuccess = ref(false);
const modelForm = reactive({
  name: "",
  base_url: "https://api.openai.com/v1",
  api_key: "",
  model: "",
  output_token_parameter: "max_tokens",
  thinking_enabled: false,
});
const form = reactive<Record<string, any>>({});
// 页面表单使用本地副本，输入时不直接更改应用已加载的全局运行设置。
watch(
  /* 作用：读取监听所依赖的状态，变化后触发界面同步。 */ () => state.settings,
  /* 作用：将加载的全局设置复制到本地表单，避免直接修改共享状态。 */ (settings) => {
    Object.assign(form, settings);
  },
  { immediate: true },
);
const modelOptions = computed(/* 作用：只列出连接测试通过的模型配置。 */ () =>
  // 只有连接测试通过的模型可选；后端保存设置时还会再次校验。
  state.profiles
    .filter(/* 作用：仅保留已通过连接测试的模型。 */ (profile) => profile.test_status === "connected")
    .map(/* 作用：只列出连接测试通过的模型配置。 */ (profile) => ({
      label: `${profile.name} · ${profile.model}`,
      value: profile.id,
    })),
);
const fields = [
  // 用统一配置渲染预算字段；字段键与后端 RuntimeSettings 保持对应。
  {
    key: "max_model_calls",
    label: "模型调用上限",
    min: 1,
    help: "包含摘要及重试，默认20次",
  },
  {
    key: "max_tool_calls",
    label: "工具调用上限",
    min: 1,
    help: "每个工具调用单独计数，默认40次",
  },
  {
    key: "max_seconds",
    label: "执行总时长 / 秒",
    min: 1,
    help: "不包含排队等待，默认300秒",
  },
  {
    key: "model_timeout",
    label: "单次模型超时 / 秒",
    min: 1,
    help: "同时受剩余总时长约束，默认60秒",
  },
  {
    key: "tool_timeout",
    label: "单次工具超时 / 秒",
    min: 1,
    help: "取消写入时仍需确认提交结果，默认10秒",
  },
  {
    key: "retries",
    label: "自动重试次数",
    min: 0,
    help: "首次失败后最多再试3次，可设0关闭",
  },
  {
    key: "retry_seconds",
    label: "重试间隔 / 秒",
    min: 0,
    help: "默认30秒，遵循更长的供应商等待要求",
  },
  {
    key: "tool_concurrency",
    label: "只读工具并行上限",
    min: 1,
    help: "默认4；含待办的批次串行",
  },
  {
    key: "context_trigger",
    label: "Context 压缩触发比例",
    min: 0.01,
    step: 0.05,
    help: "默认0.8，必须大于压缩目标且小于1",
  },
  {
    key: "context_target",
    label: "Context 压缩目标比例",
    min: 0.01,
    step: 0.05,
    help: "默认0.5；不强行删除当前任务必要信息",
  },
];
function resetProfile() {
  // 作用：退出已有连接编辑，恢复新增模型表单的默认值。
  // 退出编辑已有连接，恢复新增连接表单的默认值。
  editingId.value = "";
  Object.assign(modelForm, {
    name: "",
    base_url: "https://api.openai.com/v1",
    api_key: "",
    model: "",
    output_token_parameter: "max_tokens",
    thinking_enabled: false,
  });
  testMessage.value = "";
}
function editProfile(profile: Profile) {
  // 作用：加载已有模型连接到编辑表单，密钥保持空白以沿用已存值。
  // 密钥不会从服务端回显；留空提交代表保留原密钥。
  editingId.value = profile.id;
  Object.assign(modelForm, {
    name: profile.name,
    base_url: profile.base_url,
    model: profile.model,
    api_key: "",
    output_token_parameter: profile.output_token_parameter || "max_tokens",
    thinking_enabled: profile.thinking_enabled ?? false,
  });
  testMessage.value = "";
}
function report(profile: Profile) {
  // 作用：显示模型连接测试结果，并区分容量来源。
  // 只展示服务端实际探测到的结果，并明确容量来自供应商还是默认值。
  testSuccess.value = profile.test_status === "connected";
  testMessage.value = testSuccess.value
    ? `连接成功。Context ${formatTokenCount(profile.context_capacity)} tokens，${profile.capacity_source.startsWith("default") ? "使用默认容量" : "已从供应商读取容量"}。`
    : "连接失败，配置已保留。请检查地址、模型、密钥及供应商支持情况。";
}
async function saveProfile() {
  // 作用：新增或更新连接，等待后端测试并刷新配置列表。
  // 保存接口会真实测试模型连接，完成后刷新全局连接列表及配置。
  testing.value = true;
  await safely(/* 作用：新增或更新连接，等待后端测试并刷新配置列表。 */ async () => {
    const profile = await api<Profile>(
      editingId.value ? `/models/${editingId.value}` : "/models",
      editingId.value ? "PUT" : "POST",
      modelForm,
    );
    editingId.value = profile.id;
    modelForm.api_key = "";
    report(profile);
    await loadSettings();
  });
  testing.value = false;
}
async function testProfile() {
  // 作用：重新测试已保存的模型连接并更新界面状态。
  // 重测已保存的连接，当前表单尚未保存的改动不会参与本次测试。
  testing.value = true;
  await safely(/* 作用：重新测试已保存的模型连接并更新界面状态。 */ async () => {
    report(await api(`/models/${editingId.value}/test`, "POST"));
    await loadSettings();
  });
  testing.value = false;
}
async function deleteProfile() {
  // 作用：删除当前模型连接，成功后重置表单并刷新列表。
  // 正在被全局设置引用的连接由后端拒绝删除，错误交给统一提示处理。
  await safely(/* 作用：删除当前模型连接，成功后重置表单并刷新列表。 */ async () => {
    await api(`/models/${editingId.value}`, "DELETE");
    resetProfile();
    await loadSettings();
  });
}
async function saveSettings() {
  // 作用：保存全局运行设置，刷新配置并提示后续任务生效。
  // 全局配置保存成功后刷新状态，新设置用于后续开始执行的任务。
  saving.value = true;
  settingsSaved.value = false;
  await safely(/* 作用：保存全局运行设置，刷新配置并提示后续任务生效。 */ async () => {
    await api("/settings", "PUT", form);
    await loadSettings();
    settingsSaved.value = true;
  });
  saving.value = false;
}
</script>

<style scoped>
.settings-page {
  max-width: 1100px;
  margin: 0 auto;
}
.page-heading {
  margin: 10px 0 28px;
}
.eyebrow {
  font-size: 11px;
  color: #638c72;
  letter-spacing: 0.18em;
  margin-bottom: 8px;
}
.page-heading h1 {
  font-size: 26px;
  color: #294333;
  font-weight: 600;
}
.page-heading p {
  color: #87958c;
  font-size: 13px;
  margin-top: 8px;
}
.settings-card {
  margin-bottom: 22px;
  border-radius: 14px;
  border: 1px solid #e1e8e1 !important;
}
.model-grid {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 32px;
}
.model-list {
  border-right: 1px solid #ecf0eb;
  padding-right: 24px;
}
.model-row {
  display: block;
  width: 100%;
  padding: 14px;
  text-align: left;
  border: 1px solid #e2e9e1;
  border-radius: 9px;
  background: #fafcf8;
  cursor: pointer;
  margin-bottom: 10px;
  color: #38523e;
}
.model-row.selected {
  border-color: #74a582;
  background: #edf5ec;
}
.model-row small {
  display: block;
  font-size: 11px;
  color: #869981;
  margin: 6px 0;
  overflow-wrap: anywhere;
}
.model-row .n-tag {
  margin-top: 5px;
}
.model-form {
  max-width: 620px;
}
.field-help {
  font-size: 12px;
  color: #8c9b90;
  line-height: 1.8;
  margin-bottom: 18px;
}
.fields-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 2px 30px;
}
.number-field {
  width: 100%;
}
.number-field .n-input-number {
  width: 100%;
}
.number-field small {
  display: block;
  color: #91a08f;
  font-size: 11px;
  line-height: 1.6;
  margin-top: 6px;
}
.saved-label {
  font-size: 12px;
  color: #57916b;
  margin-left: 16px;
}
@media (max-width: 700px) {
  .model-grid,
  .fields-grid {
    grid-template-columns: 1fr;
  }
  .model-list {
    border-right: 0;
    padding-right: 0;
  }
  .model-form {
    max-width: none;
  }
}
</style>

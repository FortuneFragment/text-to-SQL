<template>
  <section class="model-page">
    <header class="page-header panel">
      <div>
        <h2>模型配置</h2>
        <p>管理大语言模型、向量模型与重排模型运行配置。每类模型仅一个启用项。</p>
      </div>
      <div class="header-tools">
        <label class="filter-field">
          <span>模型类型</span>
          <select v-model="kindFilter" @change="loadConfigs">
            <option value="">全部</option>
            <option v-for="meta in modelKinds" :key="meta.kind" :value="meta.kind">{{ meta.title }}</option>
          </select>
        </label>
        <button class="btn-ghost" :disabled="loading.list" @click="loadConfigs">刷新</button>
        <button class="btn-primary" @click="openCreate">新建模型</button>
      </div>
    </header>

    <div v-if="notice" class="notice" :class="noticeType">{{ notice }}</div>

    <section class="summary-strip">
      <article v-for="meta in modelKinds" :key="meta.kind" class="summary-card">
        <span>{{ meta.title }}</span>
        <strong>{{ activeSummary(meta.kind) }}</strong>
        <small>{{ countByKind(meta.kind) }} 个配置</small>
      </article>
    </section>

    <section class="panel table-panel">
      <div class="table-wrap">
        <table class="model-table">
          <thead>
            <tr>
              <th>编号</th>
              <th>名称</th>
              <th>类型</th>
              <th>服务商</th>
              <th>模型标识</th>
              <th>接口地址</th>
              <th>运行参数</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading.list">
              <td colspan="9" class="empty-cell">加载中...</td>
            </tr>
            <tr v-else-if="configs.length === 0">
              <td colspan="9" class="empty-cell">暂无模型配置，请先新建。</td>
            </tr>
            <template v-else>
              <tr v-for="item in configs" :key="item.id" :class="{ active: item.is_active }">
                <td class="mono">#{{ item.id }}</td>
                <td>
                  <div class="name-cell">
                    <strong>{{ item.name }}</strong>
                    <span>{{ item.has_api_key ? "密钥已保存" : "未保存密钥" }}</span>
                  </div>
                </td>
                <td>
                  <span class="kind-chip">{{ kindTitle(modelType(item)) }}</span>
                </td>
                <td>{{ providerLabel(item.provider) }}</td>
                <td class="mono break-cell">{{ item.model_name }}</td>
                <td class="break-cell" :title="baseUrl(item)">{{ baseUrl(item) }}</td>
                <td>
                  <div class="runtime-cell">
                    <span>{{ item.timeout_seconds }} 秒超时</span>
                    <span v-if="modelType(item) === 'embedding'">{{ item.vector_dim || "自动探测" }} 维</span>
                    <span v-if="modelType(item) === 'embedding'">批量 {{ item.batch_size || "-" }}</span>
                  </div>
                </td>
                <td>
                  <span class="status-chip" :class="{ active: item.is_active }">
                    {{ item.is_active ? "已启用" : "备用" }}
                  </span>
                </td>
                <td>
                  <div class="row-actions">
                    <button class="btn-link" @click="openEdit(item)">编辑</button>
                    <button class="btn-link" :disabled="item.is_active || loading.action" @click="activateConfig(item)">启用</button>
                    <button class="btn-link danger" :disabled="item.is_active || loading.action" @click="deleteConfig(item)">删除</button>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="dialogVisible" class="dialog-mask" @click.self="closeDialog">
      <section class="model-dialog" role="dialog" aria-modal="true" aria-labelledby="model-dialog-title">
        <header class="dialog-header">
          <div>
            <h3 id="model-dialog-title">{{ editingId ? "编辑模型" : "新建模型" }}</h3>
            <p>{{ editingId ? "更新运行参数。访问密钥留空则保持原值。" : "创建后默认启用。" }}</p>
          </div>
          <button class="btn-close" type="button" aria-label="关闭弹窗" @click="closeDialog">×</button>
        </header>

        <form class="dialog-body" @submit.prevent="saveConfig">
          <div class="form-grid">
            <label>
              <span>模型类型</span>
              <select v-model="form.kind" :disabled="!!editingId" @change="handleKindChange">
                <option v-for="meta in modelKinds" :key="meta.kind" :value="meta.kind">{{ meta.title }}</option>
              </select>
            </label>
            <label>
              <span>服务商</span>
              <select v-model="form.provider">
                <option v-for="item in visibleProviderOptions" :key="item.provider" :value="item.provider">
                  {{ item.label }}
                </option>
              </select>
            </label>
            <label>
              <span>配置名称</span>
              <input v-model.trim="form.name" placeholder="生产模型" />
            </label>
            <label>
              <span>模型标识</span>
              <input v-model.trim="form.model_name" placeholder="模型名称或部署名" />
            </label>
            <label class="span-2">
              <span>接口地址</span>
              <input v-model.trim="form.base_url" placeholder="模型服务接口地址" />
            </label>
            <label>
              <span>访问密钥</span>
              <input
                v-model="form.api_key"
                type="password"
                :placeholder="editingId ? '留空保持已保存密钥' : '可留空'"
              />
            </label>
            <label>
              <span>请求超时（秒）</span>
              <input v-model="form.timeout_seconds" type="number" min="1" max="3600" />
            </label>
            <label v-if="form.kind === 'embedding'">
              <span>向量维度</span>
              <input v-model="form.vector_dim" type="number" min="1" max="65536" placeholder="可留空，自动探测" />
            </label>
            <label v-if="form.kind === 'embedding'">
              <span>批量大小</span>
              <input v-model="form.batch_size" type="number" min="1" max="2048" />
            </label>
            <label>
              <span>重试次数</span>
              <input v-model="form.max_retries" type="number" min="0" max="10" />
            </label>
            <label>
              <span>重试退避（秒）</span>
              <input v-model="form.retry_backoff_seconds" type="number" min="0" max="60" step="0.1" />
            </label>
            <label class="span-2">
              <span>额外参数</span>
              <textarea v-model.trim="form.extra_params" rows="3" placeholder="可留空"></textarea>
            </label>
          </div>

          <div class="switch-row">
            <label class="check-label">
              <input v-model="form.is_active" type="checkbox" />
              <span>保存后设为启用</span>
            </label>
          </div>

          <footer class="dialog-footer">
            <button type="button" class="btn-ghost" @click="closeDialog">取消</button>
            <button class="btn-primary" :disabled="loading.save">
              {{ loading.save ? "保存中..." : "保存" }}
            </button>
          </footer>
        </form>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import { apiRequest } from "../api/client";

const modelKinds = [
  { kind: "llm", title: "大语言模型" },
  { kind: "embedding", title: "向量模型" },
  { kind: "rerank", title: "重排模型" },
];

const providerChineseLabels = {
  openai: "开放人工智能",
  dashscope: "阿里云通义",
  zhipu: "智谱智能",
  baichuan: "百川智能",
  moonshot: "月之暗面",
  deepseek: "深度求索",
  ollama: "本地模型",
  azure_openai: "微软云模型",
  anthropic: "克劳德模型",
  cohere: "科希尔模型",
  jina: "吉纳智能",
  local: "本地部署",
  custom: "自定义兼容接口",
};

const fallbackProviderOptions = [
  { provider: "openai", label: providerChineseLabels.openai, supportedKinds: ["llm", "embedding"] },
  { provider: "dashscope", label: providerChineseLabels.dashscope, supportedKinds: ["llm", "embedding", "rerank"] },
  { provider: "zhipu", label: providerChineseLabels.zhipu, supportedKinds: ["llm", "embedding"] },
  { provider: "baichuan", label: providerChineseLabels.baichuan, supportedKinds: ["llm", "embedding"] },
  { provider: "moonshot", label: providerChineseLabels.moonshot, supportedKinds: ["llm"] },
  { provider: "deepseek", label: providerChineseLabels.deepseek, supportedKinds: ["llm"] },
  { provider: "ollama", label: providerChineseLabels.ollama, supportedKinds: ["llm", "embedding"] },
  { provider: "azure_openai", label: providerChineseLabels.azure_openai, supportedKinds: ["llm", "embedding"] },
  { provider: "anthropic", label: providerChineseLabels.anthropic, supportedKinds: ["llm"] },
  { provider: "cohere", label: providerChineseLabels.cohere, supportedKinds: ["llm", "embedding", "rerank"] },
  { provider: "jina", label: providerChineseLabels.jina, supportedKinds: ["embedding", "rerank"] },
  { provider: "local", label: providerChineseLabels.local, supportedKinds: ["llm", "embedding", "rerank"] },
  { provider: "custom", label: providerChineseLabels.custom, supportedKinds: ["llm", "embedding", "rerank"] },
];

const loading = reactive({
  list: false,
  save: false,
  action: false,
});
const configs = ref([]);
const providerOptions = ref([...fallbackProviderOptions]);
const kindFilter = ref("");
const dialogVisible = ref(false);
const editingId = ref(null);
const notice = ref("");
const noticeType = ref("info");
const form = reactive(createEmptyForm("llm"));

const visibleProviderOptions = computed(() =>
  providerOptions.value.filter((item) => item.supportedKinds.includes(form.kind))
);

function createEmptyForm(kind) {
  return {
    kind,
    name: "",
    provider: "custom",
    base_url: "",
    model_name: "",
    api_key: "",
    extra_params: "",
    timeout_seconds: 120,
    vector_dim: kind === "embedding" ? "" : "",
    batch_size: kind === "embedding" ? 32 : "",
    verify_ssl: true,
    ca_bundle: "",
    max_retries: 2,
    retry_backoff_seconds: 0.5,
    trust_env: true,
    is_active: true,
  };
}

function setNotice(message, type = "info") {
  notice.value = message;
  noticeType.value = type;
}

function resetForm(kind = "llm") {
  Object.assign(form, createEmptyForm(kind));
}

function handleKindChange() {
  if (form.kind === "embedding" && !form.batch_size) {
    form.batch_size = 32;
  }
  if (form.kind !== "embedding") {
    form.vector_dim = "";
    form.batch_size = "";
  }
  if (!visibleProviderOptions.value.some((item) => item.provider === form.provider)) {
    form.provider = visibleProviderOptions.value[0]?.provider || "custom";
  }
}

function unwrapData(payload) {
  if (payload && typeof payload === "object" && "data" in payload && "code" in payload) {
    return payload.data;
  }
  return payload;
}

function modelType(item) {
  return item?.model_type || item?.kind || "";
}

function baseUrl(item) {
  return item?.api_base_url || item?.base_url || "";
}

function kindTitle(kind) {
  return modelKinds.find((item) => item.kind === kind)?.title || kind;
}

function providerLabel(provider) {
  return providerChineseLabels[provider] || providerOptions.value.find((item) => item.provider === provider)?.label || provider;
}

function countByKind(kind) {
  return configs.value.filter((item) => modelType(item) === kind).length;
}

function activeSummary(kind) {
  const active = configs.value.find((item) => modelType(item) === kind && item.is_active);
  return active ? active.name : "未启用";
}

function toPositiveNumber(value, fallback = null) {
  const raw = String(value ?? "").trim();
  if (!raw) return fallback;
  const number = Number(raw);
  return Number.isFinite(number) && number > 0 ? number : fallback;
}

function toNonNegativeNumber(value, fallback = 0) {
  const raw = String(value ?? "").trim();
  if (!raw) return fallback;
  const number = Number(raw);
  return Number.isFinite(number) && number >= 0 ? number : fallback;
}

function validateForm() {
  if (!form.name || !form.provider || !form.base_url || !form.model_name) {
    setNotice("模型类型、服务商、配置名称、接口地址和模型标识为必填项。", "error");
    return false;
  }
  if (!toPositiveNumber(form.timeout_seconds)) {
    setNotice("请求超时必须是大于 0 的数字。", "error");
    return false;
  }
  if (form.kind === "embedding" && String(form.vector_dim ?? "").trim() && !toPositiveNumber(form.vector_dim)) {
    setNotice("向量模型的向量维度如果填写，必须是大于 0 的数字。", "error");
    return false;
  }
  return true;
}

function buildPayload() {
  const payload = {
    model_type: form.kind,
    name: form.name.trim(),
    provider: form.provider.trim() || "custom",
    api_base_url: form.base_url.trim(),
    model_name: form.model_name.trim(),
    extra_params: form.extra_params.trim() || null,
    timeout_seconds: toPositiveNumber(form.timeout_seconds, 120),
    verify_ssl: Boolean(form.verify_ssl),
    ca_bundle: form.ca_bundle.trim() || null,
    max_retries: Math.min(10, toNonNegativeNumber(form.max_retries, 2)),
    retry_backoff_seconds: toNonNegativeNumber(form.retry_backoff_seconds, 0.5),
    trust_env: Boolean(form.trust_env),
    is_active: Boolean(form.is_active),
  };

  const apiKey = String(form.api_key || "").trim();
  if (apiKey) {
    payload.api_key = apiKey;
  }

  if (form.kind === "embedding") {
    payload.vector_dim = toPositiveNumber(form.vector_dim, null);
    payload.batch_size = toPositiveNumber(form.batch_size, 32);
  }

  return payload;
}

async function loadConfigs() {
  loading.list = true;
  try {
    const query = kindFilter.value ? `?model_type=${encodeURIComponent(kindFilter.value)}` : "";
    const data = unwrapData(await apiRequest(`/models${query}`));
    configs.value = Array.isArray(data) ? data : [];
  } catch (error) {
    setNotice(`加载模型配置失败：${error.message}`, "error");
  } finally {
    loading.list = false;
  }
}

async function loadProviders() {
  try {
    const data = unwrapData(await apiRequest("/models/providers"));
    const items = Array.isArray(data) ? data : [];
    if (!items.length) return;
    providerOptions.value = items.map((item) => ({
      provider: item.provider,
      label: providerChineseLabels[item.provider] || item.display_name || item.provider,
      supportedKinds: item.supported_types || item.supported_kinds || [],
    }));
  } catch {
    providerOptions.value = [...fallbackProviderOptions];
  }
}

function openCreate() {
  editingId.value = null;
  resetForm(kindFilter.value || "llm");
  dialogVisible.value = true;
}

function openEdit(item) {
  editingId.value = item.id;
  Object.assign(form, {
    kind: modelType(item) || "llm",
    name: item.name || "",
    provider: item.provider || "custom",
    base_url: baseUrl(item),
    model_name: item.model_name || "",
    api_key: "",
    extra_params: item.extra_params || "",
    timeout_seconds: item.timeout_seconds || 120,
    vector_dim: item.vector_dim || "",
    batch_size: item.batch_size || (modelType(item) === "embedding" ? 32 : ""),
    verify_ssl: Boolean(item.verify_ssl),
    ca_bundle: item.ca_bundle || "",
    max_retries: item.max_retries ?? 2,
    retry_backoff_seconds: item.retry_backoff_seconds ?? 0.5,
    trust_env: Boolean(item.trust_env),
    is_active: Boolean(item.is_active),
  });
  dialogVisible.value = true;
}

function closeDialog() {
  dialogVisible.value = false;
}

async function saveConfig() {
  if (!validateForm()) return;

  loading.save = true;
  try {
    const payload = buildPayload();
    if (editingId.value) {
      delete payload.model_type;
      await apiRequest(`/models/${editingId.value}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      setNotice("模型配置已更新。", "success");
    } else {
      await apiRequest("/models", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setNotice("模型配置已新增。", "success");
    }
    dialogVisible.value = false;
    await loadConfigs();
  } catch (error) {
    setNotice(`保存模型配置失败：${error.message}`, "error");
  } finally {
    loading.save = false;
  }
}

async function activateConfig(item) {
  if (!window.confirm(`确认启用模型配置「${item.name}」吗？`)) return;

  loading.action = true;
  try {
    const result = unwrapData(await apiRequest(`/models/${item.id}/activate`, { method: "POST" }));
    await loadConfigs();
    setNotice(result?.warning || "模型配置已启用。", result?.warning ? "info" : "success");
  } catch (error) {
    setNotice(`启用模型配置失败：${error.message}`, "error");
  } finally {
    loading.action = false;
  }
}

async function deleteConfig(item) {
  if (!window.confirm(`确认删除模型配置「${item.name}」吗？`)) return;

  loading.action = true;
  try {
    await apiRequest(`/models/${item.id}`, { method: "DELETE" });
    await loadConfigs();
    setNotice("模型配置已删除。", "success");
  } catch (error) {
    setNotice(`删除模型配置失败：${error.message}`, "error");
  } finally {
    loading.action = false;
  }
}

onMounted(async () => {
  await loadProviders();
  await loadConfigs();
});
</script>

<style scoped>
.model-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-width: 1280px;
  margin: 0 auto;
}

.panel {
  background: rgba(255, 255, 255, 0.64);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: var(--shadow-hairline);
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 22px;
}

.page-header h2 {
  margin: 0;
  font-size: 30px;
  line-height: 1.1;
  letter-spacing: 0;
}

.page-header p {
  margin: 8px 0 0;
  color: var(--text-muted);
  font-size: 14px;
}

.header-tools {
  display: flex;
  align-items: flex-end;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.filter-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 160px;
}

.filter-field span {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 650;
}

.filter-field select {
  min-height: 36px;
  padding: 0 10px;
}

.notice {
  padding: 12px 14px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 560;
}

.notice.success {
  background: var(--success-light);
  color: var(--success);
  border: 1px solid rgba(4, 120, 87, 0.18);
}

.notice.error {
  background: var(--error-light);
  color: var(--error);
  border: 1px solid rgba(180, 35, 24, 0.18);
}

.notice.info {
  background: var(--info-light);
  color: var(--info);
  border: 1px solid rgba(29, 78, 216, 0.18);
}

.summary-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
}

.summary-card {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 16px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.56);
}

.summary-card span,
.summary-card small {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 620;
}

.summary-card strong {
  color: var(--text-main);
  font-size: 18px;
  line-height: 1.25;
  overflow-wrap: anywhere;
}

.table-panel {
  overflow: hidden;
}

.table-wrap {
  overflow-x: auto;
}

.model-table {
  width: 100%;
  min-width: 1120px;
  border-collapse: collapse;
}

.model-table th,
.model-table td {
  padding: 13px 14px;
  border-bottom: 1px solid var(--line);
  text-align: left;
  vertical-align: top;
  font-size: 13px;
}

.model-table th {
  background: rgba(244, 244, 241, 0.66);
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 680;
}

.model-table tbody tr:hover td {
  background: rgba(17, 17, 17, 0.026);
}

.model-table tr.active td {
  background: rgba(236, 253, 243, 0.38);
}

.empty-cell {
  text-align: center;
  color: var(--text-muted);
  padding: 30px 0;
}

.mono {
  font-family: "Geist Mono", "SFMono-Regular", Consolas, monospace;
}

.break-cell {
  max-width: 260px;
  overflow-wrap: anywhere;
}

.name-cell {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.name-cell strong {
  color: var(--text-main);
  font-size: 14px;
}

.name-cell span,
.runtime-cell span {
  color: var(--text-muted);
  font-size: 12px;
}

.kind-chip,
.status-chip {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 8px;
  border: 1px solid var(--line);
  border-radius: 7px;
  background: var(--surface-2);
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 650;
  white-space: nowrap;
}

.status-chip.active {
  border-color: rgba(4, 120, 87, 0.18);
  background: var(--success-light);
  color: var(--success);
}

.runtime-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.btn-link {
  border: none;
  background: transparent;
  color: var(--text-main);
  font-size: 13px;
  font-weight: 640;
  padding: 0;
  cursor: pointer;
}

.btn-link:hover:not(:disabled) {
  color: #000000;
  text-decoration: underline;
}

.btn-link.danger {
  color: var(--error);
}

.btn-primary,
.btn-ghost {
  padding: 0 12px;
}

.dialog-mask {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(18, 18, 17, 0.28);
}

.model-dialog {
  width: min(760px, 100%);
  max-height: calc(100dvh - 40px);
  display: flex;
  flex-direction: column;
  border: 1px solid var(--line-strong);
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 24px 80px rgba(18, 18, 17, 0.18);
}

.dialog-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 16px;
  border-bottom: 1px solid var(--line);
}

.dialog-header h3 {
  margin: 0;
  color: var(--text-main);
  font-size: 20px;
  line-height: 1.25;
}

.dialog-header p {
  margin: 6px 0 0;
  color: var(--text-muted);
  font-size: 13px;
}

.btn-close {
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 24px;
  line-height: 1;
}

.dialog-body {
  overflow: auto;
  padding: 16px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.form-grid label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.form-grid .span-2 {
  grid-column: 1 / -1;
}

.form-grid span,
.check-label span {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 660;
}

.form-grid input,
.form-grid select,
.form-grid textarea {
  width: 100%;
  min-height: 38px;
  padding: 8px 10px;
}

.form-grid textarea {
  resize: vertical;
}

.switch-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  margin-top: 14px;
}

.check-label {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 28px;
}

.check-label input {
  width: 15px;
  height: 15px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}

@media (max-width: 860px) {
  .page-header {
    flex-direction: column;
  }

  .header-tools {
    justify-content: flex-start;
  }

  .summary-strip,
  .form-grid {
    grid-template-columns: 1fr;
  }

  .form-grid .span-2 {
    grid-column: auto;
  }
}
</style>

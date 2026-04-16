<template>
  <section class="knowledge-page">
    <header class="page-header panel">
      <div class="header-content">
        <h2>知识库文件管理</h2>
        <p>当前页面仅处理一个知识库，上传文件会固定归属到当前知识库 ID。</p>
      </div>
      <div class="quick-nav">
        <RouterLink to="/knowledge" class="quick-link">返回知识库列表</RouterLink>
        <RouterLink to="/qa" class="quick-link">知识问答</RouterLink>
      </div>
    </header>

    <div v-if="notice" class="notice" :class="noticeType">{{ notice }}</div>

    <section class="panel" v-if="loading.kb">
      <p class="loading-text">正在加载知识库信息...</p>
    </section>

    <section class="panel" v-else-if="!selectedKb">
      <h3>未找到知识库</h3>
      <p class="error-text">知识库 ID {{ selectedKbIdText }} 不存在或已删除，请返回列表重新选择。</p>
      <RouterLink to="/knowledge" class="btn-primary enter-link">返回知识库列表</RouterLink>
    </section>

    <template v-else>
      <section class="panel info-panel">
        <div class="list-tools">
          <span class="meta-tag">知识库 ID：{{ selectedKb.id }}</span>
          <span class="meta-tag">名称：{{ selectedKb.name }}</span>
          <span class="meta-tag">Collection：{{ selectedKb.collection_name }}</span>
          <span class="meta-tag">默认切片：{{ selectedKb.default_chunk_size }} / {{ selectedKb.default_chunk_overlap }}</span>
          <span class="meta-tag" v-if="selectedKb.is_default">默认知识库</span>
        </div>
      </section>

      <section class="panel form-panel">
        <h3>上传文件</h3>
        <div class="form-grid">
          <label>
            <span>统一切片大小（可选）</span>
            <input v-model.number="uploadForm.custom_chunk_size" type="number" min="100" max="8000" placeholder="留空使用知识库默认值" />
          </label>
          <label>
            <span>统一切片重叠（可选）</span>
            <input v-model.number="uploadForm.custom_chunk_overlap" type="number" min="0" max="2000" placeholder="留空使用知识库默认值" />
          </label>
          <label class="span-2 file-input-wrap">
            <span>上传文件</span>
            <input ref="fileInputRef" type="file" multiple @change="onSelectFiles" />
          </label>
        </div>

        <div class="selected-files" v-if="selectedFiles.length">
          <strong>已选择 {{ selectedFiles.length }} 个文件：</strong>
          <span>{{ selectedFiles.map((item) => item.name).join("，") }}</span>
        </div>

        <div class="actions-row">
          <button class="btn-primary" :disabled="loading.upload || selectedFiles.length === 0" @click="submitUpload">
            {{ loading.upload ? "上传中..." : "上传并异步处理" }}
          </button>
          <button class="btn-ghost" :disabled="loading.files" @click="loadFiles">刷新文件列表</button>
        </div>
      </section>

      <section class="panel list-panel">
        <div class="list-header">
          <h3>文件任务列表</h3>
          <div class="list-tools">
            <span class="meta-tag">当前：{{ selectedKb.name }}（ID: {{ selectedKb.id }}）</span>
            <span class="meta-tag" v-if="hasPendingFiles">检测到进行中任务，自动轮询中</span>
          </div>
        </div>

        <div class="table-wrap">
          <table class="file-table">
            <thead>
              <tr>
                <th>文件名</th>
                <th>大小</th>
                <th>状态</th>
                <th>分段数</th>
                <th>任务ID</th>
                <th>策略</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in filePage.items" :key="item.id">
                <td class="ellipsis" :title="item.file_name">{{ item.file_name }}</td>
                <td>{{ formatBytes(item.file_size) }}</td>
                <td>
                  <span class="status-badge" :class="statusClass(item.status)">{{ statusText(item.status) }}</span>
                  <div class="error-text" v-if="item.status === 3 && item.error_msg">{{ item.error_msg }}</div>
                </td>
                <td>{{ item.chunk_count }}</td>
                <td class="task-cell">
                  <span v-if="item.task_id" class="ellipsis" :title="item.task_id">{{ item.task_id }}</span>
                  <span v-else>-</span>
                </td>
                <td>
                  <div class="strategy-cell">
                    <input type="number" min="100" max="8000" v-model.number="strategyDraft[item.id].size" />
                    <input type="number" min="0" max="2000" v-model.number="strategyDraft[item.id].overlap" />
                  </div>
                </td>
                <td>
                  <div class="action-buttons">
                    <button class="btn-outline" :disabled="loading.action" @click="saveStrategyAndReprocess(item)">保存策略并重切分</button>
                    <button class="btn-ghost" :disabled="loading.action" @click="reprocess(item)">重处理</button>
                    <button class="btn-ghost" :disabled="loading.action" @click="previewChunks(item)">预览分段</button>
                    <button class="btn-danger" :disabled="loading.action" @click="removeFile(item)">删除</button>
                  </div>
                </td>
              </tr>
              <tr v-if="filePage.items.length === 0">
                <td colspan="7" class="empty-cell">当前知识库暂无文件</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="pager" v-if="filePage.total_pages > 1">
          <button class="btn-ghost" :disabled="filePage.page <= 1" @click="changePage(filePage.page - 1)">上一页</button>
          <span>第 {{ filePage.page }} / {{ filePage.total_pages }} 页</span>
          <button class="btn-ghost" :disabled="filePage.page >= filePage.total_pages" @click="changePage(filePage.page + 1)">下一页</button>
        </div>
      </section>

      <section class="panel" v-if="chunkPreview.visible">
        <div class="list-header">
          <h3>分段预览：{{ chunkPreview.file_name }}</h3>
          <button class="btn-ghost" @click="chunkPreview.visible = false">收起</button>
        </div>

        <div class="chunk-list">
          <article v-for="chunk in chunkPreview.items" :key="chunk.id" class="chunk-item">
            <header>Chunk #{{ chunk.chunk_index }} · {{ chunk.char_count }} 字</header>
            <pre>{{ chunk.content }}</pre>
          </article>
        </div>

        <div class="pager" v-if="chunkPreview.total_pages > 1">
          <button class="btn-ghost" :disabled="chunkPreview.page <= 1" @click="changeChunkPage(chunkPreview.page - 1)">上一页</button>
          <span>第 {{ chunkPreview.page }} / {{ chunkPreview.total_pages }} 页</span>
          <button class="btn-ghost" :disabled="chunkPreview.page >= chunkPreview.total_pages" @click="changeChunkPage(chunkPreview.page + 1)">下一页</button>
        </div>
      </section>
    </template>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { apiRequest } from "../api/client";

const route = useRoute();

const loading = reactive({ kb: false, upload: false, files: false, action: false, chunks: false });
const notice = ref("");
const noticeType = ref("info");

const selectedKb = ref(null);
const selectedKbIdText = computed(() => route.params.kbId || "-");

const uploadForm = reactive({
  custom_chunk_size: null,
  custom_chunk_overlap: null,
});
const fileInputRef = ref(null);
const selectedFiles = ref([]);

const filePage = reactive({
  items: [],
  total: 0,
  page: 1,
  page_size: 10,
  total_pages: 0,
});

const strategyDraft = reactive({});

const chunkPreview = reactive({
  visible: false,
  fileId: null,
  file_name: "",
  items: [],
  total: 0,
  page: 1,
  page_size: 10,
  total_pages: 0,
});

let pollTimer = null;

const hasPendingFiles = computed(() =>
  filePage.items.some((item) => Number(item.status) === 0 || Number(item.status) === 1)
);

function setNotice(message, type = "info") {
  notice.value = message;
  noticeType.value = type;
}

function resetFilePage() {
  filePage.items = [];
  filePage.total = 0;
  filePage.total_pages = 0;
  filePage.page = 1;
}

function ensureStrategyDraft(items) {
  for (const item of items) {
    const defaultSize = item.custom_chunk_size || selectedKb.value?.default_chunk_size || 800;
    const defaultOverlap = item.custom_chunk_overlap || selectedKb.value?.default_chunk_overlap || 120;
    strategyDraft[item.id] = {
      size: Number(defaultSize),
      overlap: Number(defaultOverlap),
    };
  }
}

function clearFileInput() {
  selectedFiles.value = [];
  if (fileInputRef.value) {
    fileInputRef.value.value = "";
  }
}

async function loadKnowledgeBase() {
  loading.kb = true;
  try {
    const kbId = Number(route.params.kbId);
    if (!Number.isInteger(kbId) || kbId <= 0) {
      selectedKb.value = null;
      setNotice("知识库 ID 无效", "error");
      resetFilePage();
      stopPolling();
      return false;
    }

    const data = await apiRequest("/text2sql/kb");
    const kbList = Array.isArray(data) ? data : [];
    const found = kbList.find((item) => Number(item.id) === kbId) || null;
    selectedKb.value = found;

    if (!found) {
      setNotice(`未找到 ID 为 ${kbId} 的知识库`, "error");
      resetFilePage();
      stopPolling();
      return false;
    }
    return true;
  } catch (error) {
    selectedKb.value = null;
    setNotice(`加载知识库失败：${error.message}`, "error");
    resetFilePage();
    stopPolling();
    return false;
  } finally {
    loading.kb = false;
  }
}

async function loadFiles() {
  if (!selectedKb.value?.id) return;

  loading.files = true;
  try {
    const data = await apiRequest(
      `/text2sql/file/kb/${selectedKb.value.id}?page=${filePage.page}&page_size=${filePage.page_size}`
    );
    filePage.items = Array.isArray(data.items) ? data.items : [];
    filePage.total = Number(data.total || 0);
    filePage.total_pages = Number(data.total_pages || 0);
    ensureStrategyDraft(filePage.items);
  } catch (error) {
    setNotice(`加载文件列表失败：${error.message}`, "error");
  } finally {
    loading.files = false;
  }
}

function onSelectFiles(event) {
  const files = Array.from(event?.target?.files || []);
  selectedFiles.value = files;
}

async function submitUpload() {
  if (!selectedKb.value?.id) {
    setNotice("当前知识库无效，请返回列表重新进入", "error");
    return;
  }
  if (!selectedFiles.value.length) {
    setNotice("请先选择上传文件", "error");
    return;
  }

  const size = uploadForm.custom_chunk_size;
  const overlap = uploadForm.custom_chunk_overlap;
  if (size != null && overlap != null && Number(overlap) >= Number(size)) {
    setNotice("统一切片重叠必须小于切片大小", "error");
    return;
  }

  const formData = new FormData();
  formData.append("kb_id", String(selectedKb.value.id));
  if (size != null && String(size).trim() !== "") {
    formData.append("custom_chunk_size", String(Number(size)));
  }
  if (overlap != null && String(overlap).trim() !== "") {
    formData.append("custom_chunk_overlap", String(Number(overlap)));
  }
  for (const file of selectedFiles.value) {
    formData.append("files", file);
  }

  loading.upload = true;
  try {
    const result = await apiRequest("/text2sql/file/upload", {
      method: "POST",
      body: formData,
    });

    const successCount = result.filter((item) => item.status === "success").length;
    const failedCount = result.filter((item) => item.status === "failed").length;
    const skippedCount = result.filter((item) => item.status === "skipped").length;
    setNotice(
      `上传完成：成功 ${successCount}，失败 ${failedCount}，跳过 ${skippedCount}`,
      failedCount > 0 ? "error" : "success"
    );

    clearFileInput();
    await loadFiles();
  } catch (error) {
    setNotice(`上传失败：${error.message}`, "error");
  } finally {
    loading.upload = false;
  }
}

async function changePage(page) {
  filePage.page = Math.max(1, Number(page || 1));
  await loadFiles();
}

async function removeFile(item) {
  const confirmed = window.confirm(`确认删除文件 ${item.file_name} 吗？该操作会同步删除向量数据。`);
  if (!confirmed) return;

  loading.action = true;
  try {
    await apiRequest(`/text2sql/file/${item.id}`, { method: "DELETE" });
    setNotice("文件已删除", "success");
    await loadFiles();
  } catch (error) {
    setNotice(`删除失败：${error.message}`, "error");
  } finally {
    loading.action = false;
  }
}

async function reprocess(item) {
  loading.action = true;
  try {
    await apiRequest(`/text2sql/file/${item.id}/reprocess`, { method: "POST" });
    setNotice("已提交重处理任务", "success");
    await loadFiles();
  } catch (error) {
    setNotice(`重处理失败：${error.message}`, "error");
  } finally {
    loading.action = false;
  }
}

async function saveStrategyAndReprocess(item) {
  const draft = strategyDraft[item.id];
  if (!draft) return;

  if (Number(draft.overlap) >= Number(draft.size)) {
    setNotice("切片重叠必须小于切片大小", "error");
    return;
  }

  loading.action = true;
  try {
    await apiRequest(`/text2sql/file/${item.id}/strategy`, {
      method: "PUT",
      body: JSON.stringify({
        custom_chunk_size: Number(draft.size),
        custom_chunk_overlap: Number(draft.overlap),
      }),
    });
    setNotice("策略已保存并提交重切分任务", "success");
    await loadFiles();
  } catch (error) {
    setNotice(`保存策略失败：${error.message}`, "error");
  } finally {
    loading.action = false;
  }
}

async function previewChunks(item) {
  chunkPreview.visible = true;
  chunkPreview.fileId = item.id;
  chunkPreview.file_name = item.file_name;
  chunkPreview.page = 1;
  await loadChunkPage();
}

async function loadChunkPage() {
  if (!chunkPreview.fileId) return;

  loading.chunks = true;
  try {
    const data = await apiRequest(
      `/text2sql/file/${chunkPreview.fileId}/chunks?page=${chunkPreview.page}&page_size=${chunkPreview.page_size}`
    );
    chunkPreview.items = Array.isArray(data.items) ? data.items : [];
    chunkPreview.total = Number(data.total || 0);
    chunkPreview.total_pages = Number(data.total_pages || 0);
  } catch (error) {
    setNotice(`加载分段失败：${error.message}`, "error");
  } finally {
    loading.chunks = false;
  }
}

async function changeChunkPage(page) {
  chunkPreview.page = Math.max(1, Number(page || 1));
  await loadChunkPage();
}

function formatBytes(size) {
  const value = Number(size || 0);
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 * 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  return `${(value / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function statusText(status) {
  const num = Number(status);
  if (num === 0) return "待处理";
  if (num === 1) return "处理中";
  if (num === 2) return "已完成";
  if (num === 3) return "失败";
  return "未知";
}

function statusClass(status) {
  const num = Number(status);
  if (num === 0) return "pending";
  if (num === 1) return "running";
  if (num === 2) return "success";
  if (num === 3) return "failed";
  return "unknown";
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function startPolling() {
  stopPolling();
  pollTimer = setInterval(() => {
    if (selectedKb.value?.id) {
      loadFiles();
    }
  }, 5000);
}

async function initPage() {
  clearFileInput();
  chunkPreview.visible = false;
  const loaded = await loadKnowledgeBase();
  if (!loaded) return;
  await loadFiles();
}

watch(hasPendingFiles, (value) => {
  if (value) {
    startPolling();
  } else {
    stopPolling();
  }
});

watch(
  () => route.params.kbId,
  async () => {
    filePage.page = 1;
    await initPage();
  }
);

onMounted(async () => {
  await initPage();
});

onBeforeUnmount(() => {
  stopPolling();
});
</script>

<style scoped>
.knowledge-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.panel {
  background: var(--bg-panel);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.8);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 16px;
}

h2 {
  margin: 0 0 8px;
  font-size: 22px;
  font-weight: 700;
}

h3 {
  margin: 0 0 16px;
  font-size: 18px;
}

.header-content p {
  margin: 0;
  color: var(--text-muted);
}

.quick-nav {
  display: flex;
  gap: 8px;
}

.quick-link {
  text-decoration: none;
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--accent);
  background: var(--accent-light);
}

.quick-link:hover {
  background: var(--accent);
  color: #fff;
}

.loading-text {
  margin: 0;
  color: var(--text-muted);
}

.info-panel {
  padding-bottom: 14px;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
}

label span {
  color: var(--text-muted);
}

input,
textarea {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 10px 12px;
  background: #fff;
}

input:focus,
textarea:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-light);
  outline: none;
}

.span-2 {
  grid-column: span 2;
}

.file-input-wrap input {
  padding: 8px;
}

.selected-files {
  margin-top: 12px;
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.6;
}

.actions-row {
  margin-top: 16px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

button {
  border: none;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--accent);
  color: #fff;
}

.btn-primary:hover:not(:disabled) {
  background: var(--accent-hover);
}

.enter-link {
  display: inline-flex;
  align-items: center;
  text-decoration: none;
}

.btn-outline {
  border: 1px solid var(--accent);
  background: transparent;
  color: var(--accent);
}

.btn-outline:hover:not(:disabled) {
  background: var(--accent-light);
}

.btn-ghost {
  border: 1px solid var(--line);
  background: transparent;
  color: var(--text-main);
}

.btn-ghost:hover:not(:disabled) {
  background: #f1f5f9;
}

.btn-danger {
  background: #fee2e2;
  color: #991b1b;
}

.btn-danger:hover:not(:disabled) {
  background: #ef4444;
  color: #fff;
}

.notice {
  padding: 12px 16px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
}

.notice.success {
  background: #d1fae5;
  color: #065f46;
  border: 1px solid #34d399;
}

.notice.error {
  background: #fee2e2;
  color: #991b1b;
  border: 1px solid #f87171;
}

.notice.info {
  background: #eff6ff;
  color: #1d4ed8;
  border: 1px solid #93c5fd;
}

.list-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.list-tools {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.meta-tag {
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 999px;
  background: #f1f5f9;
  color: var(--text-muted);
}

.table-wrap {
  overflow-x: auto;
}

.file-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 1100px;
}

.file-table th,
.file-table td {
  border-bottom: 1px solid #e2e8f0;
  padding: 10px 12px;
  text-align: left;
  vertical-align: top;
  font-size: 13px;
}

.file-table th {
  background: #f8fafc;
  color: var(--text-muted);
}

.status-badge {
  display: inline-block;
  font-size: 12px;
  padding: 3px 8px;
  border-radius: 999px;
}

.status-badge.pending {
  background: #fef3c7;
  color: #92400e;
}

.status-badge.running {
  background: #dbeafe;
  color: #1d4ed8;
}

.status-badge.success {
  background: #d1fae5;
  color: #065f46;
}

.status-badge.failed {
  background: #fee2e2;
  color: #991b1b;
}

.error-text {
  margin-top: 6px;
  color: #b91c1c;
  max-width: 280px;
  white-space: pre-wrap;
  word-break: break-word;
}

.task-cell {
  max-width: 200px;
}

.ellipsis {
  display: inline-block;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.strategy-cell {
  display: flex;
  gap: 8px;
}

.strategy-cell input {
  width: 90px;
}

.action-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.empty-cell {
  text-align: center;
  color: var(--text-muted);
  padding: 30px 0;
}

.pager {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
}

.chunk-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chunk-item {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 12px;
  background: #fff;
}

.chunk-item header {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.chunk-item pre {
  margin: 0;
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.6;
}

@media (max-width: 720px) {
  .form-grid {
    grid-template-columns: 1fr;
  }

  .span-2 {
    grid-column: span 1;
  }
}
</style>

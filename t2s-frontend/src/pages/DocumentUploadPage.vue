<template>
  <section class="document-upload-page">
    <header class="page-header panel">
      <div class="header-content">
        <h2>普通文档处理与上传</h2>
        <p>解析docx等无结构文档，上传后通过普通 RAG 链路完成切片、向量化与检索准备。</p>
      </div>
      <span class="pipeline-badge">普通 RAG</span>
    </header>

    <div v-if="notice" class="notice" :class="noticeType" role="status">{{ notice }}</div>

    <section class="panel form-panel">
      <div class="section-heading">
        <div>
          <h3>上传普通文档</h3>
          <p>仅显示用途为“文档问答”的知识库，避免文件进入高基表语义树链路。</p>
        </div>
        <button class="btn-ghost" :disabled="loading.kbs || loading.files" @click="reloadAll">刷新</button>
      </div>

      <div v-if="loading.kbs" class="loading-state">正在加载文档问答知识库...</div>

      <div v-else-if="documentKbs.length === 0" class="empty-state">
        <strong>暂无文档问答知识库</strong>
        <p>请先创建用途为“文档问答”的知识库，再上传普通文档。</p>
        <RouterLink class="btn-outline manage-link" to="/admin/model-config/knowledge">前往知识库管理</RouterLink>
      </div>

      <template v-else>
        <div class="form-grid">
          <label class="span-2">
            <span>文档问答知识库</span>
            <select v-model="selectedKbId">
              <option v-for="kb in documentKbs" :key="kb.id" :value="String(kb.id)">
                #{{ kb.id }} {{ kb.name }}
              </option>
            </select>
          </label>
          <label>
            <span>统一切片大小（可选）</span>
            <input
              v-model.number="uploadForm.custom_chunk_size"
              type="number"
              min="100"
              max="8000"
              placeholder="留空使用知识库默认值"
            />
          </label>
          <label>
            <span>统一切片重叠（可选）</span>
            <input
              v-model.number="uploadForm.custom_chunk_overlap"
              type="number"
              min="0"
              max="2000"
              placeholder="留空使用知识库默认值"
            />
          </label>
          <label class="span-2 file-input-wrap">
            <span>DOCX / PDF / 文本类文件</span>
            <input
              ref="fileInputRef"
              type="file"
              multiple
              accept=".docx,.pdf,.pptx,.html,.htm,.rtf,.txt,.md,.markdown,.csv,.json,.yaml,.yml,.sql,.log"
              @change="onSelectFiles"
            />
          </label>
        </div>

        <div v-if="selectedFiles.length" class="selected-files">
          <strong>已选择 {{ selectedFiles.length }} 个文件</strong>
          <span>{{ selectedFiles.map((item) => item.name).join("，") }}</span>
        </div>

        <div class="actions-row">
          <button
            class="btn-primary"
            :disabled="loading.upload || !selectedKbId || selectedFiles.length === 0"
            @click="submitUpload"
          >
            {{ loading.upload ? "上传中..." : "上传并进入 RAG 处理" }}
          </button>
          <span v-if="selectedKb" class="kb-summary">
            默认切片：{{ selectedKb.default_chunk_size }} / {{ selectedKb.default_chunk_overlap }}
          </span>
        </div>
      </template>
    </section>

    <section v-if="selectedKb" class="panel list-panel">
      <div class="section-heading">
        <div>
          <h3>文档处理任务</h3>
          <p>{{ selectedKb.name }}（知识库 ID：{{ selectedKb.id }}）</p>
        </div>
        <span v-if="hasPendingFiles" class="polling-badge">处理中，自动刷新</span>
      </div>

      <div v-if="loading.files && filePage.items.length === 0" class="loading-state">正在加载文件任务...</div>
      <div v-else class="table-wrap">
        <table class="file-table">
          <thead>
            <tr>
              <th>文件名</th>
              <th>大小</th>
              <th>状态</th>
              <th>分段数</th>
              <th>任务 ID</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in filePage.items" :key="item.id">
              <td class="file-name" :title="item.file_name">{{ item.file_name }}</td>
              <td>{{ formatBytes(item.file_size) }}</td>
              <td>
                <span class="status-badge" :class="statusClass(item.status)">{{ statusText(item.status) }}</span>
                <div v-if="Number(item.status) === 3 && item.error_msg" class="error-text">{{ item.error_msg }}</div>
              </td>
              <td>{{ item.chunk_count }}</td>
              <td class="task-id" :title="item.task_id || ''">{{ item.task_id || "-" }}</td>
              <td>
                <div class="action-buttons">
                  <button class="btn-outline" :disabled="loading.action" @click="previewChunks(item)">预览分段</button>
                  <button class="btn-ghost" :disabled="loading.action" @click="reprocess(item)">重处理</button>
                  <button class="btn-danger" :disabled="loading.action" @click="removeFile(item)">删除</button>
                </div>
              </td>
            </tr>
            <tr v-if="filePage.items.length === 0">
              <td colspan="6" class="empty-cell">当前知识库暂无普通文档</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="filePage.total_pages > 1" class="pager">
        <button class="btn-ghost" :disabled="filePage.page <= 1" @click="changePage(filePage.page - 1)">上一页</button>
        <span>第 {{ filePage.page }} / {{ filePage.total_pages }} 页</span>
        <button class="btn-ghost" :disabled="filePage.page >= filePage.total_pages" @click="changePage(filePage.page + 1)">下一页</button>
      </div>
    </section>

    <section v-if="chunkPreview.visible" class="panel chunk-panel">
      <div class="section-heading">
        <div>
          <h3>分段预览</h3>
          <p>{{ chunkPreview.file_name }}</p>
        </div>
        <button class="btn-ghost" @click="chunkPreview.visible = false">收起</button>
      </div>

      <div v-if="loading.chunks" class="loading-state">正在加载分段...</div>
      <div v-else class="chunk-list">
        <article v-for="chunk in chunkPreview.items" :key="chunk.id" class="chunk-item">
          <header>Chunk #{{ chunk.chunk_index }} · {{ chunk.char_count }} 字</header>
          <pre>{{ chunk.content }}</pre>
        </article>
        <div v-if="chunkPreview.items.length === 0" class="empty-state compact">该文件尚未生成分段。</div>
      </div>

      <div v-if="chunkPreview.total_pages > 1" class="pager">
        <button class="btn-ghost" :disabled="chunkPreview.page <= 1" @click="changeChunkPage(chunkPreview.page - 1)">上一页</button>
        <span>第 {{ chunkPreview.page }} / {{ chunkPreview.total_pages }} 页</span>
        <button class="btn-ghost" :disabled="chunkPreview.page >= chunkPreview.total_pages" @click="changeChunkPage(chunkPreview.page + 1)">下一页</button>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { RouterLink } from "vue-router";

import { apiRequest } from "../api/client";

const loading = reactive({ kbs: false, upload: false, files: false, action: false, chunks: false });
const notice = ref("");
const noticeType = ref("info");
const documentKbs = ref([]);
const selectedKbId = ref("");
const selectedFiles = ref([]);
const fileInputRef = ref(null);

const uploadForm = reactive({
  custom_chunk_size: null,
  custom_chunk_overlap: null,
});

const filePage = reactive({
  items: [],
  total: 0,
  page: 1,
  page_size: 10,
  total_pages: 0,
});

const chunkPreview = reactive({
  visible: false,
  file_id: null,
  file_name: "",
  items: [],
  page: 1,
  page_size: 10,
  total_pages: 0,
});

const selectedKb = computed(() => (
  documentKbs.value.find((item) => String(item.id) === selectedKbId.value) || null
));
const hasPendingFiles = computed(() => (
  filePage.items.some((item) => [0, 1].includes(Number(item.status)))
));

let pollTimer = null;
let pollInFlight = false;
let isUnmounted = false;

function setNotice(message, type = "info") {
  notice.value = message;
  noticeType.value = type;
}

function resetFilePage() {
  filePage.items = [];
  filePage.total = 0;
  filePage.page = 1;
  filePage.total_pages = 0;
}

async function loadKnowledgeBases() {
  loading.kbs = true;
  try {
    const data = await apiRequest("/text2sql/kb");
    documentKbs.value = (Array.isArray(data) ? data : []).filter((item) => item.usage === "document_qa");
    if (!documentKbs.value.some((item) => String(item.id) === selectedKbId.value)) {
      selectedKbId.value = documentKbs.value[0] ? String(documentKbs.value[0].id) : "";
    }
  } catch (error) {
    documentKbs.value = [];
    selectedKbId.value = "";
    setNotice(`加载知识库失败：${error.message}`, "error");
  } finally {
    loading.kbs = false;
  }
}

async function loadFiles({ preserveOnError = false } = {}) {
  if (!selectedKbId.value) {
    resetFilePage();
    return;
  }

  loading.files = true;
  try {
    const data = await apiRequest(
      `/text2sql/file/kb/${selectedKbId.value}?page=${filePage.page}&page_size=${filePage.page_size}`
    );
    filePage.items = Array.isArray(data.items) ? data.items : [];
    filePage.total = Number(data.total || 0);
    filePage.total_pages = Number(data.total_pages || 0);
  } catch (error) {
    if (!preserveOnError) resetFilePage();
    setNotice(`加载文件任务失败：${error.message}`, "error");
  } finally {
    loading.files = false;
  }
}

async function reloadAll() {
  await loadKnowledgeBases();
  await loadFiles();
}

function onSelectFiles(event) {
  selectedFiles.value = Array.from(event?.target?.files || []);
}

function clearFileInput() {
  selectedFiles.value = [];
  if (fileInputRef.value) fileInputRef.value.value = "";
}

async function submitUpload() {
  if (!selectedKbId.value) {
    setNotice("请选择文档问答知识库", "error");
    return;
  }
  if (selectedFiles.value.length === 0) {
    setNotice("请先选择普通文档", "error");
    return;
  }

  const size = uploadForm.custom_chunk_size;
  const overlap = uploadForm.custom_chunk_overlap;
  if (size != null && overlap != null && Number(overlap) >= Number(size)) {
    setNotice("统一切片重叠必须小于切片大小", "error");
    return;
  }

  const formData = new FormData();
  formData.append("kb_id", selectedKbId.value);
  if (size != null && String(size).trim() !== "") formData.append("custom_chunk_size", String(Number(size)));
  if (overlap != null && String(overlap).trim() !== "") formData.append("custom_chunk_overlap", String(Number(overlap)));
  for (const file of selectedFiles.value) formData.append("files", file);

  loading.upload = true;
  try {
    const data = await apiRequest("/text2sql/file/upload", { method: "POST", body: formData });
    const results = Array.isArray(data) ? data : [];
    const successCount = results.filter((item) => item.status === "success").length;
    const failedCount = results.filter((item) => item.status === "failed").length;
    const skippedCount = results.filter((item) => item.status === "skipped").length;
    setNotice(
      `上传完成：成功 ${successCount}，失败 ${failedCount}，跳过 ${skippedCount}`,
      failedCount > 0 ? "error" : "success"
    );
    clearFileInput();
    filePage.page = 1;
    await loadFiles();
  } catch (error) {
    setNotice(`上传失败：${error.message}`, "error");
  } finally {
    loading.upload = false;
  }
}

async function reprocess(item) {
  loading.action = true;
  try {
    await apiRequest(`/text2sql/file/${item.id}/reprocess`, { method: "POST" });
    setNotice("已提交普通 RAG 重处理任务", "success");
    await loadFiles();
  } catch (error) {
    setNotice(`重处理失败：${error.message}`, "error");
  } finally {
    loading.action = false;
  }
}

async function removeFile(item) {
  if (!window.confirm(`确认删除文件 ${item.file_name} 吗？该操作会同步删除向量数据。`)) return;

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

async function loadChunkPage() {
  if (!chunkPreview.file_id) return;
  loading.chunks = true;
  try {
    const data = await apiRequest(
      `/text2sql/file/${chunkPreview.file_id}/chunks?page=${chunkPreview.page}&page_size=${chunkPreview.page_size}`
    );
    chunkPreview.items = Array.isArray(data.items) ? data.items : [];
    chunkPreview.total_pages = Number(data.total_pages || 0);
  } catch (error) {
    setNotice(`加载分段失败：${error.message}`, "error");
  } finally {
    loading.chunks = false;
  }
}

async function previewChunks(item) {
  chunkPreview.visible = true;
  chunkPreview.file_id = item.id;
  chunkPreview.file_name = item.file_name;
  chunkPreview.page = 1;
  chunkPreview.items = [];
  await loadChunkPage();
}

async function changePage(page) {
  filePage.page = Math.max(1, Number(page || 1));
  await loadFiles();
}

async function changeChunkPage(page) {
  chunkPreview.page = Math.max(1, Number(page || 1));
  await loadChunkPage();
}

function formatBytes(size) {
  const value = Number(size || 0);
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function statusText(status) {
  const value = Number(status);
  if (value === 0) return "待处理";
  if (value === 1) return "处理中";
  if (value === 2) return "已完成";
  if (value === 3) return "失败";
  return "未知";
}

function statusClass(status) {
  const value = Number(status);
  if (value === 0) return "pending";
  if (value === 1) return "running";
  if (value === 2) return "success";
  if (value === 3) return "failed";
  return "unknown";
}

function stopPolling() {
  if (!pollTimer) return;
  clearTimeout(pollTimer);
  pollTimer = null;
}

async function pollPendingFiles() {
  pollTimer = null;
  if (!selectedKbId.value || pollInFlight) return;

  pollInFlight = true;
  try {
    await loadFiles({ preserveOnError: true });
  } finally {
    pollInFlight = false;
    if (!isUnmounted && hasPendingFiles.value) startPolling();
  }
}

function startPolling(delay = 2500) {
  if (isUnmounted || pollTimer || pollInFlight || !selectedKbId.value || !hasPendingFiles.value) return;
  pollTimer = setTimeout(() => void pollPendingFiles(), delay);
}

watch(selectedKbId, async () => {
  stopPolling();
  filePage.page = 1;
  chunkPreview.visible = false;
  await loadFiles();
  if (hasPendingFiles.value) startPolling(0);
});

watch(hasPendingFiles, (value) => {
  if (value) startPolling(0);
  else stopPolling();
}, { immediate: true });

onMounted(reloadAll);
onBeforeUnmount(() => {
  isUnmounted = true;
  stopPolling();
});
</script>

<style scoped>
.document-upload-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.panel {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--bg-panel);
  box-shadow: var(--shadow-hairline);
  backdrop-filter: blur(16px);
}

.page-header,
.section-heading,
.actions-row,
.pager,
.action-buttons {
  display: flex;
  align-items: center;
}

.page-header {
  justify-content: space-between;
  gap: 24px;
  padding: 24px;
}

.page-header h2,
.section-heading h3 {
  margin: 0;
  color: var(--text-main);
}

.page-header h2 {
  font-size: clamp(22px, 2vw, 30px);
}

.page-header p,
.section-heading p,
.empty-state p {
  margin: 7px 0 0;
  color: var(--text-muted);
  line-height: 1.6;
}

.pipeline-badge,
.polling-badge,
.status-badge {
  display: inline-flex;
  align-items: center;
  width: max-content;
  border-radius: 7px;
  font-weight: 680;
  white-space: nowrap;
}

.pipeline-badge {
  padding: 8px 11px;
  border: 1px solid rgba(var(--accent-rgb), 0.18);
  background: var(--accent-light);
  color: var(--accent);
  font-size: 13px;
}

.form-panel,
.list-panel,
.chunk-panel {
  padding: 22px;
}

.section-heading {
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.section-heading h3 {
  font-size: 18px;
}

.section-heading p {
  font-size: 13px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.form-grid label {
  display: flex;
  flex-direction: column;
  gap: 7px;
  color: var(--text-main);
  font-size: 13px;
  font-weight: 650;
}

.form-grid input,
.form-grid select {
  width: 100%;
  min-height: 42px;
  padding: 9px 11px;
}

.span-2 {
  grid-column: 1 / -1;
}

.selected-files,
.kb-summary {
  color: var(--text-muted);
  font-size: 13px;
}

.selected-files {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-top: 14px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 7px;
  background: var(--bg-subtle);
}

.selected-files span {
  overflow-wrap: anywhere;
}

.actions-row {
  gap: 14px;
  margin-top: 16px;
}

.actions-row button,
.manage-link,
.action-buttons button,
.pager button,
.section-heading > button {
  padding: 8px 12px;
}

.manage-link {
  display: inline-flex;
  align-items: center;
  margin-top: 14px;
  text-decoration: none;
}

.notice,
.loading-state,
.empty-state {
  padding: 14px 16px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
}

.notice.info,
.loading-state {
  border-color: rgba(29, 78, 216, 0.18);
  background: var(--info-light);
  color: var(--info);
}

.notice.success {
  border-color: rgba(4, 120, 87, 0.18);
  background: var(--success-light);
  color: var(--success);
}

.notice.error {
  border-color: rgba(180, 35, 24, 0.18);
  background: var(--error-light);
  color: var(--error);
}

.empty-state {
  color: var(--text-main);
  background: var(--bg-subtle);
}

.empty-state.compact {
  color: var(--text-muted);
}

.table-wrap {
  overflow-x: auto;
}

.file-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 900px;
}

.file-table th,
.file-table td {
  padding: 12px 10px;
  border-bottom: 1px solid var(--line);
  text-align: left;
  vertical-align: top;
  font-size: 13px;
}

.file-table th {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 720;
}

.file-name,
.task-id {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-id {
  max-width: 150px;
  color: var(--text-muted);
  font-family: "Geist Mono", Consolas, monospace;
}

.status-badge,
.polling-badge {
  padding: 5px 8px;
  font-size: 12px;
}

.status-badge.pending,
.polling-badge {
  background: #fff7e6;
  color: var(--warn);
}

.status-badge.running {
  background: var(--info-light);
  color: var(--info);
}

.status-badge.success {
  background: var(--success-light);
  color: var(--success);
}

.status-badge.failed {
  background: var(--error-light);
  color: var(--error);
}

.status-badge.unknown {
  background: var(--bg-subtle);
  color: var(--text-muted);
}

.error-text {
  max-width: 280px;
  margin-top: 6px;
  color: var(--error);
  font-size: 12px;
  line-height: 1.45;
}

.action-buttons {
  flex-wrap: wrap;
  gap: 7px;
}

.action-buttons button {
  min-height: 32px;
  white-space: nowrap;
}

.empty-cell {
  padding: 26px !important;
  color: var(--text-muted);
  text-align: center !important;
}

.pager {
  justify-content: flex-end;
  gap: 12px;
  margin-top: 16px;
  color: var(--text-muted);
  font-size: 13px;
}

.chunk-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chunk-item {
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--bg-card);
}

.chunk-item header {
  padding: 9px 12px;
  border-bottom: 1px solid var(--line);
  color: var(--text-muted);
  background: var(--bg-subtle);
  font-size: 12px;
  font-weight: 680;
}

.chunk-item pre {
  margin: 0;
  padding: 14px;
  overflow-x: auto;
  color: var(--text-main);
  font: inherit;
  line-height: 1.65;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

@media (max-width: 720px) {
  .page-header,
  .section-heading,
  .actions-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .span-2 {
    grid-column: auto;
  }

  .form-panel,
  .list-panel,
  .chunk-panel,
  .page-header {
    padding: 18px;
  }
}
</style>

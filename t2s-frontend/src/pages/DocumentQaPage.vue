<template>
  <section class="document-qa-page">
    <header class="page-header panel">
      <div class="header-content">
        <h2>{{ pageTitle }}</h2>
        <p>{{ pageDescription }}</p>
      </div>
    </header>

    <div v-if="notice" class="notice" :class="noticeType">{{ notice }}</div>

    <section class="grid-top single-panel-grid">
      <article v-if="isUploadView" class="panel form-panel">
        <h3>上传表格语义树</h3>
        <div class="form-grid">
          <label>
            <span>表格语义树知识库</span>
            <select v-model="uploadForm.kb_id">
              <option value="" disabled>请选择表格语义树知识库</option>
              <option v-for="kb in tableKbs" :key="kb.id" :value="String(kb.id)">
                #{{ kb.id }} {{ kb.name }}
              </option>
            </select>
          </label>
          <label>
            <span>工作表名称（可选）</span>
            <input v-model.trim="uploadForm.sheet_name" placeholder="留空则解析第一个工作表" />
          </label>
          <label class="span-2 file-input-wrap">
            <span>Excel / CSV 文件</span>
            <input ref="fileInputRef" type="file" accept=".xlsx,.xlsm,.xls,.csv" @change="onSelectFile" />
          </label>
        </div>
        <div v-if="selectedFile" class="selected-file">已选择：{{ selectedFile.name }}</div>
        <div class="actions-row">
          <button class="btn-primary" :disabled="loading.upload || !selectedFile || !uploadForm.kb_id" @click="uploadTable">
            {{ loading.upload ? "提交中..." : "上传并解析" }}
          </button>
          <button class="btn-ghost" :disabled="loading.kbs || loading.tables" @click="reloadAll">刷新</button>
        </div>
      </article>

      <article v-if="isDebugView" class="panel debug-panel">
        <h3>问答调试</h3>
        <div class="form-grid single">
          <div class="debug-route-grid" role="group" aria-label="选择调试链路">
            <button
              type="button"
              class="debug-route-option"
              :class="{ active: debugForm.qa_type === 'table' }"
              :aria-pressed="debugForm.qa_type === 'table'"
              @click="selectDebugRoute('table')"
            >
              <strong>仅语义树问答</strong>
              <span>检索全部表格语义树知识库，返回语义树问答结果和路径依据。</span>
              <code>POST /document-qa/table/answer</code>
            </button>
            <button
              type="button"
              class="debug-route-option"
              :class="{ active: debugForm.qa_type === 'combined' }"
              :aria-pressed="debugForm.qa_type === 'combined'"
              @click="selectDebugRoute('combined')"
            >
              <strong>完整文档问答链路</strong>
              <span>普通文档问答与语义树问答分别执行，再生成最终裁决答案。</span>
              <code>POST /document-qa/query</code>
            </button>
          </div>
          <label>
            <span>问题</span>
            <textarea v-model.trim="debugForm.question" rows="4" placeholder="输入需要验证的问题" />
          </label>
        </div>
        <div class="actions-row">
          <button class="btn-primary" :disabled="loading.debug" @click="askDebug">
            {{ loading.debug ? "问答中..." : debugForm.qa_type === "table" ? "执行语义树问答" : "执行完整链路" }}
          </button>
        </div>
        <div v-if="debugResult" class="debug-result">
          <h4>{{ debugForm.qa_type === "table" ? "语义树回答" : "最终裁决答案" }}</h4>
          <pre>{{ debugResult.answer }}</pre>
          <details v-if="debugResult.evidences?.length" open>
            <summary>引用依据（{{ debugResult.evidences.length }} 条）</summary>
            <article v-for="item in debugResult.evidences" :key="item.chunk_id || item.text" class="evidence-item">
              <div class="meta-line">KB #{{ item.kb_id }} · 文件 #{{ item.file_id || "-" }} · {{ formatScore(item.score) }}</div>
              <pre>{{ item.text }}</pre>
            </article>
          </details>
          <details v-if="debugResult.evidence_paths?.length" open>
            <summary>表格路径依据（{{ debugResult.evidence_paths.length }} 条）</summary>
            <article v-for="path in debugResult.evidence_paths" :key="path" class="evidence-item">
              <pre>{{ path }}</pre>
            </article>
          </details>
        </div>
      </article>
    </section>

    <section v-if="isUploadView" class="panel list-panel">
      <div class="list-header">
        <h3>解析任务</h3>
        <div class="job-summary">
          <span v-if="hasActiveJobs" class="meta-tag processing">处理中，自动刷新</span>
          <span class="meta-tag">共 {{ jobs.length }} 个任务</span>
        </div>
      </div>
      <div class="table-wrap">
        <table class="semantic-table jobs-table">
          <thead>
            <tr>
              <th>任务</th>
              <th>文件</th>
              <th>状态</th>
              <th>表格</th>
              <th>更新时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="job in jobs" :key="job.task_id || job.file_id">
              <td class="mono ellipsis" :title="job.task_id">{{ job.task_id || "-" }}</td>
              <td>{{ job.file_name || "-" }}</td>
              <td>
                <strong>{{ formatJobState(job) }}</strong>
                <small v-if="formatJobProgress(job)" class="job-progress">{{ formatJobProgress(job) }}</small>
              </td>
              <td class="field-list">{{ (job.table_ids || []).slice(0, 5).join("、") || "-" }}</td>
              <td>{{ formatTime(job.updated_at || job.created_at) }}</td>
            </tr>
            <tr v-if="jobs.length === 0">
              <td colspan="5" class="empty-cell">暂无解析任务。</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="isUploadView" class="panel list-panel">
      <div class="list-header">
        <h3>表格语义树列表</h3>
        <span class="meta-tag">共 {{ tables.length }} 张表</span>
      </div>
      <div class="table-wrap">
        <table class="semantic-table">
          <thead>
            <tr>
              <th>Table ID</th>
              <th>标题</th>
              <th>文件</th>
              <th>规模</th>
              <th>字段</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in tables" :key="item.table_id">
              <td class="mono ellipsis" :title="item.table_id">{{ item.table_id }}</td>
              <td>
                <strong>{{ item.table_title }}</strong>
                <p>{{ item.summary_text }}</p>
              </td>
              <td class="ellipsis" :title="item.file_name">{{ item.file_name }}</td>
              <td>{{ item.row_count }} 行 / {{ item.column_count }} 列</td>
              <td>
                <span class="field-list">{{ item.candidate_fields.slice(0, 8).join("、") }}</span>
              </td>
              <td>{{ formatTime(item.created_at) }}</td>
              <td>
                <div class="row-actions">
                  <button class="btn-outline" :disabled="loading.tree" @click="viewTableTree(item, 'tree')">查看构建树</button>
                  <button class="btn-outline" :disabled="loading.tree" @click="viewTableTree(item, 'json')">查看原始 JSON</button>
                </div>
              </td>
            </tr>
            <tr v-if="tables.length === 0">
              <td colspan="7" class="empty-cell">暂无表格语义树，请先上传表格。</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="isUploadView && treePreview.visible" class="panel tree-panel">
      <div class="list-header">
        <div>
          <h3>{{ treePreview.mode === "tree" ? "构建树" : "原始 JSON" }}：{{ treePreview.title }}</h3>
          <span class="meta-line">Table ID：{{ treePreview.tableId }}</span>
        </div>
        <button class="btn-ghost" @click="treePreview.visible = false">收起</button>
      </div>
      <div v-if="loading.tree" class="loading-state">正在读取表格语义树...</div>
      <template v-else>
        <div v-if="treePreview.payload" class="parse-diagnostics">
          <span class="meta-tag">解析模式：{{ formatParseMode(treePreview.payload.parse_mode) }}</span>
          <span
            class="meta-tag"
            :class="{ processing: treePreview.payload.coverage?.complete === false }"
          >
            覆盖率：{{ formatCoverage(treePreview.payload.coverage) }}
          </span>
          <span v-if="treePreview.payload.large_table_reason" class="meta-tag">
            切换原因：{{ treePreview.payload.large_table_reason }}
          </span>
        </div>
        <div v-if="treePreview.payload?.validation_warnings?.length" class="parse-warning-list">
          <strong>解析警告</strong>
          <ul>
            <li v-for="warning in treePreview.payload.validation_warnings" :key="warning">{{ warning }}</li>
          </ul>
        </div>
      </template>
      <div v-if="!loading.tree && treePreview.mode === 'tree'" class="semantic-tree-view">
        <div
          v-for="row in treeRows"
          :key="row.id"
          class="semantic-tree-row"
          :class="row.type"
          :style="{ paddingLeft: `${row.depth * 18 + 12}px` }"
        >
          <span class="tree-node-type">{{ row.type === "branch" ? "分支" : "值" }}</span>
          <strong>{{ row.name }}</strong>
          <span>{{ row.value }}</span>
        </div>
        <div v-if="treeRows.length === 0" class="empty-cell">该表格的构建树为空。</div>
      </div>
      <pre v-else-if="!loading.tree">{{ JSON.stringify(treePreview.payload, null, 2) }}</pre>
    </section>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { apiRequest } from "../api/client";

const props = defineProps({
  mode: {
    type: String,
    default: "upload",
  },
});

const isUploadView = computed(() => props.mode === "upload");
const isDebugView = computed(() => props.mode === "debug");
const pageTitle = computed(() => (isUploadView.value ? "高基表解析与上传" : "问答调试"));
const pageDescription = computed(() => (
  isUploadView.value
    ? "处理高基表，通过语义树解析链路生成可检索的层级结构。"
    : "分别验证全量语义树问答，以及普通文档、语义树与最终裁决组成的完整链路。"
));

const loading = reactive({ kbs: false, upload: false, tables: false, jobs: false, debug: false, tree: false });
const notice = ref("");
const noticeType = ref("info");
const tables = ref([]);
const jobs = ref([]);
const selectedFile = ref(null);
const fileInputRef = ref(null);
const debugResult = ref(null);

const uploadForm = reactive({
  kb_id: "",
  sheet_name: "",
});

const debugForm = reactive({
  qa_type: "table",
  question: "",
});

const treePreview = reactive({
  visible: false,
  mode: "tree",
  title: "",
  tableId: "",
  payload: null,
});

const treeRows = computed(() => {
  const tree = treePreview.payload?.tree;
  if (!tree || typeof tree !== "object") return [];
  return flattenTree(tree);
});

const tableKbs = ref([]);
const hasActiveJobs = computed(() => jobs.value.some((job) => {
  const state = String(job?.status || job?.state || job?.celery_state || "").toUpperCase();
  return ["QUEUED", "RUNNING", "PENDING", "STARTED", "PROGRESS", "RETRY"].includes(state);
}));

let pollTimer = null;
let pollInFlight = false;
let isUnmounted = false;

function setNotice(message, type = "info") {
  notice.value = message;
  noticeType.value = type;
}

function selectDebugRoute(type) {
  if (debugForm.qa_type === type) return;
  debugForm.qa_type = type;
  debugResult.value = null;
  notice.value = "";
}

async function loadKnowledgeBases() {
  loading.kbs = true;
  try {
    const data = await apiRequest("/text2sql/kb");
    const rows = Array.isArray(data) ? data : [];
    tableKbs.value = rows.filter((item) => item.usage === "table_semantic_tree");
  } catch (error) {
    setNotice(`加载知识库失败：${error.message}`, "error");
  } finally {
    loading.kbs = false;
  }
}

async function loadTables() {
  loading.tables = true;
  try {
    const data = await apiRequest("/document-qa/table/tables?limit=100");
    tables.value = Array.isArray(data.items) ? data.items : [];
  } catch (error) {
    setNotice(`加载表格语义树失败：${error.message}`, "error");
  } finally {
    loading.tables = false;
  }
}

async function loadJobs() {
  loading.jobs = true;
  try {
    const data = await apiRequest("/document-qa/table/jobs?limit=50");
    jobs.value = Array.isArray(data.items) ? data.items : [];
  } catch (error) {
    setNotice(`加载解析任务失败：${error.message}`, "error");
  } finally {
    loading.jobs = false;
  }
}

async function reloadAll() {
  await Promise.all([loadKnowledgeBases(), loadTables(), loadJobs()]);
}

function stopJobPolling() {
  if (!pollTimer) return;
  clearTimeout(pollTimer);
  pollTimer = null;
}

function startJobPolling(delay = 2000) {
  if (isUnmounted || pollTimer || pollInFlight || !isUploadView.value || !hasActiveJobs.value) return;
  pollTimer = setTimeout(() => void pollActiveJobs(), delay);
}

async function pollActiveJobs() {
  pollTimer = null;
  if (pollInFlight || !isUploadView.value) return;

  const wasActive = hasActiveJobs.value;
  pollInFlight = true;
  try {
    await loadJobs();
    if (wasActive && !hasActiveJobs.value) await loadTables();
  } finally {
    pollInFlight = false;
    if (!isUnmounted && hasActiveJobs.value) startJobPolling();
  }
}

function onSelectFile(event) {
  selectedFile.value = event?.target?.files?.[0] || null;
}

function clearFileInput() {
  selectedFile.value = null;
  if (fileInputRef.value) fileInputRef.value.value = "";
}

async function uploadTable() {
  if (!selectedFile.value) {
    setNotice("请先选择表格文件", "error");
    return;
  }
  if (!uploadForm.kb_id) {
    setNotice("请选择表格语义树知识库", "error");
    return;
  }

  const formData = new FormData();
  formData.append("file", selectedFile.value);
  formData.append("kb_id", uploadForm.kb_id);
  if (uploadForm.sheet_name) formData.append("sheet_name", uploadForm.sheet_name);

  loading.upload = true;
  try {
    const result = await apiRequest("/document-qa/table/upload", {
      method: "POST",
      body: formData,
    });
    clearFileInput();
    const count = Array.isArray(result.table_ids) ? result.table_ids.length : 1;
    setNotice(`解析任务已提交，共 ${count} 张表，batch_id：${result.batch_id || "-"}`, "success");
    await Promise.all([loadTables(), loadJobs()]);
    if (hasActiveJobs.value) startJobPolling(0);
  } catch (error) {
    setNotice(`上传失败：${error.message}`, "error");
  } finally {
    loading.upload = false;
  }
}

async function askDebug() {
  const question = debugForm.question.trim();
  if (!question) {
    setNotice("请先输入调试问题", "error");
    return;
  }

  loading.debug = true;
  debugResult.value = null;
  try {
    if (debugForm.qa_type === "table") {
      debugResult.value = await apiRequest("/document-qa/table/answer", {
        method: "POST",
        body: JSON.stringify({
          table_id: null,
          kb_id: null,
          question,
          top_k: 8,
          history: [],
        }),
      });
    } else {
      debugResult.value = await apiRequest("/document-qa/query", {
        method: "POST",
        body: JSON.stringify({
          question,
          kb_id: null,
          top_k: 8,
          history: [],
        }),
      });
    }
    setNotice("问答完成", "success");
  } catch (error) {
    setNotice(`问答失败：${error.message}`, "error");
  } finally {
    loading.debug = false;
  }
}

async function viewTableTree(item, mode) {
  treePreview.visible = true;
  treePreview.mode = mode;
  treePreview.title = item.table_title || item.file_name || item.table_id;
  treePreview.tableId = item.table_id;

  if (treePreview.payload?.table_id === item.table_id) return;
  treePreview.payload = null;

  loading.tree = true;
  try {
    treePreview.payload = await apiRequest(`/document-qa/table/tables/${item.table_id}/artifact`);
  } catch (error) {
    treePreview.visible = false;
    treePreview.payload = null;
    setNotice(`读取表格语义树失败：${error.message}`, "error");
  } finally {
    loading.tree = false;
  }
}

function flattenTree(value, depth = 0, name = "根节点", path = "root") {
  if (value === null || typeof value !== "object") {
    return [{
      id: path,
      depth,
      name,
      value: formatTreeValue(value),
      type: "leaf",
    }];
  }

  const entries = Array.isArray(value)
    ? value.map((item, index) => [String(index), item])
    : Object.entries(value);
  const rows = [{
    id: path,
    depth,
    name,
    value: `${entries.length} 项`,
    type: "branch",
  }];

  for (const [key, item] of entries) {
    rows.push(...flattenTree(item, depth + 1, key, `${path}.${key}`));
  }
  return rows;
}

function formatTreeValue(value) {
  if (value === null || value === undefined) return "空";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function formatScore(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "-";
  return `相关度 ${Math.round(num * 100)}%`;
}

function formatParseMode(value) {
  const labels = {
    enhanced_llm: "LLM 增强解析",
    plan_based: "LLM 解析计划",
    llm: "LLM 解析计划",
    heuristic: "启发式解析",
  };
  return labels[String(value || "")] || value || "未知";
}

function formatCoverage(coverage) {
  if (!coverage || typeof coverage !== "object") return "未知";
  const covered = Number(coverage.covered_cells);
  const expected = Number(coverage.expected_cells);
  if (Number.isFinite(covered) && Number.isFinite(expected)) {
    return `${covered} / ${expected}${coverage.complete === false ? "（不完整）" : ""}`;
  }
  return coverage.complete === true ? "完整" : "未知";
}

function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString("zh-CN", { hour12: false });
}

function formatJobState(job) {
  if (job?.successful) return "完成";
  if (job?.state === "FAILURE") return "失败";
  if (job?.state === "STARTED") return "处理中";
  if (job?.state === "PENDING") return "等待中";
  return job?.state || "-";
}

function formatJobProgress(job) {
  if (!job || job.successful || String(job.state || "").toUpperCase() === "FAILURE") return "";

  const progress = Number(job.progress);
  if (Number.isFinite(progress) && progress > 0) {
    return `进度 ${Math.min(100, Math.round(progress * 100))}%`;
  }

  const completed = Number(job.completed_sheets);
  const total = Number(job.total_sheets);
  if (Number.isFinite(completed) && Number.isFinite(total) && total > 0) {
    return `已完成 ${completed} / ${total} 张表`;
  }

  return "";
}

watch(hasActiveJobs, (value) => {
  if (value) startJobPolling(0);
  else stopJobPolling();
}, { immediate: true });

onMounted(async () => {
  if (isDebugView.value) {
    return;
  }
  await reloadAll();
  if (hasActiveJobs.value) startJobPolling(0);
});

onBeforeUnmount(() => {
  isUnmounted = true;
  stopJobPolling();
});
</script>

<style scoped>
.document-qa-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.panel {
  background: rgba(255, 255, 255, 0.58);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: none;
  padding: 18px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 16px;
  background: transparent;
  border: none;
  border-radius: 0;
  padding: 2px 0 10px;
}

h2 {
  margin: 0 0 8px;
  font-size: clamp(24px, 2.7vw, 34px);
  line-height: 1.1;
  font-weight: 720;
  letter-spacing: 0;
}

h3 {
  margin: 0 0 16px;
  font-size: 15px;
  font-weight: 690;
}

.header-content p {
  margin: 0;
  color: var(--text-muted);
}

.grid-top {
  display: grid;
  grid-template-columns: minmax(340px, 0.86fr) minmax(0, 1fr);
  gap: 14px;
}

.grid-top.single-panel-grid {
  grid-template-columns: minmax(0, 1fr);
}

.debug-panel {
  max-width: 980px;
}

.debug-route-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.debug-route-option {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 7px;
  min-height: 132px;
  padding: 16px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.7);
  color: var(--text-main);
  text-align: left;
}

.debug-route-option:hover {
  border-color: rgba(var(--accent-rgb), 0.3);
  background: #ffffff;
}

.debug-route-option.active {
  border-color: rgba(var(--accent-rgb), 0.46);
  background: var(--accent-light);
  box-shadow: inset 3px 0 0 var(--accent);
}

.debug-route-option strong {
  font-size: 15px;
}

.debug-route-option span {
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 520;
  line-height: 1.55;
}

.debug-route-option code {
  margin-top: auto;
  color: var(--accent);
  font-size: 12px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.form-grid.single {
  grid-template-columns: 1fr;
}

label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  font-weight: 620;
}

label span {
  color: var(--text-muted);
}

input,
select,
textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
}

.span-2 {
  grid-column: span 2;
}

.file-input-wrap input {
  padding: 8px;
}

.selected-file {
  margin-top: 12px;
  color: var(--text-muted);
  font-size: 13px;
}

.actions-row {
  margin-top: 16px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

button {
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.notice {
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 560;
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

.debug-result {
  margin-top: 16px;
  border-top: 1px solid var(--line);
  padding-top: 14px;
}

.debug-result h4 {
  margin: 0 0 8px;
  font-size: 14px;
}

.debug-result pre,
.tree-panel pre,
.evidence-item pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font: inherit;
}

.debug-result > pre,
.tree-panel pre {
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface-2);
}

.tree-panel {
  padding: 0;
  overflow: hidden;
}

.tree-panel > pre,
.tree-panel > .loading-state {
  margin: 14px;
}

.tree-panel > pre {
  max-height: 70vh;
  overflow: auto;
}

.parse-diagnostics {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 14px 0;
}

.parse-warning-list {
  margin: 12px 14px 0;
  padding: 10px 12px;
  border: 1px solid rgba(180, 83, 9, 0.28);
  border-radius: 8px;
  background: rgba(245, 158, 11, 0.08);
  color: var(--text-main);
  font-size: 12px;
}

.parse-warning-list ul {
  margin: 6px 0 0;
  padding-left: 18px;
}

.semantic-tree-view {
  max-height: 70vh;
  overflow: auto;
  padding: 6px 0;
}

.semantic-tree-row {
  display: grid;
  grid-template-columns: 48px minmax(160px, 0.45fr) minmax(220px, 1fr);
  align-items: center;
  gap: 10px;
  min-height: 38px;
  padding-block: 7px;
  padding-right: 14px;
  border-bottom: 1px solid var(--line);
  color: var(--text-muted);
  font-size: 12px;
}

.semantic-tree-row:last-child {
  border-bottom: none;
}

.semantic-tree-row.branch {
  background: rgba(var(--accent-rgb), 0.035);
}

.semantic-tree-row strong {
  overflow-wrap: anywhere;
  color: var(--text-main);
  font-size: 13px;
}

.tree-node-type {
  color: var(--accent);
  font-size: 11px;
  font-weight: 700;
}

.evidence-item {
  margin-top: 10px;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface-2);
}

.meta-line,
.meta-tag {
  color: var(--text-muted);
  font-size: 12px;
}

.meta-tag {
  display: inline-flex;
  padding: 4px 8px;
  border-radius: 7px;
  border: 1px solid var(--line);
  background: var(--surface-2);
}

.meta-tag.processing {
  border-color: rgba(var(--accent-rgb), 0.24);
  background: var(--accent-light);
  color: var(--accent);
}

.job-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.job-progress {
  display: block;
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 520;
}

.list-panel {
  padding: 0;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.72);
}

.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 14px 16px;
  border-bottom: 1px solid var(--line);
  background: rgba(244, 244, 241, 0.62);
}

.list-header h3 {
  margin: 0;
}

.table-wrap {
  overflow-x: auto;
}

.semantic-table {
  width: 100%;
  min-width: 1120px;
  border-collapse: collapse;
}

.semantic-table th,
.semantic-table td {
  border-bottom: 1px solid var(--line);
  padding: 12px 14px;
  text-align: left;
  vertical-align: top;
  font-size: 13px;
}

.semantic-table th {
  background: rgba(244, 244, 241, 0.68);
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 680;
}

.semantic-table p {
  margin: 6px 0 0;
  max-width: 360px;
  color: var(--text-muted);
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

.ellipsis {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.field-list {
  display: inline-block;
  max-width: 260px;
  color: var(--text-muted);
}

.row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 240px;
}

.row-actions button {
  padding: 8px 10px;
  font-size: 12px;
}

.empty-cell {
  text-align: center;
  color: var(--text-muted);
  padding: 28px 0;
}

@media (max-width: 1100px) {
  .grid-top {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .debug-route-grid,
  .form-grid {
    grid-template-columns: 1fr;
  }

  .span-2 {
    grid-column: span 1;
  }

  .semantic-tree-row {
    grid-template-columns: 40px minmax(0, 1fr);
  }

  .semantic-tree-row > span:last-child {
    grid-column: 2;
  }
}
</style>

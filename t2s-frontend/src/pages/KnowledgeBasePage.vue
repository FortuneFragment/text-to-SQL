<template>
  <section class="knowledge-page">
    <header class="page-header panel">
      <div class="header-content">
        <h2>知识库管理</h2>
        <p>先创建并确认知识库 ID，再进入对应知识库上传文件。</p>
      </div>
    </header>

    <div v-if="notice" class="notice" :class="noticeType">{{ notice }}</div>

    <article class="panel list-panel">
      <div class="list-header">
        <div class="list-heading">
          <h3>知识库列表</h3>
          <p>共 {{ kbList.length }} 个知识库</p>
        </div>
        <div class="list-actions">
          <button
            type="button"
            class="btn-secondary"
            :aria-expanded="showCreatePanel"
            :disabled="loading.kb"
            @click="toggleCreatePanel"
          >
            {{ showCreatePanel ? "收起新建" : "+ 新建知识库" }}
          </button>
          <button type="button" class="btn-ghost" :disabled="loading.kb" @click="loadKnowledgeBases">
            刷新列表
          </button>
        </div>
      </div>

      <Transition name="create-panel">
        <form v-if="showCreatePanel" class="create-panel" @submit.prevent="createKb">
          <div class="create-panel-header">
            <div>
              <h4>新建知识库</h4>
              <p>填写基础信息后保存，创建成功即可进入知识库上传文件。</p>
            </div>
            <button type="button" class="close-button" aria-label="关闭新建知识库表单" @click="closeCreatePanel">×</button>
          </div>

          <div class="form-grid">
            <label>
              <span>名称</span>
              <input ref="nameInputRef" v-model.trim="kbForm.name" required placeholder="例如：业务知识库" />
            </label>
            <label>
              <span>ES 索引名（可选）</span>
              <input v-model.trim="kbForm.collection_name" placeholder="例如：biz_docs_collection" />
            </label>
            <label>
              <span>用途</span>
              <select v-model="kbForm.usage">
                <option value="table_route">表路由</option>
                <option value="few_shot">Few-shot</option>
                <option value="data_dictionary">数据字典</option>
                <option value="document_qa">文档问答</option>
                <option value="table_semantic_tree">表格语义树</option>
              </select>
            </label>
            <label>
              <span>默认切片大小</span>
              <input v-model.number="kbForm.default_chunk_size" type="number" min="100" max="8000" required />
            </label>
            <label>
              <span>默认切片重叠</span>
              <input v-model.number="kbForm.default_chunk_overlap" type="number" min="0" max="2000" required />
            </label>
            <label class="description-field">
              <span>描述（可选）</span>
              <textarea v-model.trim="kbForm.description" rows="2" placeholder="说明知识库的数据范围和用途" />
            </label>
          </div>

          <div class="form-actions">
            <button type="button" class="btn-ghost" :disabled="loading.kb" @click="closeCreatePanel">取消</button>
            <button type="submit" class="btn-secondary" :disabled="loading.kb">
              {{ loading.kb ? "保存中..." : "保存并创建" }}
            </button>
          </div>
        </form>
      </Transition>

        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>名称/描述</th>
                <th>用途</th>
                <th>ES 索引名</th>
                <th>切片大小/重叠</th>
                <th>创建时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in kbList" :key="item.id">
                <td class="mono">{{ item.id }}</td>
                <td>
                  <div class="name-cell">
                    <strong>{{ item.name }}</strong>
                    <p v-if="item.description">{{ item.description }}</p>
                  </div>
                </td>
                <td>
                  <span class="usage-tag" :class="usageClass(item.usage)">{{ usageText(item.usage) }}</span>
                </td>
                <td class="mono">{{ item.collection_name }}</td>
                <td>{{ item.default_chunk_size }} / {{ item.default_chunk_overlap }}</td>
                <td>{{ formatTime(item.created_at) }}</td>
                <td>
                  <div class="row-actions">
                    <RouterLink :to="`${knowledgeDetailBase}/${item.id}`" class="btn-primary enter-link">进入知识库</RouterLink>
                    <button class="btn-danger" :disabled="loading.kb" @click="deleteKb(item)">删除</button>
                  </div>
                </td>
              </tr>
              <tr v-if="kbList.length === 0">
                <td colspan="7" class="empty-cell">暂无知识库，请先创建</td>
              </tr>
            </tbody>
          </table>
      </div>
    </article>
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { apiRequest } from "../api/client";

const loading = reactive({ kb: false });
const route = useRoute();
const notice = ref("");
const noticeType = ref("info");
const showCreatePanel = ref(false);
const nameInputRef = ref(null);
const knowledgeDetailBase = computed(() => {
  if (route.path.startsWith("/admin/document-qa")) {
    return "/admin/document-qa/knowledge";
  }
  if (route.path.startsWith("/admin/model-config")) {
    return "/admin/model-config/knowledge";
  }
  return "/admin/text2sql/knowledge";
});

const kbList = ref([]);
const kbForm = reactive({
  name: "",
  description: "",
  collection_name: "",
  usage: "table_route",
  default_chunk_size: 800,
  default_chunk_overlap: 120,
});

// 中文备注：处理setNotice相关业务数据并返回结果。
// 执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
function setNotice(message, type = "info") {
  notice.value = message;
  noticeType.value = type;
}

// 中文备注：处理resetKbForm相关业务数据并返回结果。
// 执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
function resetKbForm() {
  kbForm.name = "";
  kbForm.description = "";
  kbForm.collection_name = "";
  kbForm.usage = "table_route";
  kbForm.default_chunk_size = 800;
  kbForm.default_chunk_overlap = 120;
}

async function toggleCreatePanel() {
  showCreatePanel.value = !showCreatePanel.value;
  if (showCreatePanel.value) {
    await nextTick();
    nameInputRef.value?.focus();
  }
}

function closeCreatePanel() {
  showCreatePanel.value = false;
  resetKbForm();
}

// 中文备注：处理loadKnowledgeBases相关业务数据并返回结果。
// 执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
async function loadKnowledgeBases() {
  loading.kb = true;
  try {
    const data = await apiRequest("/text2sql/kb");
    kbList.value = Array.isArray(data) ? data : [];
  } catch (error) {
    setNotice(`加载知识库失败：${error.message}`, "error");
  } finally {
    loading.kb = false;
  }
}

// 中文备注：处理createKb相关业务数据并返回结果。
// 执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
async function createKb() {
  if (!kbForm.name.trim()) {
    setNotice("请输入知识库名称", "error");
    return;
  }

  if (Number(kbForm.default_chunk_overlap) >= Number(kbForm.default_chunk_size)) {
    setNotice("默认切片重叠必须小于切片大小", "error");
    return;
  }

  loading.kb = true;
  try {
    const payload = {
      name: kbForm.name,
      description: kbForm.description,
      collection_name: kbForm.collection_name || null,
      usage: kbForm.usage,
      default_chunk_size: Number(kbForm.default_chunk_size),
      default_chunk_overlap: Number(kbForm.default_chunk_overlap),
    };

    const created = await apiRequest("/text2sql/kb", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    resetKbForm();
    showCreatePanel.value = false;
    await loadKnowledgeBases();
    setNotice(`知识库创建成功，ID：${created.id}`, "success");
  } catch (error) {
    setNotice(`创建知识库失败：${error.message}`, "error");
  } finally {
    loading.kb = false;
  }
}

// 中文备注：处理deleteKb相关业务数据并返回结果。
// 执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
async function deleteKb(item) {
  const kbName = String(item?.name || "");
  const kbId = Number(item?.id || 0);
  if (!kbId) {
    setNotice("知识库 ID 无效，无法删除", "error");
    return;
  }
  const confirmed = window.confirm(`确认删除知识库「${kbName || kbId}」吗？`);
  if (!confirmed) return;

  loading.kb = true;
  try {
    await apiRequest(`/text2sql/kb/${kbId}`, { method: "DELETE" });
    await loadKnowledgeBases();
    setNotice("知识库删除成功", "success");
  } catch (error) {
    setNotice(`删除知识库失败：${error.message}`, "error");
  } finally {
    loading.kb = false;
  }
}

// 中文备注：处理formatTime相关业务数据并返回结果。
// 执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString("zh-CN", { hour12: false });
}

function usageText(value) {
  const usage = String(value || "table_route");
  if (usage === "few_shot") return "Few-shot";
  if (usage === "data_dictionary") return "数据字典";
  if (usage === "document_qa") return "文档问答";
  if (usage === "table_semantic_tree") return "表格语义树";
  return "表路由";
}

function usageClass(value) {
  const usage = String(value || "table_route");
  if (usage === "few_shot") return "few-shot";
  if (usage === "data_dictionary") return "data-dictionary";
  if (usage === "document_qa") return "document-qa";
  if (usage === "table_semantic_tree") return "table-semantic-tree";
  return "table-route";
}

onMounted(async () => {
  await loadKnowledgeBases();
});
</script>

<style scoped>
.knowledge-page {
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

.list-panel {
  min-width: 0;
}

.create-panel {
  margin: 0 16px;
  padding: 18px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(248, 248, 245, 0.9);
}

.create-panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 18px;
}

.create-panel-header h4 {
  margin: 0 0 5px;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.create-panel-header p {
  margin: 0;
  color: var(--text-muted);
  font-size: 13px;
}

.close-button {
  display: grid;
  width: 32px;
  height: 32px;
  padding: 0;
  place-items: center;
  border-radius: 7px;
  background: transparent;
  color: var(--text-muted);
  font-size: 20px;
  line-height: 1;
}

.close-button:hover {
  background: rgba(17, 17, 17, 0.06);
  color: var(--text-main);
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  font-weight: 620;
  min-width: 0;
}

label span {
  color: var(--text-muted);
}

input,
select,
textarea {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  padding: 10px 12px;
}

.description-field {
  grid-column: span 2;
}

.form-actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

button {
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 180ms ease, background-color 180ms ease, color 180ms ease;
}

button:active:not(:disabled) {
  transform: translateY(1px);
}

button:focus-visible,
input:focus-visible,
select:focus-visible,
textarea:focus-visible,
.enter-link:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-danger {
  background: #fff7f6;
  color: var(--error);
}

.btn-danger:hover:not(:disabled) {
  background: #fff1f0;
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

.list-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
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
  padding: 16px;
  border-bottom: 1px solid var(--line);
  background: rgba(244, 244, 241, 0.62);
}

.list-heading h3 {
  margin: 0 0 4px;
  font-size: 16px;
}

.list-heading p {
  margin: 0;
  color: var(--text-muted);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.list-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.table-wrap {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 1040px;
}

.data-table th,
.data-table td {
  border-bottom: 1px solid var(--line);
  padding: 12px 14px;
  text-align: left;
  vertical-align: top;
  font-size: 13px;
}

.data-table th {
  background: rgba(244, 244, 241, 0.68);
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 680;
}

.data-table tbody tr:hover td {
  background: rgba(17, 17, 17, 0.026);
}

.data-table tbody tr:last-child td {
  border-bottom: none;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

.name-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.name-cell p {
  margin: 0;
  color: var(--text-muted);
  max-width: 320px;
  white-space: pre-wrap;
  word-break: break-word;
}

.meta-tag {
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 7px;
  border: 1px solid var(--line);
  background: var(--surface-2);
  color: var(--text-muted);
}

.usage-tag {
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 7px;
  border: 1px solid var(--line);
  background: var(--surface-2);
  color: var(--text-muted);
}

.usage-tag.few-shot {
  background: var(--success-light);
  color: var(--success);
}

.usage-tag.data-dictionary {
  background: #fff7ed;
  color: #9a3412;
}

.usage-tag.document-qa {
  background: #eff6ff;
  color: #1d4ed8;
}

.usage-tag.table-semantic-tree {
  background: #f5f3ff;
  color: #6d28d9;
}

.enter-link {
  display: inline-flex;
  align-items: center;
  text-decoration: none;
}

.row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.empty-cell {
  text-align: center;
  color: var(--text-muted);
  padding: 54px 0;
}

.create-panel-enter-active,
.create-panel-leave-active {
  transition: opacity 180ms ease, transform 180ms ease;
}

.create-panel-enter-from,
.create-panel-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

@media (max-width: 720px) {
  .form-grid {
    grid-template-columns: 1fr;
  }

  .description-field {
    grid-column: span 1;
  }

  .list-header,
  .list-actions {
    align-items: stretch;
  }

  .list-actions {
    width: 100%;
  }

  .list-actions button {
    flex: 1;
  }

  .create-panel {
    margin: 0 10px;
    padding: 14px;
  }
}
</style>

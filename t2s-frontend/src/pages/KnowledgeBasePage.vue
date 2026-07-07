<template>
  <section class="knowledge-page">
    <header class="page-header panel">
      <div class="header-content">
        <h2>知识库管理</h2>
        <p>先创建并确认知识库 ID，再进入对应知识库上传文件。</p>
      </div>
    </header>

    <div v-if="notice" class="notice" :class="noticeType">{{ notice }}</div>

    <section class="grid-top">
      <article class="panel form-panel">
        <h3>新建知识库</h3>
        <div class="form-grid">
          <label>
            <span>名称</span>
            <input v-model.trim="kbForm.name" placeholder="例如：业务知识库" />
          </label>
          <label>
            <span>集合名（可选）</span>
            <input v-model.trim="kbForm.collection_name" placeholder="例如：biz_docs_collection" />
          </label>
          <label>
            <span>用途</span>
            <select v-model="kbForm.usage">
              <option value="table_route">表路由</option>
              <option value="few_shot">Few-shot</option>
              <option value="data_dictionary">数据字典</option>
            </select>
          </label>
          <label>
            <span>默认切片大小</span>
            <input v-model.number="kbForm.default_chunk_size" type="number" min="100" max="8000" />
          </label>
          <label>
            <span>默认切片重叠</span>
            <input v-model.number="kbForm.default_chunk_overlap" type="number" min="0" max="2000" />
          </label>
          <label class="span-2">
            <span>描述</span>
            <textarea v-model.trim="kbForm.description" rows="2" placeholder="可选描述" />
          </label>
        </div>

        <div class="actions-row">
          <button class="btn-secondary" :disabled="loading.kb" @click="createKb">新建知识库</button>
        </div>
      </article>

      <article class="panel list-panel">
        <div class="list-header">
          <h3>知识库列表</h3>
          <button class="btn-ghost" :disabled="loading.kb" @click="loadKnowledgeBases">刷新列表</button>
        </div>

        <div class="table-wrap">
          <table class="kb-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>名称</th>
                <th>用途</th>
                <th>Collection</th>
                <th>默认切片策略</th>
                <th>默认库</th>
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
                <td>
                  <span class="meta-tag" :class="{ 'default-tag': item.is_default }">
                    {{ item.is_default ? "是" : "-" }}
                  </span>
                </td>
                <td>{{ formatTime(item.created_at) }}</td>
                <td>
                  <div class="row-actions">
                    <RouterLink :to="`/admin/text2sql/knowledge/${item.id}`" class="btn-primary enter-link">进入知识库</RouterLink>
                    <button class="btn-danger" :disabled="loading.kb" @click="deleteKb(item)">删除</button>
                  </div>
                </td>
              </tr>
              <tr v-if="kbList.length === 0">
                <td colspan="8" class="empty-cell">暂无知识库，请先创建</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
    </section>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";

import { apiRequest } from "../api/client";

const loading = reactive({ kb: false });
const notice = ref("");
const noticeType = ref("info");

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
  return "表路由";
}

function usageClass(value) {
  const usage = String(value || "table_route");
  if (usage === "few_shot") return "few-shot";
  if (usage === "data_dictionary") return "data-dictionary";
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

.grid-top {
  display: grid;
  grid-template-columns: minmax(340px, 0.82fr) minmax(0, 1.8fr);
  gap: 14px;
}

.form-panel,
.list-panel {
  min-width: 0;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
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

.span-2 {
  grid-column: span 2;
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
  gap: 12px;
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

.table-wrap {
  overflow-x: auto;
}

.kb-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 1040px;
}

.kb-table th,
.kb-table td {
  border-bottom: 1px solid var(--line);
  padding: 12px 14px;
  text-align: left;
  vertical-align: top;
  font-size: 13px;
}

.kb-table th {
  background: rgba(244, 244, 241, 0.68);
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 680;
}

.kb-table tbody tr:hover td {
  background: rgba(17, 17, 17, 0.026);
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

.default-tag {
  background: #f2f2ef;
  color: var(--text-main);
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
  padding: 28px 0;
}

@media (max-width: 1200px) {
  .grid-top {
    grid-template-columns: 1fr;
  }
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

<template>
  <section class="relation-page">
    <header class="page-header panel">
      <div>
        <h2>表关系配置</h2>
        <p>三步向导维护关系白名单，支持 XLSX 批量导入导出。</p>
      </div>
    </header>

    <div v-if="notice" class="notice" :class="noticeType">{{ notice }}</div>

    <section class="panel toolbar-panel">
      <div class="toolbar-left">
        <div class="search-wrap">
          <input
            v-model.trim="searchKeyword"
            type="text"
            placeholder="按表名或描述搜索"
            @keyup.enter="searchRelations"
          />
          <button class="btn-secondary" @click="searchRelations">查询</button>
          <button class="btn-ghost" @click="resetSearch">重置</button>
        </div>
      </div>
      <div class="toolbar-right">
        <button class="btn-ghost" :disabled="loading.list || relations.length === 0" @click="exportXlsx">导出 XLSX</button>
        <button class="btn-ghost" :disabled="loading.importing" @click="triggerImport">导入 XLSX</button>
        <button class="btn-primary" @click="openCreateWizard">新增关系</button>
      </div>
      <input
        ref="importInputRef"
        type="file"
        accept=".xlsx,.xlsm,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel.sheet.macroEnabled.12"
        class="hidden-file"
        @change="onImportFileChange"
      />
    </section>

    <section class="panel table-panel">
      <div class="table-head-meta">
        <div>
          <strong>{{ total }}</strong> 条关系
        </div>
        <div class="page-size-wrap">
          <span>每页</span>
          <select v-model.number="pageSize" @change="changePageSize">
            <option :value="10">10</option>
            <option :value="20">20</option>
            <option :value="50">50</option>
          </select>
        </div>
      </div>

      <div class="table-wrap">
        <table class="relation-table">
          <thead>
            <tr>
              <th>关系摘要</th>
              <th>类型</th>
              <th>描述</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading.list">
              <td colspan="4" class="empty-cell">加载中...</td>
            </tr>
            <tr v-else-if="relations.length === 0">
              <td colspan="4" class="empty-cell">暂无关系，点击“新增关系”开始配置。</td>
            </tr>
            <tr v-for="item in relations" :key="item.id">
              <td>
                <div class="summary-main">{{ formatRelationSummary(item) }}</div>
                <div class="summary-sub">{{ item.source_table }} ↔ {{ item.target_table }}</div>
              </td>
              <td>
                <span class="type-chip">{{ item.relation_type || "N:1" }}</span>
              </td>
              <td class="desc-cell">{{ item.description || "-" }}</td>
              <td>
                <div class="actions">
                  <button class="btn-link" @click="openEditWizard(item)">编辑</button>
                  <button class="btn-link danger" @click="deleteRelation(item.id)">删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <footer v-if="total > 0" class="pager">
        <button class="btn-ghost" :disabled="page <= 1" @click="changePage(page - 1)">上一页</button>
        <span>{{ page }} / {{ totalPages }}</span>
        <button class="btn-ghost" :disabled="page >= totalPages" @click="changePage(page + 1)">下一页</button>
      </footer>
    </section>

    <div v-if="showWizard" class="wizard-mask" @click.self="closeWizard">
      <section class="wizard-panel">
        <header class="wizard-header">
          <div>
            <h3>{{ editingId ? "编辑关系" : "新增关系" }}</h3>
            <p>{{ wizardStepTitle }}</p>
          </div>
          <button class="btn-close" @click="closeWizard">×</button>
        </header>

        <div class="stepper">
          <div v-for="s in [1, 2, 3]" :key="s" class="step-item" :class="{ active: step === s, done: step > s }">
            <span>{{ s }}</span>
            <small>{{ stepLabels[s - 1] }}</small>
          </div>
        </div>

        <div class="wizard-body">
          <template v-if="step === 1">
            <div class="grid-two">
              <label>
                <span>主表</span>
                <input
                  v-model.trim="sourceTableKeyword"
                  type="text"
                  placeholder="按主表表名/备注搜索"
                />
                <select v-model="form.source_table" @change="onSourceTableChange">
                  <option value="">请选择主表</option>
                  <option
                    v-for="item in filteredSourceTableOptions"
                    :key="`s-${item.table_name}`"
                    :value="item.table_name"
                  >
                    {{ formatTableOptionLabel(item) }}
                  </option>
                </select>
              </label>
              <label>
                <span>目标表</span>
                <input
                  v-model.trim="targetTableKeyword"
                  type="text"
                  placeholder="按目标表表名/备注搜索"
                />
                <select v-model="form.target_table" @change="onTargetTableChange">
                  <option value="">请选择目标表</option>
                  <option
                    v-for="item in filteredTargetTableOptions"
                    :key="`t-${item.table_name}`"
                    :value="item.table_name"
                  >
                    {{ formatTableOptionLabel(item) }}
                  </option>
                </select>
              </label>
            </div>
          </template>

          <template v-else-if="step === 2">
            <div class="pair-header">
              <span>字段映射（顺序即复合键顺序）</span>
              <button class="btn-ghost" @click="addPairRow">+ 添加一行</button>
            </div>
            <div class="pairs">
              <div v-for="(pair, idx) in form.column_pairs" :key="`pair-${idx}`" class="pair-row">
                <select v-model="pair.source_column">
                  <option value="">主表字段</option>
                  <option v-for="col in sourceColumns" :key="`src-${idx}-${col.name}`" :value="col.name">{{ col.name }}</option>
                </select>
                <span class="pair-eq">=</span>
                <select v-model="pair.target_column">
                  <option value="">目标表字段</option>
                  <option v-for="col in targetColumns" :key="`tgt-${idx}-${col.name}`" :value="col.name">{{ col.name }}</option>
                </select>
                <button class="btn-link danger" :disabled="form.column_pairs.length <= 1" @click="removePairRow(idx)">删除</button>
              </div>
            </div>
          </template>

          <template v-else>
            <label>
              <span>关系类型</span>
              <select v-model="form.relation_type">
                <option value="1:1">1:1</option>
                <option value="1:N">1:N</option>
                <option value="N:1">N:1</option>
                <option value="N:N">N:N</option>
              </select>
            </label>
            <label>
              <span>关系描述</span>
              <textarea v-model.trim="form.description" rows="3" placeholder="例如：学生表通过班级ID关联班级表"></textarea>
            </label>
            <div class="preview-box">
              <strong>关系预览</strong>
              <p>{{ previewSummary || "请先补全表和字段映射" }}</p>
            </div>
          </template>
        </div>

        <footer class="wizard-footer">
          <button class="btn-ghost" @click="closeWizard">取消</button>
          <button v-if="step > 1" class="btn-ghost" @click="goPrevStep">上一步</button>
          <button v-if="step < 3" class="btn-secondary" @click="goNextStep">下一步</button>
          <button v-else class="btn-primary" :disabled="loading.save" @click="saveRelation">
            {{ loading.save ? "保存中..." : "保存关系" }}
          </button>
        </footer>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { API_BASE, apiRequest, readErrorDetail } from "../api/client";

const notice = ref("");
const noticeType = ref("info");

const loading = reactive({
  list: false,
  save: false,
  importing: false,
  tables: false,
});

const relations = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(10);
const searchKeyword = ref("");
const sourceTableKeyword = ref("");
const targetTableKeyword = ref("");

const availableTables = ref([]);
const columnsCache = reactive({});

const showWizard = ref(false);
const editingId = ref(null);
const step = ref(1);
const importInputRef = ref(null);

const stepLabels = ["选择表对", "映射字段", "确认信息"];

const form = reactive({
  source_table: "",
  target_table: "",
  column_pairs: [{ source_column: "", target_column: "" }],
  relation_type: "N:1",
  description: "",
});

const totalPages = computed(() => {
  const size = Math.max(1, Number(pageSize.value || 1));
  return Math.max(1, Math.ceil(Number(total.value || 0) / size));
});

const filteredSourceTableOptions = computed(() => {
  const keyword = String(sourceTableKeyword.value || "").trim().toLowerCase();
  if (!keyword) return availableTables.value;
  return availableTables.value.filter((item) => {
    const tableName = String(item.table_name || "").toLowerCase();
    const tableComment = String(item.table_comment || "").toLowerCase();
    return tableName.includes(keyword) || tableComment.includes(keyword);
  });
});

const filteredTargetTableOptions = computed(() => {
  const keyword = String(targetTableKeyword.value || "").trim().toLowerCase();
  if (!keyword) return availableTables.value;
  return availableTables.value.filter((item) => {
    const tableName = String(item.table_name || "").toLowerCase();
    const tableComment = String(item.table_comment || "").toLowerCase();
    return tableName.includes(keyword) || tableComment.includes(keyword);
  });
});

const sourceColumns = computed(() => {
  const tableName = form.source_table;
  return tableName && columnsCache[tableName] ? columnsCache[tableName] : [];
});

const targetColumns = computed(() => {
  const tableName = form.target_table;
  return tableName && columnsCache[tableName] ? columnsCache[tableName] : [];
});

const previewSummary = computed(() => {
  if (!form.source_table || !form.target_table) return "";
  const pairs = form.column_pairs
    .map((pair) => {
      const left = String(pair.source_column || "").trim();
      const right = String(pair.target_column || "").trim();
      if (!left || !right) return "";
      return `${form.source_table}.${left} = ${form.target_table}.${right}`;
    })
    .filter(Boolean);
  return pairs.join(" AND ");
});

const wizardStepTitle = computed(() => {
  return `步骤 ${step.value}/3 · ${stepLabels[step.value - 1]}`;
});

function setNotice(message, type = "info") {
  notice.value = String(message || "");
  noticeType.value = type;
}

function clearNotice() {
  notice.value = "";
}

function formatTableOptionLabel(item) {
  const name = String(item?.table_name || "").trim();
  const comment = String(item?.table_comment || "").trim();
  return comment ? `${name}（${comment}）` : name;
}

function normalizeRelationPayload(payload) {
  const sourceColumns = Array.isArray(payload.source_columns)
    ? payload.source_columns.map((item) => String(item || "").trim()).filter(Boolean)
    : String(payload.source_columns || "")
        .split(/[|,]/)
        .map((item) => item.trim())
        .filter(Boolean);
  const targetColumns = Array.isArray(payload.target_columns)
    ? payload.target_columns.map((item) => String(item || "").trim()).filter(Boolean)
    : String(payload.target_columns || "")
        .split(/[|,]/)
        .map((item) => item.trim())
        .filter(Boolean);
  return {
    source_table: String(payload.source_table || "").trim(),
    source_columns: sourceColumns,
    target_table: String(payload.target_table || "").trim(),
    target_columns: targetColumns,
    relation_type: String(payload.relation_type || "N:1").trim() || "N:1",
    description: String(payload.description || "").trim(),
  };
}

function formatRelationSummary(item) {
  const src = Array.isArray(item.source_columns) ? item.source_columns : [];
  const tgt = Array.isArray(item.target_columns) ? item.target_columns : [];
  const pairs = [];
  for (let i = 0; i < Math.min(src.length, tgt.length); i += 1) {
    pairs.push(`${item.source_table}.${src[i]} = ${item.target_table}.${tgt[i]}`);
  }
  return pairs.join(" AND ") || "-";
}

async function loadRelations() {
  loading.list = true;
  try {
    const params = new URLSearchParams({
      page: String(page.value),
      page_size: String(pageSize.value),
      keyword: searchKeyword.value,
    });
    const data = await apiRequest(`/text2sql/relation?${params.toString()}`);
    relations.value = Array.isArray(data.items) ? data.items : [];
    total.value = Number(data.total || 0);
  } catch (error) {
    setNotice(`加载关系失败：${error.message}`, "error");
  } finally {
    loading.list = false;
  }
}

async function loadTableOptions() {
  loading.tables = true;
  try {
    const data = await apiRequest("/text2sql/table/options");
    availableTables.value = Array.isArray(data.tables)
      ? data.tables
          .map((item) => ({
            table_name: String(item.table_name || "").trim(),
            table_comment: String(item.table_comment || "").trim(),
          }))
          .filter((item) => item.table_name)
      : [];
  } catch (error) {
    setNotice(`加载表列表失败：${error.message}`, "error");
  } finally {
    loading.tables = false;
  }
}

async function ensureTableColumns(tableName) {
  const safeName = String(tableName || "").trim();
  if (!safeName) return;
  if (columnsCache[safeName]) return;
  const data = await apiRequest(`/text2sql/relation/table/${encodeURIComponent(safeName)}/columns`);
  columnsCache[safeName] = Array.isArray(data.columns) ? data.columns : [];
}

function resetForm() {
  form.source_table = "";
  form.target_table = "";
  form.column_pairs = [{ source_column: "", target_column: "" }];
  form.relation_type = "N:1";
  form.description = "";
  sourceTableKeyword.value = "";
  targetTableKeyword.value = "";
}

function openCreateWizard() {
  clearNotice();
  editingId.value = null;
  step.value = 1;
  resetForm();
  showWizard.value = true;
}

async function openEditWizard(item) {
  clearNotice();
  editingId.value = Number(item.id);
  step.value = 1;
  resetForm();
  form.source_table = String(item.source_table || "");
  form.target_table = String(item.target_table || "");
  form.relation_type = String(item.relation_type || "N:1") || "N:1";
  form.description = String(item.description || "");
  sourceTableKeyword.value = String(item.source_table || "");
  targetTableKeyword.value = String(item.target_table || "");

  await Promise.all([
    ensureTableColumns(form.source_table),
    ensureTableColumns(form.target_table),
  ]);

  const sourceColumns = Array.isArray(item.source_columns) ? item.source_columns : [];
  const targetColumns = Array.isArray(item.target_columns) ? item.target_columns : [];
  const pairCount = Math.max(1, Math.min(sourceColumns.length, targetColumns.length));
  form.column_pairs = Array.from({ length: pairCount }, (_, index) => ({
    source_column: String(sourceColumns[index] || ""),
    target_column: String(targetColumns[index] || ""),
  }));
  showWizard.value = true;
}

function closeWizard() {
  showWizard.value = false;
}

async function onSourceTableChange() {
  if (!form.source_table) {
    form.column_pairs = [{ source_column: "", target_column: form.column_pairs[0]?.target_column || "" }];
    return;
  }
  await ensureTableColumns(form.source_table);
  form.column_pairs = form.column_pairs.map((pair) => ({ ...pair, source_column: "" }));
}

async function onTargetTableChange() {
  if (!form.target_table) {
    form.column_pairs = [{ source_column: form.column_pairs[0]?.source_column || "", target_column: "" }];
    return;
  }
  await ensureTableColumns(form.target_table);
  form.column_pairs = form.column_pairs.map((pair) => ({ ...pair, target_column: "" }));
}

function addPairRow() {
  form.column_pairs.push({ source_column: "", target_column: "" });
}

function removePairRow(index) {
  if (form.column_pairs.length <= 1) return;
  form.column_pairs.splice(index, 1);
}

function validateStepOne() {
  if (!form.source_table || !form.target_table) {
    setNotice("请先选择主表和目标表", "error");
    return false;
  }
  return true;
}

function validateStepTwo() {
  const hasInvalid = form.column_pairs.some((pair) => !pair.source_column || !pair.target_column);
  if (hasInvalid) {
    setNotice("请完整选择每一行的主表字段和目标表字段", "error");
    return false;
  }

  const sourceSeen = new Set();
  const targetSeen = new Set();
  for (const pair of form.column_pairs) {
    if (sourceSeen.has(pair.source_column)) {
      setNotice(`主表字段重复：${pair.source_column}`, "error");
      return false;
    }
    if (targetSeen.has(pair.target_column)) {
      setNotice(`目标表字段重复：${pair.target_column}`, "error");
      return false;
    }
    sourceSeen.add(pair.source_column);
    targetSeen.add(pair.target_column);
  }
  return true;
}

function goNextStep() {
  clearNotice();
  if (step.value === 1 && !validateStepOne()) return;
  if (step.value === 2 && !validateStepTwo()) return;
  step.value += 1;
}

function goPrevStep() {
  clearNotice();
  step.value = Math.max(1, step.value - 1);
}

function buildSavePayload() {
  const sourceColumns = form.column_pairs.map((pair) => String(pair.source_column || "").trim()).filter(Boolean);
  const targetColumns = form.column_pairs.map((pair) => String(pair.target_column || "").trim()).filter(Boolean);
  return {
    source_table: String(form.source_table || "").trim(),
    source_columns: sourceColumns,
    target_table: String(form.target_table || "").trim(),
    target_columns: targetColumns,
    relation_type: String(form.relation_type || "N:1").trim() || "N:1",
    description: String(form.description || "").trim(),
  };
}

async function saveRelation() {
  clearNotice();
  if (!validateStepOne() || !validateStepTwo()) return;
  const payload = buildSavePayload();
  if (payload.source_columns.length !== payload.target_columns.length) {
    setNotice("复合键字段数量必须一致", "error");
    return;
  }

  loading.save = true;
  try {
    if (editingId.value) {
      await apiRequest(`/text2sql/relation/${editingId.value}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      setNotice("关系更新成功", "success");
    } else {
      await apiRequest("/text2sql/relation", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setNotice("关系创建成功", "success");
    }
    closeWizard();
    await loadRelations();
  } catch (error) {
    setNotice(`保存失败：${error.message}`, "error");
  } finally {
    loading.save = false;
  }
}

async function deleteRelation(id) {
  if (!window.confirm("确定删除该关系吗？")) return;
  try {
    await apiRequest(`/text2sql/relation/${id}`, { method: "DELETE" });
    setNotice("删除成功", "success");
    await loadRelations();
  } catch (error) {
    setNotice(`删除失败：${error.message}`, "error");
  }
}

function searchRelations() {
  page.value = 1;
  loadRelations();
}

function resetSearch() {
  searchKeyword.value = "";
  page.value = 1;
  loadRelations();
}

function changePage(nextPage) {
  const target = Math.max(1, Math.min(Number(nextPage), totalPages.value));
  page.value = target;
  loadRelations();
}

function changePageSize() {
  page.value = 1;
  loadRelations();
}

function triggerImport() {
  if (importInputRef.value) {
    importInputRef.value.value = "";
    importInputRef.value.click();
  }
}

async function onImportFileChange(event) {
  const file = event?.target?.files?.[0];
  if (!file) return;

  loading.importing = true;
  clearNotice();
  try {
    const formData = new FormData();
    formData.append("file", file);
    const result = await apiRequest("/text2sql/relation/import", {
      method: "POST",
      body: formData,
    });
    await loadRelations();
    const failed = Number(result.failed || 0);
    const created = Number(result.created || 0);
    if (failed === 0) {
      setNotice(`导入完成：成功 ${created} 条`, "success");
    } else {
      const detail = Array.isArray(result.errors) ? result.errors.slice(0, 2).join("；") : "";
      setNotice(`导入完成：成功 ${created} 条，失败 ${failed} 条。${detail}`, "error");
    }
  } catch (error) {
    setNotice(`导入失败：${error.message}`, "error");
  } finally {
    loading.importing = false;
  }
}

function downloadBlob(filename, content, type) {
  const blob = content instanceof Blob ? content : new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

async function exportXlsx() {
  clearNotice();
  try {
    const response = await fetch(`${API_BASE}/text2sql/relation/export`);
    if (!response.ok) {
      const detail = await readErrorDetail(response, "导出失败");
      throw new Error(detail);
    }
    const blob = await response.blob();
    downloadBlob(
      `relations-${new Date().toISOString().slice(0, 10)}.xlsx`,
      blob,
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    );
    setNotice("已导出 XLSX", "success");
  } catch (error) {
    setNotice(`导出失败：${error.message}`, "error");
  }
}

onMounted(async () => {
  await Promise.all([loadTableOptions(), loadRelations()]);
});
</script>

<style scoped>
.relation-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.panel {
  background: rgba(255, 255, 255, 0.58);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 16px;
  box-shadow: none;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  background: transparent;
  border: none;
  border-radius: 0;
  padding: 2px 0 10px;
}

.page-header h2 {
  margin: 0;
  font-size: clamp(24px, 2.7vw, 34px);
  line-height: 1.1;
  color: var(--text-main);
  letter-spacing: 0;
}

.page-header p {
  margin: 6px 0 0;
  color: var(--text-muted);
  font-size: 14px;
}

.notice {
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 13px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.64);
  color: var(--text-main);
}

.notice.success {
  border-color: #86efac;
  background: #f0fdf4;
  color: #166534;
}

.notice.error {
  border-color: #fca5a5;
  background: #fef2f2;
  color: #991b1b;
}

.toolbar-panel {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}

.search-wrap {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.search-wrap input {
  width: 280px;
  max-width: 100%;
  padding: 10px 12px;
}

.toolbar-right {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.hidden-file {
  display: none;
}

.table-panel {
  padding: 0;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.72);
}

.table-head-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--line);
  background: rgba(244, 244, 241, 0.62);
}

.page-size-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-muted);
  font-size: 13px;
}

.page-size-wrap select {
  padding: 6px 8px;
}

.table-wrap {
  overflow-x: auto;
}

.relation-table {
  width: 100%;
  border-collapse: collapse;
}

.relation-table th,
.relation-table td {
  border-bottom: 1px solid var(--line);
  text-align: left;
  padding: 13px 16px;
  font-size: 14px;
  vertical-align: top;
}

.relation-table th {
  background: rgba(244, 244, 241, 0.66);
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 680;
}

.relation-table tbody tr:hover td {
  background: rgba(17, 17, 17, 0.026);
}

.summary-main {
  color: var(--text-main);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 13px;
  line-height: 1.45;
}

.summary-sub {
  color: var(--text-muted);
  font-size: 12px;
  margin-top: 4px;
}

.type-chip {
  display: inline-block;
  border: 1px solid var(--line);
  border-radius: 7px;
  padding: 3px 8px;
  font-size: 12px;
  background: var(--surface-2);
  color: var(--text-muted);
}

.desc-cell {
  color: var(--text-main);
  max-width: 300px;
}

.actions {
  display: flex;
  gap: 10px;
}

.empty-cell {
  text-align: center;
  color: var(--text-muted);
  padding: 28px 12px;
}

.pager {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.62);
}

.btn-primary,
.btn-secondary,
.btn-ghost {
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  padding: 8px 12px;
  cursor: pointer;
}

.btn-primary:disabled,
.btn-secondary:disabled,
.btn-ghost:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.btn-link {
  background: transparent;
  border: none;
  color: var(--text-main);
  font-size: 13px;
  font-weight: 640;
  cursor: pointer;
  padding: 0;
}

.btn-link.danger {
  color: #dc2626;
}

.wizard-mask {
  position: fixed;
  inset: 0;
  background: rgba(18, 18, 17, 0.28);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  padding: 20px;
}

.wizard-panel {
  width: min(860px, 100%);
  background: #ffffff;
  border: 1px solid var(--line-strong);
  border-radius: 8px;
  box-shadow: 0 24px 80px rgba(18, 18, 17, 0.18);
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 40px);
}

.wizard-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 16px;
  border-bottom: 1px solid var(--line);
}

.wizard-header h3 {
  margin: 0;
  font-size: 20px;
}

.wizard-header p {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--text-muted);
}

.btn-close {
  border: none;
  background: transparent;
  font-size: 24px;
  color: var(--text-muted);
  cursor: pointer;
  line-height: 1;
}

.stepper {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--line);
}

.step-item {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-soft);
  font-size: 12px;
}

.step-item span {
  width: 22px;
  height: 22px;
  border-radius: 999px;
  border: 1px solid var(--line);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
}

.step-item.active,
.step-item.done {
  color: var(--text-main);
}

.step-item.active span,
.step-item.done span {
  border-color: var(--text-main);
  color: var(--text-main);
}

.wizard-body {
  padding: 16px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.grid-two {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: var(--text-main);
}

select,
textarea {
  padding: 10px 12px;
  color: var(--text-main);
}

.pair-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: var(--text-muted);
}

.pairs {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.pair-row {
  display: grid;
  grid-template-columns: 1fr auto 1fr auto;
  gap: 8px;
  align-items: center;
}

.pair-eq {
  color: #334155;
  font-weight: 700;
}

.preview-box {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface-2);
  padding: 12px;
}

.preview-box strong {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  color: var(--text-muted);
}

.preview-box p {
  margin: 0;
  font-size: 13px;
  color: var(--text-main);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

.wizard-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--line);
}

@media (max-width: 900px) {
  .page-header {
    flex-direction: column;
  }

  .grid-two {
    grid-template-columns: 1fr;
  }

  .pair-row {
    grid-template-columns: 1fr;
  }

  .pair-eq {
    display: none;
  }

  .toolbar-panel {
    flex-direction: column;
  }
}
</style>

<template>
  <section class="relation-page">
    <header class="page-header panel">
      <div>
        <h2>表关系配置</h2>
        <p>三步向导维护关系白名单，支持批量导入导出。</p>
      </div>
      <div class="quick-nav">
        <RouterLink to="/table" class="quick-link">表开关</RouterLink>
        <RouterLink to="/field" class="quick-link">字段开关</RouterLink>
        <RouterLink to="/qa" class="quick-link">知识问答</RouterLink>
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
        <button class="btn-ghost" :disabled="loading.list || relations.length === 0" @click="exportJson">导出 JSON</button>
        <button class="btn-ghost" :disabled="loading.list || relations.length === 0" @click="exportCsv">导出 CSV</button>
        <button class="btn-ghost" :disabled="loading.importing" @click="triggerImport">导入 JSON/CSV</button>
        <button class="btn-primary" @click="openCreateWizard">新增关系</button>
      </div>
      <input
        ref="importInputRef"
        type="file"
        accept=".json,.csv,text/csv,application/json"
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
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading.list">
              <td colspan="5" class="empty-cell">加载中...</td>
            </tr>
            <tr v-else-if="relations.length === 0">
              <td colspan="5" class="empty-cell">暂无关系，点击“新增关系”开始配置。</td>
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
                <label class="switch-sm">
                  <input type="checkbox" :checked="item.is_active" @change="toggleActive(item)" />
                  <span class="slider"></span>
                </label>
              </td>
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
            <div class="grid-two">
              <label>
                <span>关系类型</span>
                <select v-model="form.relation_type">
                  <option value="1:1">1:1</option>
                  <option value="1:N">1:N</option>
                  <option value="N:1">N:1</option>
                  <option value="N:N">N:N</option>
                </select>
              </label>
              <div class="switch-line">
                <span>启用关系</span>
                <label class="switch-sm">
                  <input v-model="form.is_active" type="checkbox" />
                  <span class="slider"></span>
                </label>
              </div>
            </div>
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
import { RouterLink } from "vue-router";
import { apiRequest } from "../api/client";

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
  is_active: true,
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
    is_active: payload.is_active !== false,
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
  form.is_active = true;
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
  form.is_active = Boolean(item.is_active);
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
    is_active: Boolean(form.is_active),
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

async function toggleActive(item) {
  const payload = normalizeRelationPayload(item);
  payload.is_active = !Boolean(item.is_active);
  try {
    await apiRequest(`/text2sql/relation/${item.id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    item.is_active = payload.is_active;
    setNotice("状态已更新", "success");
  } catch (error) {
    setNotice(`更新状态失败：${error.message}`, "error");
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

function escapeCsvCell(value) {
  const text = String(value ?? "");
  if (/[",\n]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function parseCsvLine(line) {
  const cells = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    if (char === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (char === "," && !inQuotes) {
      cells.push(current);
      current = "";
    } else {
      current += char;
    }
  }
  cells.push(current);
  return cells;
}

function parseCsvRelations(text) {
  const lines = String(text || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length <= 1) return [];

  const headers = parseCsvLine(lines[0]).map((item) => item.trim());
  const records = [];
  for (let i = 1; i < lines.length; i += 1) {
    const row = parseCsvLine(lines[i]);
    const obj = {};
    headers.forEach((header, idx) => {
      obj[header] = row[idx] ?? "";
    });
    records.push({
      source_table: obj.source_table,
      source_columns: String(obj.source_columns || "")
        .split("|")
        .map((v) => v.trim())
        .filter(Boolean),
      target_table: obj.target_table,
      target_columns: String(obj.target_columns || "")
        .split("|")
        .map((v) => v.trim())
        .filter(Boolean),
      relation_type: obj.relation_type || "N:1",
      description: obj.description || "",
      is_active: String(obj.is_active || "true").toLowerCase() !== "false",
    });
  }
  return records;
}

async function onImportFileChange(event) {
  const file = event?.target?.files?.[0];
  if (!file) return;

  loading.importing = true;
  clearNotice();
  try {
    const text = await file.text();
    const isJson = file.name.toLowerCase().endsWith(".json");
    const imported = isJson ? JSON.parse(text) : parseCsvRelations(text);
    const rows = Array.isArray(imported) ? imported : [];
    if (rows.length === 0) {
      setNotice("导入文件为空或格式不正确", "error");
      return;
    }

    let successCount = 0;
    let failCount = 0;
    const failMessages = [];

    for (const row of rows) {
      const payload = normalizeRelationPayload(row);
      if (
        !payload.source_table ||
        !payload.target_table ||
        payload.source_columns.length === 0 ||
        payload.target_columns.length === 0 ||
        payload.source_columns.length !== payload.target_columns.length
      ) {
        failCount += 1;
        failMessages.push(`无效数据: ${JSON.stringify(row)}`);
        continue;
      }

      try {
        await apiRequest("/text2sql/relation", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        successCount += 1;
      } catch (error) {
        failCount += 1;
        failMessages.push(`${payload.source_table} -> ${payload.target_table}: ${error.message}`);
      }
    }

    await loadRelations();
    if (failCount === 0) {
      setNotice(`导入完成：成功 ${successCount} 条`, "success");
    } else {
      setNotice(`导入完成：成功 ${successCount} 条，失败 ${failCount} 条。${failMessages.slice(0, 2).join("；")}`, "error");
    }
  } catch (error) {
    setNotice(`导入失败：${error.message}`, "error");
  } finally {
    loading.importing = false;
  }
}

function downloadBlob(filename, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function buildExportRows() {
  return relations.value.map((item) => ({
    source_table: item.source_table,
    source_columns: Array.isArray(item.source_columns) ? item.source_columns : [],
    target_table: item.target_table,
    target_columns: Array.isArray(item.target_columns) ? item.target_columns : [],
    relation_type: item.relation_type || "N:1",
    description: item.description || "",
    is_active: Boolean(item.is_active),
  }));
}

function exportJson() {
  const rows = buildExportRows();
  downloadBlob(
    `relations-${new Date().toISOString().slice(0, 10)}.json`,
    JSON.stringify(rows, null, 2),
    "application/json;charset=utf-8"
  );
  setNotice("已导出 JSON", "success");
}

function exportCsv() {
  const rows = buildExportRows();
  const headers = [
    "source_table",
    "source_columns",
    "target_table",
    "target_columns",
    "relation_type",
    "description",
    "is_active",
  ];
  const lines = [headers.join(",")];
  rows.forEach((row) => {
    const line = [
      escapeCsvCell(row.source_table),
      escapeCsvCell(row.source_columns.join("|")),
      escapeCsvCell(row.target_table),
      escapeCsvCell(row.target_columns.join("|")),
      escapeCsvCell(row.relation_type),
      escapeCsvCell(row.description),
      escapeCsvCell(row.is_active),
    ].join(",");
    lines.push(line);
  });
  downloadBlob(
    `relations-${new Date().toISOString().slice(0, 10)}.csv`,
    lines.join("\n"),
    "text/csv;charset=utf-8"
  );
  setNotice("已导出 CSV", "success");
}

onMounted(async () => {
  await Promise.all([loadTableOptions(), loadRelations()]);
});
</script>

<style scoped>
.relation-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  padding: 16px;
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.04);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.page-header h2 {
  margin: 0;
  font-size: 22px;
  color: #0f172a;
}

.page-header p {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 14px;
}

.quick-nav {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.quick-link {
  text-decoration: none;
  color: #334155;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 13px;
  background: #f8fafc;
}

.notice {
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 13px;
  border: 1px solid #cbd5e1;
  background: #f8fafc;
  color: #334155;
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
  border: 1px solid #cbd5e1;
  border-radius: 8px;
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
}

.table-head-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #e5e7eb;
  background: #f8fafc;
}

.page-size-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #64748b;
  font-size: 13px;
}

.page-size-wrap select {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 6px 8px;
  background: #fff;
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
  border-bottom: 1px solid #e5e7eb;
  text-align: left;
  padding: 12px 16px;
  font-size: 14px;
  vertical-align: top;
}

.relation-table th {
  background: #f8fafc;
  color: #475569;
  font-weight: 600;
}

.summary-main {
  color: #0f172a;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 13px;
  line-height: 1.45;
}

.summary-sub {
  color: #64748b;
  font-size: 12px;
  margin-top: 4px;
}

.type-chip {
  display: inline-block;
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 12px;
  background: #f8fafc;
  color: #334155;
}

.desc-cell {
  color: #334155;
  max-width: 300px;
}

.actions {
  display: flex;
  gap: 10px;
}

.empty-cell {
  text-align: center;
  color: #64748b;
  padding: 28px 12px;
}

.pager {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  padding: 12px;
  background: #fff;
}

.btn-primary,
.btn-secondary,
.btn-ghost {
  border-radius: 8px;
  border: 1px solid transparent;
  font-size: 13px;
  font-weight: 600;
  padding: 8px 12px;
  cursor: pointer;
}

.btn-primary {
  background: #1d4ed8;
  color: #fff;
}

.btn-secondary {
  background: #0f172a;
  color: #fff;
}

.btn-ghost {
  background: #fff;
  border-color: #cbd5e1;
  color: #334155;
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
  color: #1d4ed8;
  font-size: 13px;
  cursor: pointer;
  padding: 0;
}

.btn-link.danger {
  color: #dc2626;
}

.wizard-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.25);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  padding: 20px;
}

.wizard-panel {
  width: min(860px, 100%);
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.14);
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 40px);
}

.wizard-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 16px;
  border-bottom: 1px solid #e5e7eb;
}

.wizard-header h3 {
  margin: 0;
  font-size: 20px;
}

.wizard-header p {
  margin: 6px 0 0;
  font-size: 13px;
  color: #64748b;
}

.btn-close {
  border: none;
  background: transparent;
  font-size: 24px;
  color: #64748b;
  cursor: pointer;
  line-height: 1;
}

.stepper {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid #e5e7eb;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #94a3b8;
  font-size: 12px;
}

.step-item span {
  width: 22px;
  height: 22px;
  border-radius: 999px;
  border: 1px solid #cbd5e1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
}

.step-item.active,
.step-item.done {
  color: #0f172a;
}

.step-item.active span,
.step-item.done span {
  border-color: #1d4ed8;
  color: #1d4ed8;
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
  color: #334155;
}

select,
textarea {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 10px 12px;
  background: #fff;
  color: #0f172a;
}

.pair-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: #334155;
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

.switch-line {
  justify-content: space-between;
}

.preview-box {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
  padding: 12px;
}

.preview-box strong {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  color: #334155;
}

.preview-box p {
  margin: 0;
  font-size: 13px;
  color: #0f172a;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

.wizard-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid #e5e7eb;
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

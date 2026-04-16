<template>
  <section class="field-page">
    <header class="page-header panel">
      <div class="header-content">
        <h2>字段开关配置</h2>
        <p>控制表内可被访问的具体字段。</p>
      </div>
      <div class="quick-nav">
        <RouterLink to="/connection" class="quick-link">连接配置</RouterLink>
        <RouterLink to="/table" class="quick-link">表开关</RouterLink>
        <RouterLink to="/knowledge" class="quick-link">知识库上传</RouterLink>
        <RouterLink to="/qa" class="quick-link">知识问答</RouterLink>
      </div>
    </header>

    <div v-if="notice" class="notice" :class="noticeType">{{ notice }}</div>

    <div v-if="!connectionConfigured" class="empty-state panel">
      <div class="empty-icon">🔌</div>
      <p>外部数据库尚未配置，请先完成连接配置。</p>
    </div>

    <template v-else>
      <section class="control-card panel">
        <div class="toolbar-row">
          <label>
            <span>搜索表名</span>
            <input v-model.trim="tableKeyword" placeholder="按表名或注释搜索" />
          </label>
          <label>
            <span>选择目标表</span>
            <select v-model="selectedTableName" @change="loadFields">
              <option value="">请选择</option>
              <option v-for="item in filteredTableOptions" :key="item.table_name" :value="item.table_name">
                {{ item.table_name }}
              </option>
            </select>
          </label>
          <div class="toolbar-actions">
            <button class="btn-secondary" @click="searchTables">应用筛选</button>
            <button class="btn-ghost" @click="resetTableFilter">重置</button>
          </div>
        </div>
      </section>

      <section class="field-content-card panel">
        <div class="field-header-row">
          <div class="field-search">
            <label><span>字段内搜索</span></label>
            <div class="input-icon-wrap">
              <span class="search-icon">🔍</span>
              <input v-model.trim="fieldKeyword" placeholder="输入字段名过滤..." class="pl-10" />
            </div>
          </div>
          <div class="table-meta-box" v-if="fieldData.table_name">
            <div class="meta-title">
              <span class="badge">当前表</span> <strong>{{ fieldData.table_name }}</strong>
            </div>
            <div class="meta-desc">{{ fieldData.table_comment || "无表注释" }}</div>
          </div>
        </div>

        <div class="stats-bar">
          <span class="stat-badge">字段总数: <strong>{{ filteredFields.length }}</strong></span>
          <span class="stat-badge">已勾选: <strong class="text-accent">{{ checkedFieldNames.length }}</strong></span>
        </div>

        <div class="batch-actions mt-4 mb-4">
          <button class="btn-outline" @click="toggleSelectFilteredFields">
            {{ allFilteredSelected ? "取消全选筛选项" : "全选筛选项" }}
          </button>
          <div class="divider"></div>
          <button class="btn-success-light" @click="batchSwitch(true)" :disabled="loading.mutate">批量开启勾选</button>
          <button class="btn-danger-light" @click="batchSwitch(false)" :disabled="loading.mutate">批量关闭勾选</button>
        </div>

        <div class="table-container">
          <header class="table-head">
            <div class="col-name">字段信息 (勾选)</div>
            <div class="col-type">数据类型</div>
            <div class="col-action">查询开关</div>
          </header>

          <article v-for="item in filteredFields" :key="item.name" class="table-row">
            <div class="col-name">
              <label class="custom-check-label">
                <input type="checkbox" class="custom-checkbox" :checked="isFieldChecked(item.name)" @change="toggleFieldCheck(item.name)" />
                <span class="field-name-text">{{ item.name }}</span>
                <span v-if="item.comment" class="field-comment-text">({{ item.comment }})</span>
              </label>
            </div>
            <div class="col-type"><span class="type-badge">{{ item.type || "-" }}</span></div>
            <div class="col-action">
              <label class="toggle-switch">
                <input type="checkbox" :checked="item.query_enabled" :disabled="loading.mutate" @change="switchSingle(item, $event)" />
                <span class="slider"></span>
                <span class="toggle-text">{{ item.query_enabled ? "开启" : "关闭" }}</span>
              </label>
            </div>
          </article>
        </div>

        <div v-if="!selectedTableName" class="empty-state py-8">👆 请在上方选择一个表以查看其字段。</div>
        <div v-else-if="filteredFields.length === 0" class="empty-state py-8">当前表没有匹配字段。</div>
      </section>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";
import { apiRequest } from "../api/client";

// 原有逻辑原封不动
const loading = reactive({ mutate: false });
const tableKeyword = ref(""); const selectedTableName = ref(""); const fieldKeyword = ref("");
const allTableOptions = ref([]); const checkedFieldNames = ref([]); const connectionConfigured = ref(false);
const notice = ref(""); const noticeType = ref("info");
const fieldData = reactive({ table_name: "", table_comment: "", fields: [] });

const filteredTableOptions = computed(() => {
  const keyword = tableKeyword.value.toLowerCase();
  if (!keyword) return allTableOptions.value;
  return allTableOptions.value.filter(item => item.table_name.toLowerCase().includes(keyword) || String(item.table_comment || "").toLowerCase().includes(keyword));
});
const filteredFields = computed(() => {
  const keyword = fieldKeyword.value.toLowerCase();
  if (!keyword) return fieldData.fields || [];
  return (fieldData.fields || []).filter((item) => item.name.toLowerCase().includes(keyword));
});
const allFilteredSelected = computed(() => {
  if (filteredFields.value.length === 0) return false;
  return filteredFields.value.every((item) => checkedFieldNames.value.includes(item.name));
});

function setNotice(message, type = "info") { notice.value = message; noticeType.value = type; }
function applyFieldResponse(data) { fieldData.table_name = data.table_name || ""; fieldData.table_comment = data.table_comment || ""; fieldData.fields = Array.isArray(data.fields) ? data.fields : []; }
function isFieldChecked(fieldName) { return checkedFieldNames.value.includes(fieldName); }
function toggleFieldCheck(fieldName) {
  if (isFieldChecked(fieldName)) { checkedFieldNames.value = checkedFieldNames.value.filter((name) => name !== fieldName); return; }
  checkedFieldNames.value = [...checkedFieldNames.value, fieldName];
}
function toggleSelectFilteredFields() {
  if (allFilteredSelected.value) {
    const currentSet = new Set(filteredFields.value.map((item) => item.name));
    checkedFieldNames.value = checkedFieldNames.value.filter((name) => !currentSet.has(name));
    return;
  }
  const merged = new Set(checkedFieldNames.value);
  for (const item of filteredFields.value) merged.add(item.name);
  checkedFieldNames.value = Array.from(merged);
}
async function loadConnectionStatus() { const data = await apiRequest("/text2sql/connection"); connectionConfigured.value = Boolean(data.configured); }
async function loadTableOptions() {
  const data = await apiRequest("/text2sql/table/options"); allTableOptions.value = Array.isArray(data.tables) ? data.tables : [];
  if (!selectedTableName.value && allTableOptions.value.length > 0) selectedTableName.value = allTableOptions.value[0].table_name;
}
async function loadFields() {
  checkedFieldNames.value = []; fieldData.table_name = ""; fieldData.table_comment = ""; fieldData.fields = []; fieldKeyword.value = "";
  if (!selectedTableName.value) return;
  try {
    const data = await apiRequest(`/text2sql/table/${encodeURIComponent(selectedTableName.value)}/fields`);
    applyFieldResponse(data);
  } catch (error) { setNotice(`加载字段失败：${error.message}`, "error"); }
}
async function searchTables() {
  const options = filteredTableOptions.value;
  if (!selectedTableName.value && options.length > 0) { selectedTableName.value = options[0].table_name; await loadFields(); return; }
  if (selectedTableName.value && !options.some((item) => item.table_name === selectedTableName.value)) { selectedTableName.value = options.length > 0 ? options[0].table_name : ""; await loadFields(); }
}
async function resetTableFilter() { tableKeyword.value = ""; if (!selectedTableName.value && allTableOptions.value.length > 0) selectedTableName.value = allTableOptions.value[0].table_name; await loadFields(); }
async function applyFieldSwitch(fieldNames, enabled) {
  if (!selectedTableName.value) { setNotice("请先选择表", "error"); return; }
  if (!fieldNames.length) { setNotice("请至少勾选一个字段", "error"); return; }
  loading.mutate = true;
  try {
    const selectedSet = new Set(fieldNames);
    const payload = { fields: fieldData.fields.map((item) => ({ name: item.name, query_enabled: selectedSet.has(item.name) ? enabled : Boolean(item.query_enabled) })) };
    const data = await apiRequest(`/text2sql/table/${encodeURIComponent(selectedTableName.value)}/fields`, { method: "PUT", body: JSON.stringify(payload) });
    applyFieldResponse(data); setNotice(enabled ? "字段批量开启成功" : "字段批量关闭成功", "success");
  } catch (error) { setNotice(`更新失败：${error.message}`, "error"); } finally { loading.mutate = false; }
}
async function switchSingle(item, event) { await applyFieldSwitch([item.name], event.target.checked); }
async function batchSwitch(enabled) { await applyFieldSwitch(checkedFieldNames.value, enabled); }

onMounted(async () => {
  try { await loadConnectionStatus(); if (!connectionConfigured.value) return; await loadTableOptions(); await loadFields(); }
  catch (error) { setNotice(`初始化失败：${error.message}`, "error"); }
});
</script>

<style scoped>
.field-page { display: flex; flex-direction: column; gap: 20px; }
.panel { background: var(--bg-panel); backdrop-filter: blur(16px); border: 1px solid rgba(255,255,255,0.8); border-radius: var(--radius); box-shadow: var(--shadow); padding: 24px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px; background: linear-gradient(to right, #ffffff, #f8fafc); }
h2 { margin: 0 0 8px; font-size: 22px; font-weight: 700; color: var(--text-main); }
.header-content p { margin: 0; color: var(--text-muted); font-size: 14px; }
.quick-nav { display: flex; gap: 8px; }
.quick-link { text-decoration: none; padding: 6px 14px; border-radius: 8px; font-size: 13px; font-weight: 600; color: var(--accent); background: var(--accent-light); transition: all 0.2s; }
.quick-link:hover { background: var(--accent); color: white; }

.toolbar-row { display: grid; grid-template-columns: 1fr 1fr auto; gap: 16px; align-items: end; }
label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 600; color: var(--text-main); }
input, select { border: 1px solid var(--line); border-radius: 8px; padding: 10px 14px; background: #fff; width: 100%; transition: 0.2s; }
input:focus, select:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-light); }
.toolbar-actions { display: flex; gap: 8px; }
button { border: none; border-radius: 8px; font-weight: 600; font-size: 14px; cursor: pointer; transition: all 0.2s; padding: 10px 16px; }
button:active:not(:disabled) { transform: scale(0.97); }
button:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary { background: var(--text-main); color: white; }
.btn-secondary:hover:not(:disabled) { background: #000; }
.btn-ghost { background: transparent; border: 1px solid var(--line); color: var(--text-main); }
.btn-ghost:hover:not(:disabled) { background: #f1f5f9; }

.field-header-row { display: flex; gap: 24px; flex-wrap: wrap; margin-bottom: 16px; align-items: flex-end; }
.field-search { flex: 1; min-width: 280px; }
.input-icon-wrap { position: relative; }
.search-icon { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); font-size: 14px; color: #94a3b8; }
.pl-10 { padding-left: 36px; }

.table-meta-box { background: #f8fafc; border: 1px solid var(--line); padding: 12px 20px; border-radius: 12px; flex: 2; min-width: 300px; display: flex; flex-direction: column; justify-content: center;}
.meta-title { font-size: 16px; margin-bottom: 4px; }
.badge { background: var(--accent); color: white; font-size: 11px; padding: 2px 6px; border-radius: 4px; margin-right: 6px; vertical-align: middle; }
.meta-desc { color: var(--text-muted); font-size: 13px; }

.stats-bar { display: flex; gap: 12px; border-top: 1px dashed var(--line); padding-top: 16px; margin-top: 16px;}
.stat-badge { background: #f8fafc; padding: 6px 12px; border-radius: 6px; font-size: 13px; border: 1px solid #e2e8f0; }
.text-accent { color: var(--accent); }

.batch-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.mt-4 { margin-top: 16px; } .mb-4 { margin-bottom: 16px; }
.divider { width: 1px; height: 24px; background: var(--line); margin: 0 4px; }
.btn-outline { border: 1px solid var(--accent); color: var(--accent); background: transparent; }
.btn-outline:hover:not(:disabled) { background: var(--accent-light); }
.btn-success-light { background: #d1fae5; color: #065f46; }
.btn-success-light:hover:not(:disabled) { background: #10b981; color: white; }
.btn-danger-light { background: #fee2e2; color: #991b1b; }
.btn-danger-light:hover:not(:disabled) { background: #ef4444; color: white; }

.table-container { border: 1px solid var(--line); border-radius: 12px; overflow: hidden; background: #fff; }
.table-head { display: grid; grid-template-columns: 3fr 1.5fr 1.5fr; background: #f8fafc; font-weight: 600; font-size: 13px; color: var(--text-muted); border-bottom: 1px solid var(--line); }
.table-head > div { padding: 12px 16px; }
.table-row { display: grid; grid-template-columns: 3fr 1.5fr 1.5fr; border-bottom: 1px solid #f1f5f9; align-items: center; transition: background 0.2s; }
.table-row:hover { background: #f8fafc; }
.table-row:last-child { border-bottom: none; }
.table-row > div { padding: 12px 16px; font-size: 14px; }

.custom-check-label { display: flex; align-items: center; gap: 10px; cursor: pointer; flex-direction: row; }
.custom-checkbox { width: 16px; height: 16px; accent-color: var(--accent); }
.field-name-text { font-weight: 600; color: var(--text-main); }
.field-comment-text { color: var(--text-muted); font-size: 12px; }
.type-badge { background: #f1f5f9; padding: 2px 8px; border-radius: 4px; font-family: monospace; font-size: 12px; color: var(--text-muted); }

/* Toggle Switch */
.toggle-switch { position: relative; display: inline-flex; align-items: center; cursor: pointer; gap: 8px; }
.toggle-switch input { opacity: 0; width: 0; height: 0; position: absolute; }
.slider { position: relative; width: 38px; height: 20px; background-color: #cbd5e1; border-radius: 20px; transition: .4s; }
.slider:before { position: absolute; content: ""; height: 14px; width: 14px; left: 3px; bottom: 3px; background-color: white; border-radius: 50%; transition: .4s; box-shadow: 0 1px 2px rgba(0,0,0,0.1); }
input:checked + .slider { background-color: var(--success); }
input:checked + .slider:before { transform: translateX(18px); }
.toggle-text { font-size: 13px; font-weight: 500; color: var(--text-muted); width: 30px; }
input:checked ~ .toggle-text { color: var(--success); }

.empty-state { text-align: center; padding: 48px 20px; color: var(--text-muted); }
.empty-icon { font-size: 48px; margin-bottom: 16px; opacity: 0.5; }
.notice { padding: 12px 16px; border-radius: 10px; font-size: 14px; font-weight: 500; margin-bottom: 20px; }
.notice.success { background: #d1fae5; color: #065f46; border: 1px solid #34d399; }
.notice.error { background: #fee2e2; color: #991b1b; border: 1px solid #f87171; }
</style>

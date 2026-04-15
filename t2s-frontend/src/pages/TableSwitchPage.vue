<template>
  <section class="table-page">
    <header class="page-header panel">
      <div class="header-content">
        <h2>表开关配置</h2>
        <p>通过后端配置项控制可参与 Text2SQL 的表范围。</p>
      </div>
      <div class="quick-nav">
        <RouterLink to="/connection" class="quick-link">连接配置</RouterLink>
        <RouterLink to="/field" class="quick-link">字段开关</RouterLink>
        <RouterLink to="/qa" class="quick-link">知识问答</RouterLink>
      </div>
    </header>

    <div v-if="notice" class="notice" :class="noticeType">{{ notice }}</div>

    <div v-if="!connectionConfigured" class="empty-state panel">
      <div class="empty-icon">🔌</div>
      <p>外部数据库尚未配置，请先完成连接配置。</p>
      <RouterLink to="/connection" class="btn-primary mt-4 inline-block">去配置</RouterLink>
    </div>

    <template v-else>
      <section class="control-card panel">
        <div class="toolbar-row">
          <label>
            <span>表名/注释搜索</span>
            <div class="input-icon-wrap">
              <span class="search-icon">🔍</span>
              <input v-model.trim="filters.keyword" class="pl-10" placeholder="输入关键字..." @keyup.enter="searchTables" />
            </div>
          </label>
          <label>
            <span>快速选择表</span>
            <select v-model="filters.quickTable" @change="applyQuickTableFilter">
              <option value="">全部表</option>
              <option v-for="item in tableOptions" :key="item.table_name" :value="item.table_name">{{ item.table_name }}</option>
            </select>
          </label>
          <label>
            <span>每页条数</span>
            <select v-model.number="tablePage.page_size" @change="changePageSize">
              <option :value="12">12</option>
              <option :value="24">24</option>
              <option :value="50">50</option>
              <option :value="100">100</option>
            </select>
          </label>
          <div class="toolbar-actions">
            <button class="btn-secondary" @click="searchTables">查询</button>
            <button class="btn-ghost" @click="resetFilters">重置</button>
          </div>
        </div>

        <div class="stats-row">
          <span class="stat-badge">总计: <strong>{{ filteredRows.length }}</strong> 表</span>
          <span class="stat-badge">页码: <strong>{{ tablePage.page }} / {{ totalPages }}</strong></span>
          <span class="stat-badge">已选: <strong class="text-accent">{{ checkedTableNames.length }}</strong></span>
          <span class="stat-badge">已启用: <strong class="text-success">{{ enabledTableNames.length }}</strong></span>
        </div>

        <div class="batch-actions">
          <button class="btn-outline" @click="toggleSelectCurrentPage">{{ allCurrentPageSelected ? "取消全选" : "全选本页" }}</button>
          <div class="divider"></div>
          <button class="btn-success-light" @click="batchSwitchSelected(true)" :disabled="loading.mutate">开启勾选项</button>
          <button class="btn-danger-light" @click="batchSwitchSelected(false)" :disabled="loading.mutate">关闭勾选项</button>
          <button class="btn-primary" @click="batchSwitchByFilter(true)" :disabled="loading.mutate">一键开启所有筛选结果</button>
        </div>
      </section>

      <section class="table-card panel">
        <header class="table-head">
          <div class="col-check">选</div>
          <div class="col-name">表名</div>
          <div class="col-comment">表注释</div>
          <div class="col-action">状态开关</div>
        </header>

        <article v-for="item in pageItems" :key="item.table_name" class="table-row">
          <div class="col-check">
            <input type="checkbox" class="custom-checkbox" :checked="isChecked(item.table_name)" @change="toggleCheck(item.table_name)" />
          </div>
          <div class="col-name"><strong>{{ item.table_name }}</strong></div>
          <div class="col-comment text-muted">{{ item.table_comment || "-" }}</div>
          <div class="col-action">
            <label class="toggle-switch">
              <input type="checkbox" :checked="item.enabled" :disabled="loading.mutate" @change="switchSingle(item, $event)" />
              <span class="slider"></span>
              <span class="toggle-text">{{ item.enabled ? "已开启" : "已关闭" }}</span>
            </label>
          </div>
        </article>
        <div v-if="pageItems.length === 0" class="empty-state py-8">当前条件下暂无数据表。</div>
      </section>

      <section class="pager-card panel" v-if="filteredRows.length > 0">
        <button class="btn-ghost" :disabled="tablePage.page <= 1" @click="changePage(tablePage.page - 1)">上一页</button>
        <div class="page-numbers">
          <button v-for="item in pageButtonItems" :key="`page-${item}`" class="page-btn" :class="{ active: item === tablePage.page, dots: item === '...' }" :disabled="item === '...'" @click="item === '...' ? null : changePage(item)">
            {{ item }}
          </button>
        </div>
        <button class="btn-ghost" :disabled="tablePage.page >= totalPages" @click="changePage(tablePage.page + 1)">下一页</button>
        <div class="jump-wrap">
          跳转 <input v-model.number="jumpPage" type="number" min="1" :max="Math.max(1, totalPages)" class="jump-input" />
          <button class="btn-secondary" @click="goToJumpPage">GO</button>
        </div>
      </section>

      <section class="prompt-card panel">
        <h3>配置业务提示词</h3>
        <p class="text-muted mb-4">设定 Text2SQL 生成 SQL 时的偏好和规则。</p>
        <textarea v-model="promptHint" rows="3" placeholder="例如：优先按最近一周统计；字段需要给出中文可读含义" class="w-full"></textarea>
        <div class="mt-4 text-right">
          <button class="btn-primary" @click="savePromptHint" :disabled="loading.prompt">保存提示词设置</button>
        </div>
      </section>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { apiRequest } from "../api/client";

// 原有逻辑原封不动
const loading = reactive({ mutate: false, prompt: false });
const tablePage = reactive({ page: 1, page_size: 12 });
const filters = reactive({ keyword: "", quickTable: "" });
const tableOptions = ref([]); const checkedTableNames = ref([]); const enabledTableNames = ref([]);
const promptHint = ref(""); const connectionConfigured = ref(false);
const notice = ref(""); const noticeType = ref("info"); const jumpPage = ref(1);

const enabledSet = computed(() => new Set(enabledTableNames.value));
const tableRows = computed(() => tableOptions.value.map((item) => ({ table_name: item.table_name, table_comment: item.table_comment || "", enabled: enabledSet.value.has(item.table_name) })));
const filteredRows = computed(() => {
  const keyword = (filters.keyword || "").trim().toLowerCase();
  if (!keyword) return tableRows.value;
  return tableRows.value.filter(item => item.table_name.toLowerCase().includes(keyword) || String(item.table_comment || "").toLowerCase().includes(keyword));
});
const totalPages = computed(() => filteredRows.value.length === 0 ? 1 : Math.ceil(filteredRows.value.length / tablePage.page_size));
const pageItems = computed(() => filteredRows.value.slice((tablePage.page - 1) * tablePage.page_size, tablePage.page * tablePage.page_size));
const allCurrentPageSelected = computed(() => pageItems.value.length > 0 && pageItems.value.every((item) => checkedTableNames.value.includes(item.table_name)));
const pageButtonItems = computed(() => {
  const total = totalPages.value; const current = Math.max(1, Number(tablePage.page || 1));
  if (total <= 8) return Array.from({ length: total }, (_, i) => i + 1);
  const pages = new Set([1, total, current - 1, current, current + 1]);
  const validPages = Array.from(pages).filter((p) => p >= 1 && p <= total).sort((a, b) => a - b);
  const result = [];
  for (let i = 0; i < validPages.length; i += 1) {
    const p = validPages[i]; const prev = validPages[i - 1];
    if (prev && p - prev > 1) result.push("...");
    result.push(p);
  }
  return result;
});

watch([filteredRows, () => tablePage.page_size], () => { if (tablePage.page > totalPages.value) tablePage.page = totalPages.value; jumpPage.value = tablePage.page; }, { immediate: true });

function setNotice(message, type = "info") { notice.value = message; noticeType.value = type; }
function isChecked(tableName) { return checkedTableNames.value.includes(tableName); }
function toggleCheck(tableName) {
  if (isChecked(tableName)) { checkedTableNames.value = checkedTableNames.value.filter((name) => name !== tableName); return; }
  checkedTableNames.value = [...checkedTableNames.value, tableName];
}
function toggleSelectCurrentPage() {
  if (allCurrentPageSelected.value) {
    const pageSet = new Set(pageItems.value.map((item) => item.table_name));
    checkedTableNames.value = checkedTableNames.value.filter((name) => !pageSet.has(name));
    return;
  }
  const merged = new Set(checkedTableNames.value);
  for (const item of pageItems.value) merged.add(item.table_name);
  checkedTableNames.value = Array.from(merged);
}
function buildOrderedSelectedTables(nextSet) { return tableOptions.value.map((item) => item.table_name).filter((tableName) => nextSet.has(tableName)); }
async function loadConnectionStatus() { const data = await apiRequest("/text2sql/connection"); connectionConfigured.value = Boolean(data.configured); }
async function loadTableOptions() {
  const data = await apiRequest("/text2sql/table/options"); tableOptions.value = Array.isArray(data.tables) ? data.tables : [];
  const tableNameSet = new Set(tableOptions.value.map((item) => item.table_name)); checkedTableNames.value = checkedTableNames.value.filter((name) => tableNameSet.has(name));
}
async function loadConfig() { const data = await apiRequest("/text2sql/table/config"); enabledTableNames.value = Array.isArray(data.selected_tables) ? data.selected_tables : []; promptHint.value = data.prompt_hint || ""; }
async function saveConfig(selectedTables, hint, successMessage, loadingKey = "mutate") {
  loading[loadingKey] = true;
  try {
    const data = await apiRequest("/text2sql/table/config", { method: "PUT", body: JSON.stringify({ selected_tables: selectedTables, prompt_hint: hint }) });
    enabledTableNames.value = Array.isArray(data.selected_tables) ? data.selected_tables : []; promptHint.value = data.prompt_hint || "";
    setNotice(successMessage, "success");
  } catch (error) { setNotice(`保存失败：${error.message}`, "error"); } finally { loading[loadingKey] = false; }
}
async function searchTables() { tablePage.page = 1; }
async function applyQuickTableFilter() { filters.keyword = filters.quickTable || ""; tablePage.page = 1; }
async function changePage(page) { const target = Math.max(1, Math.min(Number(page), totalPages.value)); tablePage.page = target; jumpPage.value = target; }
async function changePageSize() { tablePage.page = 1; }
async function goToJumpPage() { await changePage(jumpPage.value || 1); }
async function resetFilters() { filters.keyword = ""; filters.quickTable = ""; tablePage.page = 1; }
async function applyTableSwitch(tableNames, enabled) {
  if (!tableNames.length) { setNotice("请至少选择一个表", "error"); return; }
  const nextSet = new Set(enabledTableNames.value);
  for (const tableName of tableNames) { if (enabled) nextSet.add(tableName); else nextSet.delete(tableName); }
  await saveConfig(buildOrderedSelectedTables(nextSet), promptHint.value, enabled ? "表批量开启成功" : "表批量关闭成功", "mutate");
}
async function switchSingle(item, event) { await applyTableSwitch([item.table_name], event.target.checked); }
async function batchSwitchSelected(enabled) { await applyTableSwitch(checkedTableNames.value, enabled); }
async function batchSwitchCurrentPage(enabled) { await applyTableSwitch(pageItems.value.map((item) => item.table_name), enabled); }
async function batchSwitchByFilter(enabled) { await applyTableSwitch(filteredRows.value.map((item) => item.table_name), enabled); }
async function savePromptHint() { await saveConfig(buildOrderedSelectedTables(new Set(enabledTableNames.value)), promptHint.value, "提示词保存成功", "prompt"); }

onMounted(async () => {
  try { await loadConnectionStatus(); if (!connectionConfigured.value) return; await Promise.all([loadTableOptions(), loadConfig()]); }
  catch (error) { setNotice(`初始化失败：${error.message}`, "error"); }
});
</script>

<style scoped>
.table-page { display: flex; flex-direction: column; gap: 20px; }
.panel { background: var(--bg-panel); backdrop-filter: blur(16px); border: 1px solid rgba(255,255,255,0.8); border-radius: var(--radius); box-shadow: var(--shadow); padding: 24px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px; background: linear-gradient(to right, #ffffff, #f8fafc); }
h2 { margin: 0 0 8px; font-size: 22px; font-weight: 700; color: var(--text-main); }
.header-content p { margin: 0; color: var(--text-muted); font-size: 14px; }
.quick-nav { display: flex; gap: 8px; }
.quick-link { text-decoration: none; padding: 6px 14px; border-radius: 8px; font-size: 13px; font-weight: 600; color: var(--accent); background: var(--accent-light); transition: all 0.2s; }
.quick-link:hover { background: var(--accent); color: white; }
.text-muted { color: var(--text-muted); }
.text-accent { color: var(--accent); }
.text-success { color: var(--success); }

.toolbar-row { display: grid; grid-template-columns: 2fr 1fr 1fr auto; gap: 16px; align-items: end; }
label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 600; color: var(--text-main); }
.input-icon-wrap { position: relative; }
.search-icon { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); font-size: 14px; color: #94a3b8; }
input, select, textarea { border: 1px solid var(--line); border-radius: 8px; padding: 10px 14px; background: #fff; color: var(--text-main); width: 100%; transition: 0.2s; }
input.pl-10 { padding-left: 36px; }
input:focus, select:focus, textarea:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-light); }

.toolbar-actions { display: flex; gap: 8px; }
button { border: none; border-radius: 8px; font-weight: 600; font-size: 14px; cursor: pointer; transition: all 0.2s; padding: 10px 16px; }
button:active:not(:disabled) { transform: scale(0.97); }
button:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: var(--accent); color: white; box-shadow: 0 2px 8px rgba(79, 70, 229, 0.25); }
.btn-primary:hover:not(:disabled) { background: var(--accent-hover); }
.btn-secondary { background: var(--text-main); color: white; }
.btn-secondary:hover:not(:disabled) { background: #000; }
.btn-ghost { background: transparent; border: 1px solid var(--line); color: var(--text-main); }
.btn-ghost:hover:not(:disabled) { background: #f1f5f9; }
.btn-outline { border: 1px solid var(--accent); color: var(--accent); background: transparent; }
.btn-outline:hover:not(:disabled) { background: var(--accent-light); }
.btn-success-light { background: #d1fae5; color: #065f46; }
.btn-success-light:hover:not(:disabled) { background: #10b981; color: white; }
.btn-danger-light { background: #fee2e2; color: #991b1b; }
.btn-danger-light:hover:not(:disabled) { background: #ef4444; color: white; }

.stats-row { display: flex; gap: 12px; margin-top: 16px; padding-top: 16px; border-top: 1px dashed var(--line); flex-wrap: wrap; }
.stat-badge { background: #f8fafc; padding: 6px 12px; border-radius: 6px; font-size: 13px; border: 1px solid #e2e8f0; }

.batch-actions { display: flex; align-items: center; gap: 10px; margin-top: 16px; flex-wrap: wrap; }
.divider { width: 1px; height: 24px; background: var(--line); margin: 0 4px; }

/* Table Styles */
.table-card { padding: 0; overflow: hidden; }
.table-head { display: grid; grid-template-columns: 60px 2fr 3fr 120px; background: #f8fafc; font-weight: 600; font-size: 13px; color: var(--text-muted); border-bottom: 1px solid var(--line); }
.table-head > div { padding: 14px 16px; }
.table-row { display: grid; grid-template-columns: 60px 2fr 3fr 120px; border-bottom: 1px solid #f1f5f9; transition: background 0.2s; align-items: center; }
.table-row:hover { background: #f8fafc; }
.table-row:last-child { border-bottom: none; }
.table-row > div { padding: 14px 16px; font-size: 14px; }

/* Custom Checkbox */
.custom-checkbox { width: 18px; height: 18px; accent-color: var(--accent); cursor: pointer; }

/* Toggle Switch */
.toggle-switch { position: relative; display: inline-flex; align-items: center; cursor: pointer; gap: 10px; }
.toggle-switch input { opacity: 0; width: 0; height: 0; position: absolute; }
.slider { position: relative; width: 44px; height: 24px; background-color: #cbd5e1; border-radius: 24px; transition: .4s; }
.slider:before { position: absolute; content: ""; height: 18px; width: 18px; left: 3px; bottom: 3px; background-color: white; border-radius: 50%; transition: .4s; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
input:checked + .slider { background-color: var(--success); }
input:checked + .slider:before { transform: translateX(20px); }
.toggle-text { font-size: 13px; font-weight: 500; color: var(--text-muted); width: 45px;}
input:checked ~ .toggle-text { color: var(--success); }

/* Pager */
.pager-card { display: flex; justify-content: center; align-items: center; gap: 12px; flex-wrap: wrap; }
.page-numbers { display: flex; gap: 6px; }
.page-btn { min-width: 36px; height: 36px; padding: 0 10px; background: white; border: 1px solid var(--line); border-radius: 8px; color: var(--text-main); cursor: pointer; }
.page-btn.active { background: var(--accent); color: white; border-color: var(--accent); font-weight: bold; box-shadow: 0 2px 6px rgba(79,70,229,0.3); }
.page-btn.dots { cursor: default; border: none; background: transparent; }
.jump-wrap { display: inline-flex; align-items: center; gap: 8px; font-size: 14px; color: var(--text-muted); margin-left: auto; }
.jump-input { width: 64px; text-align: center; padding: 8px; }

.empty-state { text-align: center; padding: 48px 20px; color: var(--text-muted); }
.empty-icon { font-size: 48px; margin-bottom: 16px; opacity: 0.5; }
.w-full { width: 100%; } .mt-4 { margin-top: 16px; } .mb-4 { margin-bottom: 16px; } .inline-block { display: inline-block; }

.notice { padding: 12px 16px; border-radius: 10px; font-size: 14px; font-weight: 500; margin-bottom: 20px; }
.notice.success { background: #d1fae5; color: #065f46; border: 1px solid #34d399; }
.notice.error { background: #fee2e2; color: #991b1b; border: 1px solid #f87171; }
</style>
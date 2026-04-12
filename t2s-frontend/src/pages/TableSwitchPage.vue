<template>
  <section class="panel">
    <h2>表开关配置</h2>

    <div class="quick-nav">
      <RouterLink to="/connection" class="quick-link">去连接配置</RouterLink>
      <RouterLink to="/qa" class="quick-link">去知识问答</RouterLink>
    </div>

    <div v-if="notice" class="notice" :class="noticeType">{{ notice }}</div>

    <div v-if="!connectionConfigured" class="empty">外部数据库尚未配置，请先完成连接配置。</div>

    <template v-else>
      <h3>可查询数据表</h3>
      <div class="toolbar">
        <label class="search-box">
          按表名搜索
          <input v-model.trim="tableKeyword" placeholder="例如：student / score" />
        </label>
        <div class="stats">
          <span class="tag">总表数 {{ schemaTables.length }}</span>
          <span class="tag">匹配数 {{ filteredTables.length }}</span>
          <span class="tag">已选 {{ config.selected_tables.length }}</span>
        </div>
      </div>

      <div class="row">
        <button @click="selectFilteredTables" :disabled="filteredTables.length === 0">全选匹配项</button>
        <button class="ghost" @click="clearFilteredTables" :disabled="filteredTables.length === 0">清空匹配项</button>
        <button @click="saveConfig" :disabled="loading.config">保存表开关</button>
      </div>

      <div class="table-checks">
        <label v-for="table in filteredTables" :key="table.table_name" class="checkbox-item">
          <input type="checkbox" :value="table.table_name" v-model="config.selected_tables" />
          <span>{{ table.table_name }}</span>
        </label>
      </div>

      <p v-if="schemaTables.length === 0" class="empty">当前数据库未发现可用数据表。</p>
      <p v-else-if="filteredTables.length === 0" class="empty">没有匹配当前关键字的表。</p>

      <label>
        业务提示词
        <textarea v-model="config.prompt_hint" rows="3" placeholder="例如：只统计最近一次考试" />
      </label>

      <h3>字段预览</h3>
      <div class="preview-toolbar">
        <label>
          选择预览表
          <select v-model="previewTableName">
            <option v-for="table in previewCandidates" :key="table.table_name" :value="table.table_name">
              {{ table.table_name }}
            </option>
          </select>
        </label>
      </div>

      <article v-if="previewTable" class="schema-card">
        <h4>{{ previewTable.table_name }}</h4>
        <ul>
          <li v-for="col in previewTable.columns" :key="`${previewTable.table_name}-${col.name}`">
            <strong>{{ col.name }}</strong>
            <small>{{ col.type }}</small>
          </li>
        </ul>
      </article>
      <p v-else class="empty">暂无可预览的表。</p>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { RouterLink } from "vue-router";

import { apiRequest } from "../api/client";

const loading = reactive({
  config: false,
});

const config = reactive({
  selected_tables: [],
  prompt_hint: "",
});

const schemaTables = ref([]);
const connectionConfigured = ref(false);
const notice = ref("");
const noticeType = ref("info");
const tableKeyword = ref("");
const previewTableName = ref("");

const filteredTables = computed(() => {
  const keyword = tableKeyword.value.toLowerCase();
  if (!keyword) {
    return schemaTables.value;
  }
  return schemaTables.value.filter((table) => table.table_name.toLowerCase().includes(keyword));
});

const previewCandidates = computed(() => {
  if (filteredTables.value.length > 0) {
    return filteredTables.value;
  }
  return schemaTables.value;
});

const previewTable = computed(() => {
  if (!previewTableName.value) {
    return previewCandidates.value[0] || null;
  }
  return previewCandidates.value.find((table) => table.table_name === previewTableName.value) || null;
});

watch(
  previewCandidates,
  (next) => {
    if (!next.length) {
      previewTableName.value = "";
      return;
    }
    const exists = next.some((table) => table.table_name === previewTableName.value);
    if (!exists) {
      previewTableName.value = next[0].table_name;
    }
  },
  { immediate: true }
);

function setNotice(message, type = "info") {
  notice.value = message;
  noticeType.value = type;
}

function filterSelectedTablesBySchema() {
  const valid = new Set(schemaTables.value.map((t) => t.table_name));
  config.selected_tables = config.selected_tables.filter((name) => valid.has(name));
}

function selectFilteredTables() {
  const merged = new Set(config.selected_tables);
  for (const table of filteredTables.value) {
    merged.add(table.table_name);
  }
  config.selected_tables = Array.from(merged);
}

function clearFilteredTables() {
  const filteredNames = new Set(filteredTables.value.map((table) => table.table_name));
  config.selected_tables = config.selected_tables.filter((tableName) => !filteredNames.has(tableName));
}

async function loadConnectionStatus() {
  const data = await apiRequest("/text2sql/connection");
  connectionConfigured.value = Boolean(data.configured);
}

async function loadSchema() {
  const data = await apiRequest("/text2sql/schema");
  schemaTables.value = data.tables || [];
  filterSelectedTablesBySchema();
}

async function loadConfig() {
  const data = await apiRequest("/text2sql/config");
  config.selected_tables = data.selected_tables || [];
  config.prompt_hint = data.prompt_hint || "";
  filterSelectedTablesBySchema();
}

async function saveConfig() {
  loading.config = true;
  try {
    const data = await apiRequest("/text2sql/config", {
      method: "PUT",
      body: JSON.stringify(config),
    });
    config.selected_tables = data.selected_tables || [];
    config.prompt_hint = data.prompt_hint || "";
    setNotice("表开关配置已保存", "success");
  } catch (error) {
    setNotice(`保存失败：${error.message}`, "error");
  } finally {
    loading.config = false;
  }
}

onMounted(async () => {
  try {
    await loadConnectionStatus();
    if (!connectionConfigured.value) {
      schemaTables.value = [];
      return;
    }
    await loadSchema();
    await loadConfig();
  } catch (error) {
    setNotice(`初始化失败：${error.message}`, "error");
  }
});
</script>

<style scoped>
.panel {
  background: var(--bg-panel);
  backdrop-filter: blur(8px);
  border: 1px solid var(--line);
  border-radius: 18px;
  box-shadow: var(--shadow);
  padding: 20px;
}

h2 {
  margin: 0 0 12px;
  font-size: 20px;
}

h3 {
  margin: 16px 0 10px;
  font-size: 18px;
}

.quick-nav {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
}

.quick-link {
  text-decoration: none;
  color: var(--text-main);
  border: 1px solid var(--line);
  background: #ffffff;
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 13px;
  font-weight: 600;
}

.toolbar {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  justify-content: space-between;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.search-box {
  min-width: min(440px, 100%);
}

.stats {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.tag {
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  background: #eef6ff;
  color: #1d4ed8;
  border: 1px solid #cde0ff;
}

label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 14px;
  color: var(--text-muted);
}

input,
textarea,
select {
  background: var(--bg-card);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 10px 12px;
  color: var(--text-main);
}

.row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 12px 0 16px;
  flex-wrap: wrap;
}

button {
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: 10px;
  padding: 10px 14px;
  font-weight: 600;
  cursor: pointer;
}

button.ghost {
  background: #ffffff;
  color: var(--text-main);
  border: 1px solid var(--line);
}

button:hover {
  background: var(--accent-strong);
}

button.ghost:hover {
  background: #f6f8fa;
}

button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.table-checks {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 8px;
  margin-bottom: 10px;
}

.checkbox-item {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border: 1px dashed var(--line);
  border-radius: 10px;
}

.checkbox-item input {
  margin: 0;
}

.preview-toolbar {
  margin-bottom: 10px;
}

.schema-card {
  background: var(--bg-card);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 10px;
}

.schema-card h4 {
  margin: 0 0 8px;
  font-size: 15px;
}

.schema-card ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 4px;
}

.schema-card li {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
}

.notice {
  margin-bottom: 12px;
  display: inline-flex;
  border-radius: 999px;
  font-size: 13px;
  padding: 6px 12px;
  border: 1px solid transparent;
}

.notice.success {
  background: #def7ec;
  color: #0f5132;
  border-color: #a6e4c0;
}

.notice.error {
  background: #fff1e8;
  color: var(--warn);
  border-color: #ffd8bf;
}

.notice.info {
  background: #eef6ff;
  color: #1d4ed8;
  border-color: #cde0ff;
}

.empty {
  color: var(--text-muted);
  margin: 8px 0;
}
</style>

<template>
  <section class="panel">
    <h2>知识问答（外部库）</h2>

    <div class="quick-nav">
      <RouterLink to="/connection" class="quick-link">去连接配置</RouterLink>
      <RouterLink to="/table" class="quick-link">去表开关</RouterLink>
    </div>

    <p class="hint">请先完成连接配置与表开关配置，再发起问答。</p>

    <div v-if="notice" class="notice" :class="noticeType">{{ notice }}</div>

    <div v-if="!connectionConfigured" class="empty">外部数据库尚未配置。</div>

    <label>
      问题
      <textarea v-model="question" rows="3" placeholder="例如：按班级统计平均分" />
    </label>

    <div class="row">
      <button @click="askQuestion" :disabled="loading.query || !connectionConfigured">执行查询</button>
      <button @click="debugGenerate" :disabled="loading.query || !connectionConfigured">仅生成 SQL</button>
      <button @click="loadLogs" :disabled="loading.logs">刷新日志</button>
    </div>

    <div v-if="debugResult" class="debug-block">
      <h3>SQL 调试结果</h3>
      <p class="tag" :class="debugResult.validation_passed ? 'ok' : 'warn'">
        {{ debugResult.validation_passed ? "校验通过" : "校验失败" }}
      </p>
      <pre>{{ debugResult.sql }}</pre>
      <p v-if="debugResult.validation_message" class="muted">{{ debugResult.validation_message }}</p>
    </div>

    <div class="history">
      <h3>查询历史</h3>
      <article v-for="(item, index) in history" :key="index" class="chat-item">
        <p><strong>问：</strong> {{ item.question }}</p>
        <p><strong>SQL：</strong> <code>{{ item.sql }}</code></p>
        <p><strong>答：</strong> {{ item.answer }}</p>
        <p class="muted">{{ item.row_count }} 行 · {{ item.repaired ? "已修复" : "未修复" }}</p>

        <div v-if="item.rows.length" class="table-wrap">
          <table>
            <thead>
              <tr>
                <th v-for="col in item.columns" :key="col" class="th-cell">
                  <div class="th-title">{{ col }}</div>
                  <small
                    v-if="getFieldInference(item, col)"
                    class="infer-chip"
                    :title="getFieldInferenceTip(item, col)"
                  >
                    {{ getFieldInference(item, col).inferred_meaning }} ·
                    {{ formatConfidence(getFieldInference(item, col).confidence) }}
                  </small>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, rIdx) in item.rows.slice(0, 10)" :key="rIdx">
                <td v-for="col in item.columns" :key="`${rIdx}-${col}`">{{ row[col] }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
      <p v-if="history.length === 0" class="empty">暂无查询历史。</p>
    </div>

    <div class="history">
      <h3>执行日志</h3>
      <article v-for="log in logs" :key="log.id" class="log-item">
        <p><strong>{{ log.status }}</strong> · {{ formatTime(log.created_at) }}</p>
        <p>{{ log.question }}</p>
        <p class="muted">{{ log.duration_ms ?? "-" }} ms · {{ log.row_count ?? "-" }} 行</p>
      </article>
      <p v-if="logs.length === 0" class="empty">暂无日志。</p>
    </div>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";

import { apiRequest } from "../api/client";

const loading = reactive({
  query: false,
  logs: false,
});

const question = ref("");
const history = ref([]);
const logs = ref([]);
const debugResult = ref(null);
const connectionConfigured = ref(false);
const notice = ref("");
const noticeType = ref("info");

function setNotice(message, type = "info") {
  notice.value = message;
  noticeType.value = type;
}

function buildFieldInferenceMap(fieldInference) {
  const map = {};
  for (const item of fieldInference || []) {
    if (!item || !item.column) {
      continue;
    }
    map[item.column] = item;
  }
  return map;
}

function getFieldInference(item, column) {
  return item?.field_inference_map?.[column] || null;
}

function getFieldInferenceTip(item, column) {
  const inference = getFieldInference(item, column);
  return inference?.reason || "";
}

function formatConfidence(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) {
    return "-";
  }
  return `${Math.round(Math.max(0, Math.min(1, num)) * 100)}%`;
}

async function loadConnectionStatus() {
  try {
    const data = await apiRequest("/text2sql/connection");
    connectionConfigured.value = Boolean(data.configured);
  } catch {
    connectionConfigured.value = false;
  }
}

async function askQuestion() {
  if (!question.value.trim()) {
    setNotice("请先输入问题", "error");
    return;
  }

  loading.query = true;
  try {
    const data = await apiRequest("/text2sql/query", {
      method: "POST",
      body: JSON.stringify({ question: question.value }),
    });

    const fieldInference = Array.isArray(data.field_inference) ? data.field_inference : [];
    history.value.unshift({
      question: question.value,
      ...data,
      field_inference: fieldInference,
      field_inference_map: buildFieldInferenceMap(fieldInference),
    });

    question.value = "";
    debugResult.value = null;
    await loadLogs();
    setNotice("查询成功", "success");
  } catch (error) {
    setNotice(`查询失败：${error.message}`, "error");
  } finally {
    loading.query = false;
  }
}

async function debugGenerate() {
  if (!question.value.trim()) {
    setNotice("请先输入问题", "error");
    return;
  }

  loading.query = true;
  try {
    debugResult.value = await apiRequest("/text2sql/debug/generate", {
      method: "POST",
      body: JSON.stringify({ question: question.value }),
    });
    setNotice("SQL 生成完成", "success");
  } catch (error) {
    setNotice(`调试失败：${error.message}`, "error");
  } finally {
    loading.query = false;
  }
}

async function loadLogs() {
  loading.logs = true;
  try {
    logs.value = await apiRequest("/text2sql/logs?limit=20");
  } catch {
    logs.value = [];
  } finally {
    loading.logs = false;
  }
}

function formatTime(value) {
  return value ? new Date(value).toLocaleString() : "-";
}

onMounted(async () => {
  await Promise.all([loadConnectionStatus(), loadLogs()]);
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
  margin: 0 0 6px;
  font-size: 20px;
}

.hint {
  color: var(--text-muted);
  margin: 0 0 12px;
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

label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 14px;
  color: var(--text-muted);
}

textarea {
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
  margin: 12px 0 18px;
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

button:hover {
  background: var(--accent-strong);
}

button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.history {
  margin-top: 18px;
}

.chat-item,
.log-item,
.debug-block {
  background: var(--bg-card);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 10px;
  margin-bottom: 10px;
}

pre {
  white-space: pre-wrap;
  margin: 8px 0;
  background: #f6f8fa;
  border-radius: 8px;
  padding: 8px;
  border: 1px solid var(--line);
}

.table-wrap {
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 10px;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

th,
td {
  border-bottom: 1px solid var(--line);
  text-align: left;
  padding: 8px;
  vertical-align: top;
}

th {
  background: #f5fbff;
}

.th-cell {
  min-width: 140px;
}

.th-title {
  font-weight: 700;
}

.infer-chip {
  display: inline-block;
  margin-top: 4px;
  font-weight: 500;
  color: #176040;
  background: #def7ec;
  border: 1px solid #a6e4c0;
  border-radius: 999px;
  padding: 2px 8px;
  line-height: 1.2;
}

.notice {
  margin-bottom: 12px;
  display: inline-flex;
  border-radius: 999px;
  font-size: 13px;
  padding: 6px 12px;
  border: 1px solid transparent;
}

.notice.success,
.tag.ok {
  background: #def7ec;
  color: #0f5132;
  border-color: #a6e4c0;
}

.notice.error,
.tag.warn {
  background: #fff1e8;
  color: var(--warn);
  border-color: #ffd8bf;
}

.notice.info {
  background: #eef6ff;
  color: #1d4ed8;
  border-color: #cde0ff;
}

.tag {
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
}

.muted,
.empty {
  color: var(--text-muted);
}

.empty {
  margin: 8px 0;
}
</style>

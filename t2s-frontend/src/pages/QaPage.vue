<template>
  <section class="qa-page">
    <div class="main-panel panel">
      <header class="page-header">
        <div class="header-content">
          <h2>QA 调试</h2>
          <p>用于系统调试：查看表路由、SQL 生成、执行日志和反馈示例沉淀。</p>
        </div>
      </header>

      <div v-if="notice" class="notice" :class="noticeType">{{ notice }}</div>

      <div v-if="!connectionConfigured" class="empty-state">
        <div class="empty-icon">🔌</div>
        <p>外部数据库尚未配置，请先完成连接配置。</p>
      </div>

      <div class="query-box">
        <label>
          <span class="label-text">你的问题</span>
          <div class="textarea-wrap">
            <textarea v-model="question" rows="3" placeholder="例如：按班级统计平均分，展示前10名。可继续追问：只看本学期。" />
          </div>
        </label>

        <div class="action-row">
          <button class="btn-primary" @click="askQuestion" :disabled="loading.query || loading.debug || !connectionConfigured">
            <span>{{ loading.query ? "查询中..." : "✨ 执行智能查询" }}</span>
          </button>
          <button class="btn-outline" @click="debugGenerate" :disabled="loading.query || loading.debug || !connectionConfigured">
            {{ loading.debug ? "生成中..." : "仅生成 SQL" }}
          </button>
          <button class="btn-ghost" @click="newConversation" :disabled="loading.query || loading.debug || history.length === 0">新对话</button>
          <button class="btn-ghost" @click="loadLogs" :disabled="loading.logs">↻ 刷新日志</button>
        </div>

        <div v-if="loading.query || streamStatus || selectedTables.length || generatedSql" class="stream-block">
          <div class="stream-line"><span>阶段：</span>{{ streamStatus || "等待后端响应..." }}</div>
          <div class="stream-line"><span>候选表：</span>{{ selectedTables.join("、") || "--" }}</div>
          <pre v-if="generatedSql" class="sql-code stream-sql"><code>{{ generatedSql }}</code></pre>
        </div>
      </div>

      <div v-if="debugResult || loading.debug || debugStreamStatus || debugGeneratedSql" class="debug-block fade-in">
        <div class="debug-header">
          <h3>SQL 调试结果</h3>
          <span v-if="debugResult" class="status-badge" :class="debugResult.validation_passed ? 'ok' : 'warn'">
            {{ debugResult.validation_passed ? "校验通过" : "校验失败" }}
          </span>
        </div>
        <p v-if="debugStreamStatus" class="route-msg">阶段：{{ debugStreamStatus }}</p>
        <p v-if="debugSelectedTables.length" class="route-msg">候选表：{{ debugSelectedTables.join("、") }}</p>
        <pre class="sql-code debug-sql-code"><code>{{ debugGeneratedSql || debugResult?.sql || "--" }}</code></pre>
        <p v-if="debugResult?.validation_message" class="debug-msg">{{ debugResult.validation_message }}</p>
        <p v-if="Array.isArray(debugResult?.route_tables) && debugResult.route_tables.length" class="route-msg">
          路由（{{ debugResult.route_mode || "single" }}）: {{ debugResult.route_tables.join("、") }}
        </p>
      </div>

      <div class="history-section">
        <h3 class="section-title">查询历史</h3>
        <div class="chat-container">
          <article v-for="(item, index) in history" :key="item.id || index" class="chat-bubble fade-in">
            <div class="chat-row user-row">
              <div class="avatar user-avatar">Q</div>
              <div class="chat-content user-msg">{{ item.question }}</div>
            </div>

            <div class="chat-row bot-row">
              <div class="avatar bot-avatar">A</div>
              <div class="chat-content bot-msg">
                <template v-if="item.status === 'streaming'">
                  <div class="stream-line">{{ item.progressStatus || "正在生成 SQL..." }}</div>
                  <div v-if="item.selected_tables.length" class="meta-info">候选表：{{ item.selected_tables.join("、") }}</div>
                  <div v-if="item.generated_sql" class="sql-wrapper mt-3">
                    <div class="sql-header">Generated SQL</div>
                    <pre class="sql-code"><code>{{ item.generated_sql }}</code></pre>
                  </div>
                  <div v-if="item.summaryStreaming || item.answer" class="answer-text streaming-answer">
                    {{ item.answer || "正在生成结果总结..." }}
                  </div>
                </template>

                <template v-else-if="item.status === 'clarify'">
                  <div class="clarification-box">{{ item.clarification || "当前问题需要补充更多条件。" }}</div>
                </template>

                <template v-else-if="item.status === 'error'">
                  <div class="error-box">{{ item.error_message || "查询失败" }}</div>
                </template>

                <template v-else>
                  <div class="sql-wrapper">
                    <div class="sql-header">Generated SQL</div>
                    <pre class="sql-code"><code>{{ item.sql || "--" }}</code></pre>
                  </div>

                  <div class="answer-text">{{ item.answer || "--" }}</div>
                  <div class="meta-info">
                    {{ item.row_count }} 行数据 · {{ item.repaired ? "已尝试修复SQL" : "原生SQL未修复" }}
                    <span v-if="item.few_shot_reused"> · 命中已审核 SQL</span>
                    <span v-if="item.log_id"> · 日志 #{{ item.log_id }}</span>
                  </div>

                  <div v-if="Array.isArray(item.rows) && item.rows.length" class="result-table-wrap mt-3">
                    <table class="result-table">
                      <thead>
                        <tr>
                          <th v-for="col in columnsOf(item)" :key="col">
                            <div class="th-content">{{ col }}</div>
                            <div v-if="getFieldInference(item, col)" class="infer-tag" :title="getFieldInferenceTip(item, col)">
                              {{ getFieldInference(item, col).inferred_meaning }} ({{ formatConfidence(getFieldInference(item, col).confidence) }})
                            </div>
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="(row, rIdx) in item.rows.slice(0, 10)" :key="rIdx">
                          <td v-for="col in columnsOf(item)" :key="`${rIdx}-${col}`">{{ formatCellValue(row[col]) }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <div v-if="item.log_id" class="feedback-row">
                    <span class="feedback-label">满意度（5 星仅作为待审核的 few-shot 候选）</span>
                    <div class="star-row">
                      <button
                        v-for="score in [1, 2, 3, 4, 5]"
                        :key="score"
                        class="star-btn"
                        :class="{ active: item.feedbackScore >= score }"
                        :disabled="item.feedbackSubmitting || item.feedbackSubmitted"
                        @click="submitFeedback(item, score)"
                      >
                        ★
                      </button>
                    </div>
                    <span v-if="item.feedbackSubmitted" class="feedback-done">已记录</span>
                  </div>
                </template>
              </div>
            </div>
          </article>
          <div v-if="history.length === 0" class="empty-state py-8">暂无查询历史，开始提问吧！</div>
        </div>
      </div>
    </div>

    <aside class="side-panel panel">
      <h3 class="section-title">执行日志</h3>
      <div class="log-list">
        <article v-for="log in logs" :key="log.id" class="log-item">
          <div class="log-header">
            <span class="log-status" :class="String(log.status || '').toLowerCase()">{{ log.status }}</span>
            <span class="log-time">{{ formatTime(log.created_at) }}</span>
          </div>
          <p class="log-q">{{ log.question }}</p>
          <div class="log-meta">
            耗时: {{ log.duration_ms ?? "-" }} ms | 结果: {{ log.row_count ?? "-" }} 行 | 评分: {{ log.feedback_score ?? "-" }}
          </div>
        </article>
        <div v-if="logs.length === 0" class="empty-state">暂无日志。</div>
      </div>
    </aside>
  </section>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { apiRequest, streamRequest } from "../api/client";

const loading = reactive({ query: false, debug: false, logs: false });
const question = ref("");
const history = ref([]);
const logs = ref([]);
const debugResult = ref(null);
const connectionConfigured = ref(false);
const notice = ref("");
const noticeType = ref("info");

const streamStopper = ref(null);
const streamStatus = ref("");
const selectedTables = ref([]);
const generatedSql = ref("");
const debugStreamStatus = ref("");
const debugSelectedTables = ref([]);
const debugGeneratedSql = ref("");

let turnSeq = 0;

function setNotice(message, type = "info") {
  notice.value = message;
  noticeType.value = type;
}

function stopActiveStream() {
  if (!streamStopper.value) return;
  streamStopper.value();
  streamStopper.value = null;
}

function buildFieldInferenceMap(fieldInference) {
  const map = {};
  for (const item of fieldInference || []) {
    if (!item || !item.column) continue;
    map[item.column] = item;
  }
  return map;
}

function columnsOf(item) {
  if (Array.isArray(item?.columns) && item.columns.length) return item.columns;
  const firstRow = Array.isArray(item?.rows) ? item.rows[0] : null;
  return firstRow ? Object.keys(firstRow) : [];
}

function formatCellValue(value) {
  if (value === null || value === undefined) return "空值";
  if (typeof value === "string" && ["null", "none"].includes(value.trim().toLowerCase())) {
    return "空值";
  }
  return value;
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
  if (!Number.isFinite(num)) return "-";
  return `${Math.round(Math.max(0, Math.min(1, num)) * 100)}%`;
}

function normalizeQueryResult(questionText, data, base = {}) {
  // 优先展示解码后的中文行（decoded_rows），缺省回退原始码值 rows。
  const rows = Array.isArray(data?.decoded_rows) && data.decoded_rows.length
    ? data.decoded_rows
    : (Array.isArray(data?.rows) ? data.rows : []);
  const columns = Array.isArray(data?.columns) ? data.columns : columnsOf({ rows });
  const fieldInference = Array.isArray(data?.field_inference) ? data.field_inference : [];
  const clarification = String(data?.clarification || "");
  return {
    ...base,
    question: questionText,
    status: clarification ? "clarify" : "done",
    sql: data?.sql || base.sql || base.generated_sql || "",
    generated_sql: base.generated_sql || data?.sql || "",
    columns,
    rows,
    answer: data?.answer || base.answer || "",
    summaryStreaming: false,
    row_count: Number(data?.row_count ?? rows.length),
    repaired: Boolean(data?.repaired),
    few_shot_reused: Boolean(data?.few_shot_reused ?? base.few_shot_reused),
    few_shot_match_score: data?.few_shot_match_score ?? base.few_shot_match_score ?? null,
    few_shot_log_id: data?.few_shot_log_id ?? base.few_shot_log_id ?? null,
    field_inference: fieldInference,
    field_inference_map: buildFieldInferenceMap(fieldInference),
    clarification,
    log_id: data?.log_id ?? base.log_id ?? null,
    error_message: "",
    feedbackScore: base.feedbackScore || 0,
    feedbackSubmitting: false,
    feedbackSubmitted: false,
  };
}

function buildConversationHistory() {
  return history.value
    .slice()
    .reverse()
    .filter((item) => item.status === "done" && item.sql)
    .slice(-20)
    .map((item) => ({ question: item.question, sql: item.sql, answer: item.answer || "" }));
}

function newConversation() {
  stopActiveStream();
  history.value = [];
  streamStatus.value = "";
  selectedTables.value = [];
  generatedSql.value = "";
  debugResult.value = null;
  setNotice("已开始新对话。", "info");
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
  const q = question.value.trim();
  if (!q) {
    setNotice("请先输入问题", "error");
    return;
  }
  if (loading.query || loading.debug) return;

  const activeTurn = {
    id: `turn-${Date.now()}-${turnSeq++}`,
    question: q,
    status: "streaming",
    progressStatus: "正在启动查询...",
    selected_tables: [],
    generated_sql: "",
    sql: "",
    columns: [],
    rows: [],
    answer: "",
    summaryStreaming: false,
    row_count: 0,
    repaired: false,
    few_shot_reused: false,
    few_shot_match_score: null,
    few_shot_log_id: null,
    field_inference: [],
    field_inference_map: {},
    clarification: "",
    log_id: null,
    error_message: "",
    feedbackScore: 0,
    feedbackSubmitting: false,
    feedbackSubmitted: false,
  };

  const payload = { question: q, history: buildConversationHistory() };
  history.value.unshift(activeTurn);
  question.value = "";
  debugResult.value = null;
  streamStatus.value = "正在启动查询...";
  selectedTables.value = [];
  generatedSql.value = "";
  loading.query = true;
  stopActiveStream();

  try {
    await new Promise((resolve, reject) => {
      let finished = false;
      streamStopper.value = streamRequest("/text2sql/query/stream", payload, {
        onStatus: (data) => {
          const message = data?.message || "";
          streamStatus.value = message;
          activeTurn.progressStatus = message;
          if (data?.step === "summarizing") {
            activeTurn.summaryStreaming = true;
          }
        },
        onSelectedTables: (data) => {
          const tables = Array.isArray(data?.selected_tables) ? data.selected_tables : [];
          selectedTables.value = tables;
          activeTurn.selected_tables = tables;
        },
        onGeneratedSql: (data) => {
          const sql = data?.sql || data?.final_sql || "";
          generatedSql.value = sql;
          activeTurn.generated_sql = sql;
          if (!activeTurn.sql) activeTurn.sql = sql;
          activeTurn.few_shot_reused = Boolean(data?.few_shot_reused);
          activeTurn.few_shot_match_score = data?.few_shot_match_score ?? null;
          activeTurn.few_shot_log_id = data?.few_shot_log_id ?? null;
        },
        onSqlResult: (data) => {
          activeTurn.sql = data?.sql || activeTurn.generated_sql || activeTurn.sql;
          activeTurn.columns = Array.isArray(data?.columns) ? data.columns : [];
          activeTurn.rows = Array.isArray(data?.decoded_rows) && data.decoded_rows.length
            ? data.decoded_rows
            : (Array.isArray(data?.rows) ? data.rows : []);
          activeTurn.row_count = Number(data?.row_count ?? activeTurn.rows.length);
          activeTurn.repaired = Boolean(data?.repaired);
          activeTurn.few_shot_reused = Boolean(data?.few_shot_reused ?? activeTurn.few_shot_reused);
          activeTurn.few_shot_match_score = data?.few_shot_match_score ?? activeTurn.few_shot_match_score;
          activeTurn.few_shot_log_id = data?.few_shot_log_id ?? activeTurn.few_shot_log_id;
          activeTurn.field_inference = Array.isArray(data?.field_inference) ? data.field_inference : [];
          activeTurn.field_inference_map = buildFieldInferenceMap(activeTurn.field_inference);
        },
        onAnswerDelta: (content) => {
          activeTurn.summaryStreaming = true;
          if (content) activeTurn.answer += content;
        },
        onDone: (data) => {
          if (finished) return;
          finished = true;
          Object.assign(activeTurn, normalizeQueryResult(q, data, activeTurn));
          streamStopper.value = null;
          resolve();
        },
        onError: (error) => {
          if (finished) return;
          finished = true;
          activeTurn.status = "error";
          activeTurn.error_message = error?.message || "查询失败";
          activeTurn.summaryStreaming = false;
          streamStopper.value = null;
          reject(new Error(activeTurn.error_message));
        },
      });
    });

    await loadLogs();
    setNotice(activeTurn.status === "clarify" ? "需要补充查询条件。" : "查询成功", activeTurn.status === "clarify" ? "info" : "success");
  } catch (error) {
    setNotice(`查询失败：${error.message}`, "error");
  } finally {
    loading.query = false;
  }
}

async function debugGenerate() {
  const q = question.value.trim();
  if (!q) {
    setNotice("请先输入问题", "error");
    return;
  }
  if (loading.query || loading.debug) return;

  loading.debug = true;
  debugResult.value = null;
  debugStreamStatus.value = "正在启动 SQL 生成...";
  debugSelectedTables.value = [];
  debugGeneratedSql.value = "";
  stopActiveStream();

  try {
    await new Promise((resolve, reject) => {
      let finished = false;
      streamStopper.value = streamRequest("/text2sql/debug/generate/stream", { question: q, history: buildConversationHistory() }, {
        onStatus: (data) => {
          debugStreamStatus.value = data?.message || "";
        },
        onSelectedTables: (data) => {
          debugSelectedTables.value = Array.isArray(data?.selected_tables) ? data.selected_tables : [];
        },
        onGeneratedSql: (data) => {
          debugGeneratedSql.value = data?.sql || data?.final_sql || "";
        },
        onDone: (data) => {
          if (finished) return;
          finished = true;
          debugResult.value = data;
          streamStopper.value = null;
          resolve();
        },
        onError: (error) => {
          if (finished) return;
          finished = true;
          streamStopper.value = null;
          reject(new Error(error?.message || "调试失败"));
        },
      });
    });
    setNotice("SQL 生成完成", "success");
  } catch (error) {
    setNotice(`调试失败：${error.message}`, "error");
  } finally {
    loading.debug = false;
  }
}

async function submitFeedback(item, score) {
  if (!item?.log_id || !score) return;
  item.feedbackSubmitting = true;
  try {
    await apiRequest("/text2sql/query/feedback", {
      method: "POST",
      body: JSON.stringify({
        log_id: item.log_id,
        score,
      }),
    });
    item.feedbackScore = score;
    item.feedbackSubmitted = true;
    await loadLogs();
    setNotice(score >= 5 ? "反馈已记录，该问答已进入 few-shot 待审核列表。" : "反馈已记录。", "success");
  } catch (error) {
    setNotice(`反馈提交失败：${error.message}`, "error");
  } finally {
    item.feedbackSubmitting = false;
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

onBeforeUnmount(() => {
  stopActiveStream();
});
</script>

<style scoped>
.qa-page { display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: 14px; align-items: start; }
@media (max-width: 1024px) { .qa-page { grid-template-columns: 1fr; } }

.panel { background: rgba(255, 255, 255, 0.58); border: 1px solid var(--line); border-radius: 8px; box-shadow: none; padding: 18px; }
.main-panel { min-height: 80vh; background: transparent; border: none; border-radius: 0; padding: 0; }
.side-panel { position: sticky; top: 86px; max-height: calc(100vh - 104px); overflow-y: auto; background: rgba(255, 255, 255, 0.72); }

.page-header { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px; margin-bottom: 18px; padding-bottom: 18px; border-bottom: 1px solid var(--line); }
h2 { margin: 0 0 8px; font-size: clamp(24px, 2.7vw, 34px); line-height: 1.1; font-weight: 720; color: var(--text-main); letter-spacing: 0; }
.header-content p { margin: 0; color: var(--text-muted); font-size: 14px; }
.query-box { background: rgba(255, 255, 255, 0.64); border-radius: 8px; padding: 16px; border: 1px solid var(--line); margin-bottom: 18px; box-shadow: none; }
.label-text { font-weight: 600; margin-bottom: 8px; display: inline-block; color: var(--text-main); }
.textarea-wrap { position: relative; }
textarea { width: 100%; border-radius: 8px; padding: 14px; font-size: 15px; resize: vertical; color: var(--text-main); }

button { font-weight: 620; padding: 10px 14px; cursor: pointer; }
button:active:not(:disabled) { transform: scale(0.98); }
button:disabled { opacity: 0.6; cursor: not-allowed; }
.action-row { display: flex; gap: 10px; margin-top: 14px; flex-wrap: wrap; }

.stream-block {
  margin-top: 16px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface-2);
}
.stream-line { color: var(--text-muted); font-size: 13px; line-height: 1.7; }
.stream-line span { color: var(--text-main); font-weight: 600; }
.stream-sql { margin-top: 8px; border-radius: 8px; background: #0f172a; }

.section-title { font-size: 15px; font-weight: 690; margin: 0 0 16px; color: var(--text-main); }

.chat-container { display: flex; flex-direction: column; gap: 24px; }
.chat-row { display: flex; gap: 16px; margin-bottom: 16px; align-items: flex-start; }
.avatar { width: 32px; height: 32px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-weight: 690; flex-shrink: 0; color: #ffffff; box-shadow: none; font-size: 12px; }
.user-avatar { background: #111111; }
.bot-avatar { background: #6f6f66; }

.chat-content { padding: 14px; border-radius: 8px; max-width: 100%; box-shadow: none; line-height: 1.5; font-size: 15px; }
.user-msg { background: var(--surface-2); color: var(--text-main); }
.bot-msg { background: rgba(255, 255, 255, 0.66); border: 1px solid var(--line); width: 100%; overflow: hidden; }

.sql-wrapper { background: #111111; border-radius: 8px; overflow: hidden; margin-bottom: 16px; }
.sql-header { background: #1d1d1b; color: #b7b7ae; font-size: 12px; padding: 6px 12px; font-family: monospace; border-bottom: 1px solid rgba(255,255,255,0.1); }
.sql-code { margin: 0; padding: 16px; color: #f8fafc; font-family: monospace; font-size: 13px; white-space: pre-wrap; word-break: break-word; }

.answer-text { font-weight: 500; color: var(--text-main); margin-bottom: 8px; white-space: pre-wrap; }
.meta-info { font-size: 12px; color: var(--text-muted); }
.clarification-box { background: #fffbeb; color: #92400e; border: 1px solid #fde68a; border-radius: 10px; padding: 12px; }
.error-box { background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; border-radius: 10px; padding: 12px; }

.result-table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; }
.result-table { width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; }
.result-table th, .result-table td { padding: 10px 14px; border-bottom: 1px solid var(--line); }
.result-table th { background: var(--surface-2); font-weight: 600; color: var(--text-muted); }
.result-table tr:hover td { background: rgba(var(--accent-rgb), 0.05); }
.infer-tag { display: inline-block; background: #d1fae5; color: #065f46; font-size: 11px; padding: 2px 6px; border-radius: 4px; margin-top: 4px; font-weight: 500; }

.feedback-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--line);
}
.feedback-label { color: var(--text-muted); font-size: 12px; }
.star-row { display: flex; gap: 4px; }
.star-btn {
  padding: 2px 4px;
  background: transparent;
  color: #cbd5e1;
  font-size: 18px;
  line-height: 1;
}
.star-btn.active,
.star-btn:hover:not(:disabled) { color: #f59e0b; }
.feedback-done { color: var(--success); font-size: 12px; }

.debug-block { background: rgba(255, 255, 255, 0.66); border: 1px solid var(--line); border-radius: 8px; padding: 16px; margin-bottom: 18px; border-left: 3px solid var(--text-main); }
.debug-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.debug-header h3 { margin: 0; font-size: 16px; }
.status-badge { font-size: 12px; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
.status-badge.ok { background: rgba(16, 185, 129, 0.2); color: var(--success); }
.status-badge.warn { background: rgba(239, 68, 68, 0.2); color: var(--error); }
.debug-sql-code { background: #0f172a; color: #f8fafc; border: 1px solid #1e293b; border-radius: 8px; opacity: 1; }
.debug-sql-code code { color: inherit; opacity: 1; }
.debug-msg { color: var(--error); font-size: 13px; margin-top: 8px; }
.route-msg { color: var(--text-muted); font-size: 14px; margin-top: 8px; }

.log-list { display: flex; flex-direction: column; gap: 12px; }
.log-item { background: rgba(255, 255, 255, 0.66); padding: 12px; border-radius: 8px; border: 1px solid var(--line); font-size: 13px; }
.log-header { display: flex; justify-content: space-between; margin-bottom: 6px; gap: 8px; }
.log-status { font-weight: bold; }
.log-status.success { color: var(--success); }
.log-status.error { color: var(--error); }
.log-time { color: var(--text-muted); font-size: 12px; }
.log-q { margin: 0 0 6px; font-weight: 500; color: var(--text-main); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.log-meta { color: var(--text-muted); font-size: 12px; }

.empty-state { text-align: center; color: var(--text-muted); padding: 32px 0; }
.empty-icon { font-size: 32px; margin-bottom: 8px; opacity: 0.5; }
.py-8 { padding-top: 32px; padding-bottom: 32px; } .mt-3 { margin-top: 12px; }

.notice { padding: 12px 16px; border-radius: 8px; font-size: 13px; font-weight: 560; margin-bottom: 18px; }
.notice.success { background: rgba(16, 185, 129, 0.1); color: var(--success); border: 1px solid rgba(16, 185, 129, 0.2); }
.notice.error { background: rgba(239, 68, 68, 0.1); color: var(--error); border: 1px solid rgba(239, 68, 68, 0.2); }
.notice.info { background: #eff6ff; color: #1e40af; border: 1px solid #bfdbfe; }
</style>

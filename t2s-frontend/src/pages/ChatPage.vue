<template>
  <section class="chat-page">
    <div class="chat-shell panel">
      <header class="page-header">
        <div>
          <h2>{{ activeMode === "document" ? "文档问答" : "数据问答" }}</h2>
          <p>{{ activeMode === "document" ? "基于文档知识与高基表回答问题" : "基于学校数据库查询" }}</p>
        </div>

        <div class="page-actions">
          <span class="current-user">{{ currentUserName }}</span>
          <div class="mode-switch" aria-label="问答模式">
            <button
              type="button"
              :class="{ active: activeMode === 'document' }"
              :disabled="loading.query"
              @click="switchMode('document')"
            >
              文档问答
            </button>
            <button
              type="button"
              :class="{ active: activeMode === 'data' }"
              :disabled="loading.query"
              @click="switchMode('data')"
            >
              数据问答
            </button>
          </div>
          <RouterLink v-if="isAdmin" to="/admin" class="header-link">进入后台管理</RouterLink>
          <a class="header-link" :href="ssoLogoutUrl">退出登录</a>
        </div>
      </header>

      <div v-if="notice" class="notice" :class="noticeType">{{ notice }}</div>

      <div v-if="activeMode === 'data' && !connectionConfigured" class="empty-state">
        <div class="empty-title">外部数据库尚未配置</div>
        <p>请联系管理员完成数据连接配置。</p>
      </div>

      <div ref="conversationRef" class="conversation">
        <div v-if="messages.length === 0 && canUseCurrentMode" class="welcome">
          <h3>{{ activeMode === "document" ? "想查哪份资料或表格？" : "今天想查什么数据？" }}</h3>
        </div>

        <article v-for="item in messages" :key="item.id" class="turn">
          <div class="bubble-row user-row">
            <div class="avatar user-avatar">Q</div>
            <div class="bubble user-bubble">{{ item.question }}</div>
          </div>

          <div class="bubble-row assistant-row">
            <div class="avatar assistant-avatar">A</div>
            <div class="bubble assistant-bubble">
              <template v-if="item.status === 'streaming'">
                <div class="progress-line">{{ item.progressStatus || "正在查询..." }}</div>
                <div v-if="item.summaryStreaming || item.answer" class="answer-text streaming-answer">
                  {{ item.answer || "正在生成回答..." }}
                </div>
              </template>

              <template v-else-if="item.status === 'clarify'">
                <div class="clarification-box">{{ item.clarification || "当前问题需要补充更多条件。" }}</div>
              </template>

              <template v-else-if="item.status === 'error'">
                <div class="error-box">{{ item.error_message || "查询失败" }}</div>
              </template>

              <template v-else>
                <div class="answer-text">{{ item.answer || "没有生成可展示的回答。" }}</div>

                <template v-if="item.mode === 'data'">
                  <div class="meta-info">
                    {{ item.row_count }} 行结果
                    <span v-if="item.repaired"> · 已自动修复 SQL</span>
                  </div>

                  <details v-if="Array.isArray(item.rows) && item.rows.length" class="data-preview" open>
                    <summary>查看数据明细（前 10 行）</summary>
                    <div class="result-table-wrap">
                      <table class="result-table">
                        <thead>
                          <tr>
                            <th v-for="col in columnsOf(item)" :key="col">{{ col }}</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr v-for="(row, rIdx) in item.rows.slice(0, 10)" :key="rIdx">
                            <td v-for="col in columnsOf(item)" :key="`${rIdx}-${col}`">{{ formatCellValue(row[col]) }}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </details>

                  <div v-if="item.log_id" class="feedback-row">
                    <span>这次回答有帮助吗？</span>
                    <div class="star-row" aria-label="回答评分">
                      <button
                        v-for="score in [1, 2, 3, 4, 5]"
                        :key="score"
                        type="button"
                        class="star-btn"
                        :class="{ active: item.feedbackScore >= score }"
                        :disabled="item.feedbackSubmitting || item.feedbackSubmitted"
                        :title="`${score} 星`"
                        @click="submitFeedback(item, score)"
                      >
                        ★
                      </button>
                    </div>
                    <span v-if="item.feedbackSubmitted" class="feedback-done">已记录</span>
                  </div>
                </template>

                <details v-if="item.mode === 'document' && item.evidences.length" class="evidence-list">
                  <summary>查看引用依据（{{ item.evidences.length }} 条）</summary>
                  <article v-for="evidence in item.evidences" :key="evidence.chunk_id || evidence.text" class="evidence-item">
                    <div class="meta-info">
                      KB #{{ evidence.kb_id }}
                      <span v-if="evidence.file_id"> · 文件 #{{ evidence.file_id }}</span>
                      <span v-if="Number.isFinite(Number(evidence.score))"> · {{ formatScore(evidence.score) }}</span>
                    </div>
                    <pre>{{ evidence.text }}</pre>
                  </article>
                </details>
              </template>
            </div>
          </div>
        </article>
      </div>

      <form class="composer" @submit.prevent="sendQuestion">
        <textarea
          v-model="question"
          rows="3"
          :disabled="loading.query || !canUseCurrentMode"
          :placeholder="activeMode === 'document' ? '输入你的文档或表格问题，按 Enter 发送' : '输入你的数据问题，按 Enter 发送'"
          @keydown.enter.exact.prevent="sendQuestion"
        />
        <div class="composer-actions">
          <button type="button" class="btn-ghost" :disabled="loading.query || messages.length === 0" @click="newConversation">
            新对话
          </button>
          <button class="btn-primary" :disabled="loading.query || !canUseCurrentMode">
            {{ loading.query ? "查询中..." : "发送" }}
          </button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup>
import { computed, inject, nextTick, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";
import { API_BASE, apiRequest, streamRequest } from "../api/client";

const userState = inject("userState");
const ssoLogoutUrl = `${API_BASE}/auth/logout/sso`;
const isAdmin = computed(() => userState?.user?.permissions?.includes("admin:access"));
const currentUserName = computed(() => userState?.user?.name || "已登录用户");

const loading = reactive({ query: false });
const activeMode = ref("document");
const question = ref("");
const messages = ref([]);
const connectionConfigured = ref(false);
const notice = ref("");
const noticeType = ref("info");
const streamStopper = ref(null);
const conversationRef = ref(null);

let turnSeq = 0;

const canUseCurrentMode = computed(() => activeMode.value === "document" || connectionConfigured.value);

function setNotice(message, type = "info") {
  notice.value = message;
  noticeType.value = type;
}

function switchMode(mode) {
  if (loading.query || activeMode.value === mode) return;
  stopActiveStream();
  activeMode.value = mode;
  messages.value = [];
  setNotice(mode === "document" ? "已切换到文档问答。" : "已切换到数据问答。", "info");
}

function stopActiveStream() {
  if (!streamStopper.value) return;
  streamStopper.value();
  streamStopper.value = null;
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

function formatScore(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "-";
  return `相关度 ${Math.round(num * 100)}%`;
}

function normalizeDataResult(questionText, data, base = {}) {
  const rows = Array.isArray(data?.decoded_rows) && data.decoded_rows.length
    ? data.decoded_rows
    : (Array.isArray(data?.rows) ? data.rows : []);
  const columns = Array.isArray(data?.columns) ? data.columns : columnsOf({ rows });
  const clarification = String(data?.clarification || "");
  return {
    ...base,
    mode: "data",
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
    clarification,
    log_id: data?.log_id ?? base.log_id ?? null,
    error_message: "",
    evidences: [],
    feedbackScore: base.feedbackScore || 0,
    feedbackSubmitting: false,
    feedbackSubmitted: false,
  };
}

function normalizeDocumentResult(questionText, data, base = {}) {
  return {
    ...base,
    mode: "document",
    question: questionText,
    status: "done",
    answer: data?.answer || base.answer || "",
    evidences: Array.isArray(data?.evidences) ? data.evidences : [],
    summaryStreaming: false,
    error_message: "",
  };
}

function buildDataHistory() {
  return messages.value
    .filter((item) => item.mode === "data" && item.status === "done" && item.sql)
    .slice(-20)
    .map((item) => ({ question: item.question, sql: item.sql, answer: item.answer || "" }));
}

function buildDocumentHistory() {
  return messages.value
    .filter((item) => item.mode === "document" && item.status === "done")
    .slice(-20)
    .map((item) => ({ question: item.question, answer: item.answer || "" }));
}

async function scrollToBottom() {
  await nextTick();
  const el = conversationRef.value;
  if (el) el.scrollTop = el.scrollHeight;
}

function newConversation() {
  stopActiveStream();
  messages.value = [];
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

function createActiveTurn(q) {
  return {
    id: `chat-${Date.now()}-${turnSeq++}`,
    mode: activeMode.value,
    question: q,
    status: "streaming",
    progressStatus: "正在启动查询...",
    selected_tables: [],
    generated_sql: "",
    sql: "",
    columns: [],
    rows: [],
    answer: "",
    evidences: [],
    summaryStreaming: false,
    row_count: 0,
    repaired: false,
    clarification: "",
    log_id: null,
    error_message: "",
    feedbackScore: 0,
    feedbackSubmitting: false,
    feedbackSubmitted: false,
  };
}

async function sendQuestion() {
  const q = question.value.trim();
  if (!q) {
    setNotice("请先输入问题", "error");
    return;
  }
  if (loading.query) return;
  if (!canUseCurrentMode.value) {
    setNotice("当前模式尚不可用，请先完成配置。", "error");
    return;
  }

  const activeTurn = createActiveTurn(q);
  messages.value.push(activeTurn);
  question.value = "";
  loading.query = true;
  stopActiveStream();
  await scrollToBottom();

  try {
    if (activeMode.value === "data") {
      await sendDataQuestion(q, activeTurn);
    } else {
      await sendDocumentQuestion(q, activeTurn);
    }
    await scrollToBottom();
    setNotice(activeTurn.status === "clarify" ? "需要补充查询条件。" : "查询成功", activeTurn.status === "clarify" ? "info" : "success");
  } catch (error) {
    setNotice(`查询失败：${error.message}`, "error");
  } finally {
    loading.query = false;
  }
}

async function sendDataQuestion(q, activeTurn) {
  const payload = { question: q, history: buildDataHistory() };
  await new Promise((resolve, reject) => {
    let finished = false;
    streamStopper.value = streamRequest("/text2sql/query/stream", payload, {
      onStatus: (data) => {
        activeTurn.progressStatus = data?.message || "";
        if (data?.step === "summarizing") activeTurn.summaryStreaming = true;
        scrollToBottom();
      },
      onSelectedTables: (data) => {
        activeTurn.selected_tables = Array.isArray(data?.selected_tables) ? data.selected_tables : [];
      },
      onGeneratedSql: (data) => {
        const sql = data?.sql || data?.final_sql || "";
        activeTurn.generated_sql = sql;
        if (!activeTurn.sql) activeTurn.sql = sql;
      },
      onSqlResult: (data) => {
        activeTurn.sql = data?.sql || activeTurn.generated_sql || activeTurn.sql;
        activeTurn.columns = Array.isArray(data?.columns) ? data.columns : [];
        activeTurn.rows = Array.isArray(data?.decoded_rows) && data.decoded_rows.length
          ? data.decoded_rows
          : (Array.isArray(data?.rows) ? data.rows : []);
        activeTurn.row_count = Number(data?.row_count ?? activeTurn.rows.length);
        activeTurn.repaired = Boolean(data?.repaired);
      },
      onAnswerDelta: (content) => {
        activeTurn.summaryStreaming = true;
        if (content) {
          activeTurn.answer += content;
          scrollToBottom();
        }
      },
      onDone: (data) => {
        if (finished) return;
        finished = true;
        Object.assign(activeTurn, normalizeDataResult(q, data, activeTurn));
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
}

async function sendDocumentQuestion(q, activeTurn) {
  const payload = { question: q, history: buildDocumentHistory() };
  await new Promise((resolve, reject) => {
    let finished = false;
    streamStopper.value = streamRequest("/document-qa/query/stream", payload, {
      onStatus: (data) => {
        activeTurn.progressStatus = data?.message || "";
        scrollToBottom();
      },
      onDone: (data) => {
        if (finished) return;
        finished = true;
        Object.assign(activeTurn, normalizeDocumentResult(q, data, activeTurn));
        streamStopper.value = null;
        resolve();
      },
      onError: (error) => {
        if (finished) return;
        finished = true;
        activeTurn.status = "error";
        activeTurn.error_message = error?.message || "文档问答失败";
        streamStopper.value = null;
        reject(new Error(activeTurn.error_message));
      },
    });
  });
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
        question: item.question,
        sql: item.sql || item.generated_sql || "",
        answer: item.answer || "",
        selected_tables: item.selected_tables || [],
      }),
    });
    item.feedbackScore = score;
    item.feedbackSubmitted = true;
    setNotice(score >= 5 ? "反馈已记录，满分回答将回流到 few-shot 知识库。" : "反馈已记录。", "success");
  } catch (error) {
    setNotice(`反馈提交失败：${error.message}`, "error");
  } finally {
    item.feedbackSubmitting = false;
  }
}

onMounted(async () => {
  await loadConnectionStatus();
});

onBeforeUnmount(() => {
  stopActiveStream();
});
</script>

<style scoped>
.chat-page {
  min-height: 100dvh;
  background:
    radial-gradient(circle at 50% -10%, rgba(255, 255, 255, 0.98), transparent 30rem),
    linear-gradient(180deg, #fbfbf8 0%, #f4f4f0 100%);
  color: var(--text-main);
}

.panel {
  background: transparent;
  border: none;
  border-radius: 0;
  box-shadow: none;
}

.chat-shell {
  min-height: 100dvh;
  display: grid;
  grid-template-rows: auto auto 1fr auto;
  overflow: hidden;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  padding: 18px clamp(16px, 4vw, 42px);
  border-bottom: 1px solid var(--line);
  background: rgba(247, 247, 244, 0.86);
  backdrop-filter: blur(18px);
}

h2 {
  margin: 0 0 8px;
  font-size: clamp(22px, 2.6vw, 34px);
  line-height: 1.08;
  color: var(--text-main);
  font-weight: 730;
  letter-spacing: 0;
}

.page-header p {
  margin: 0;
  color: var(--text-muted);
  font-size: 14px;
}

.page-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.current-user {
  color: var(--text-muted);
  font-size: 13px;
}

.header-link {
  min-height: 34px;
  display: inline-flex;
  align-items: center;
  padding: 0 12px;
  border: 1px solid var(--line);
  border-radius: 7px;
  background: rgba(255, 255, 255, 0.78);
  color: var(--text-main);
  font-size: 13px;
  font-weight: 650;
  text-decoration: none;
}

.header-link:hover {
  border-color: rgba(var(--accent-rgb), 0.24);
  background: var(--accent-light);
  color: var(--accent);
}

.mode-switch {
  display: inline-flex;
  gap: 4px;
  padding: 4px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.7);
}

.mode-switch button {
  min-width: 92px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-muted);
}

.mode-switch button.active {
  background: #111111;
  color: #ffffff;
}

.notice {
  justify-self: center;
  width: min(960px, calc(100% - 32px));
  margin: 16px 0 0;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 560;
}

.notice.success {
  background: var(--success-light);
  color: var(--success);
  border: 1px solid rgba(4, 120, 87, 0.16);
}

.notice.error {
  background: var(--error-light);
  color: var(--error);
  border: 1px solid rgba(180, 35, 24, 0.16);
}

.notice.info {
  background: var(--info-light);
  color: var(--info);
  border: 1px solid rgba(29, 78, 216, 0.16);
}

.conversation {
  width: 100%;
  max-width: 960px;
  margin: 0 auto;
  overflow-y: auto;
  padding: 28px 16px 30px;
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.welcome,
.empty-state {
  text-align: center;
  color: var(--text-muted);
  padding: 68px 16px;
}

.welcome h3,
.empty-title {
  margin: 0 0 8px;
  color: var(--text-main);
  font-size: clamp(24px, 3vw, 42px);
  line-height: 1.08;
  font-weight: 730;
  letter-spacing: 0;
}

.turn {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.bubble-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.user-row {
  justify-content: flex-end;
}

.assistant-row {
  justify-content: flex-start;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: #fff;
  font-size: 12px;
  font-weight: 690;
}

.user-avatar {
  order: 2;
  background: #111111;
}

.assistant-avatar {
  background: #6f6f66;
}

.bubble {
  max-width: min(760px, calc(100% - 48px));
  padding: 14px 16px;
  border-radius: 10px;
  line-height: 1.6;
  font-size: 15px;
}

.user-bubble {
  color: var(--text-main);
  background: var(--surface-2);
  border: 1px solid var(--line);
}

.assistant-bubble {
  background: rgba(255, 255, 255, 0.76);
  border: 1px solid var(--line);
  color: var(--text-main);
}

.progress-line,
.meta-info {
  color: var(--text-muted);
  font-size: 13px;
}

.answer-text {
  white-space: pre-wrap;
}

.clarification-box {
  background: #fffbeb;
  color: #92400e;
  border: 1px solid #fde68a;
  border-radius: 8px;
  padding: 12px;
}

.error-box {
  background: var(--error-light);
  color: var(--error);
  border: 1px solid rgba(180, 35, 24, 0.16);
  border-radius: 8px;
  padding: 12px;
}

.data-preview,
.evidence-list {
  margin-top: 12px;
}

.data-preview summary,
.evidence-list summary {
  color: var(--text-main);
  cursor: pointer;
  font-weight: 620;
  font-size: 13px;
}

.result-table-wrap {
  margin-top: 10px;
  overflow-x: auto;
  border: 1px solid var(--line);
  border-radius: 8px;
}

.result-table {
  width: 100%;
  min-width: 640px;
  border-collapse: collapse;
  font-size: 13px;
}

.result-table th,
.result-table td {
  padding: 9px 12px;
  border-bottom: 1px solid var(--line);
  text-align: left;
}

.result-table th {
  background: var(--surface-2);
  color: var(--text-muted);
  font-weight: 620;
}

.evidence-item {
  margin-top: 10px;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface-2);
}

.evidence-item pre {
  margin: 8px 0 0;
  white-space: pre-wrap;
  word-break: break-word;
  font: inherit;
  color: var(--text-main);
}

.feedback-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--line);
  color: var(--text-muted);
  font-size: 13px;
}

.star-row {
  display: flex;
  gap: 4px;
}

.star-btn {
  border: none;
  background: transparent;
  color: #c8c8c0;
  cursor: pointer;
  font-size: 19px;
  line-height: 1;
  padding: 2px 3px;
}

.star-btn.active,
.star-btn:hover:not(:disabled) {
  color: #a16207;
}

.feedback-done {
  color: var(--success);
}

.composer {
  border-top: 1px solid var(--line);
  padding: 16px clamp(16px, 4vw, 42px) 22px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 14px;
  align-items: end;
  background: rgba(247, 247, 244, 0.92);
  backdrop-filter: blur(18px);
}

textarea {
  width: 100%;
  max-width: 820px;
  justify-self: end;
  border-radius: 10px;
  padding: 13px 14px;
  font-size: 15px;
  resize: vertical;
  color: var(--text-main);
}

.composer-actions {
  display: flex;
  gap: 10px;
}

button,
.btn-outline {
  padding: 11px 16px;
  font-size: 14px;
  font-weight: 620;
  cursor: pointer;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

@media (max-width: 720px) {
  .page-header {
    flex-direction: column;
  }

  .page-actions {
    justify-content: flex-start;
  }

  .composer {
    display: flex;
    flex-direction: column;
    align-items: stretch;
  }

  textarea {
    max-width: none;
  }

  .composer-actions {
    justify-content: flex-end;
  }

  .bubble {
    max-width: calc(100% - 46px);
  }
}
</style>

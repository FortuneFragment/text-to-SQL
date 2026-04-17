<template>
  <section class="qa-page">
    <div class="main-panel panel">
      <header class="page-header">
        <div class="header-content">
          <h2>智能知识问答</h2>
          <p>将自然语言转换为 SQL 并查询外部数据库。</p>
        </div>
        <div class="quick-nav">
          <RouterLink to="/connection" class="quick-link">连接配置</RouterLink>
          <RouterLink to="/table" class="quick-link">表开关</RouterLink>
          <RouterLink to="/field" class="quick-link">字段开关</RouterLink>
          <RouterLink to="/knowledge" class="quick-link">知识库上传</RouterLink>
        </div>
      </header>

      <div v-if="notice" class="notice" :class="noticeType">{{ notice }}</div>

      <div v-if="!connectionConfigured" class="empty-state">
        <div class="empty-icon">🔌</div>
        <p>外部数据库尚未配置，请先完成连接配置与表开关配置。</p>
      </div>

      <div class="query-box">
        <label>
          <span class="label-text">你的问题</span>
          <div class="textarea-wrap">
            <textarea v-model="question" rows="3" placeholder="例如：按班级统计平均分，展示前10名..." />
          </div>
        </label>

        <div class="action-row">
          <button class="btn-primary" @click="askQuestion" :disabled="loading.query || !connectionConfigured">
            <span>✨ 执行智能查询</span>
          </button>
          <button class="btn-outline" @click="debugGenerate" :disabled="loading.query || !connectionConfigured">仅生成 SQL</button>
          <button class="btn-ghost" @click="loadLogs" :disabled="loading.logs">↻ 刷新日志</button>
        </div>
      </div>

      <div v-if="debugResult" class="debug-block fade-in">
        <div class="debug-header">
          <h3>SQL 调试结果</h3>
          <span class="status-badge" :class="debugResult.validation_passed ? 'ok' : 'warn'">
            {{ debugResult.validation_passed ? "校验通过" : "校验失败" }}
          </span>
        </div>
        <pre class="sql-code debug-sql-code"><code>{{ debugResult.sql }}</code></pre>
        <p v-if="debugResult.validation_message" class="debug-msg">{{ debugResult.validation_message }}</p>
        <p v-if="Array.isArray(debugResult.route_tables) && debugResult.route_tables.length" class="route-msg">
          路由（{{ debugResult.route_mode || "single" }}）: {{ debugResult.route_tables.join("、") }}
        </p>
      </div>

      <div class="history-section">
        <h3 class="section-title">查询历史</h3>
        <div class="chat-container">
          <article v-for="(item, index) in history" :key="index" class="chat-bubble fade-in">
            <div class="chat-row user-row">
              <div class="avatar user-avatar">Q</div>
              <div class="chat-content user-msg">{{ item.question }}</div>
            </div>

            <div class="chat-row bot-row">
              <div class="avatar bot-avatar">A</div>
              <div class="chat-content bot-msg">
                <div class="sql-wrapper">
                  <div class="sql-header">Generated SQL</div>
                  <pre class="sql-code"><code>{{ item.sql }}</code></pre>
                </div>

                <div class="answer-text">{{ item.answer }}</div>
                <div class="meta-info">{{ item.row_count }} 行数据 · {{ item.repaired ? "已尝试修复SQL" : "原生SQL未修复" }}</div>

                <div v-if="item.rows.length" class="result-table-wrap mt-3">
                  <table class="result-table">
                    <thead>
                      <tr>
                        <th v-for="col in item.columns" :key="col">
                          <div class="th-content">{{ col }}</div>
                          <div v-if="getFieldInference(item, col)" class="infer-tag" :title="getFieldInferenceTip(item, col)">
                            {{ getFieldInference(item, col).inferred_meaning }} ({{ formatConfidence(getFieldInference(item, col).confidence) }})
                          </div>
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
            <span class="log-status" :class="log.status.toLowerCase()">{{ log.status }}</span>
            <span class="log-time">{{ formatTime(log.created_at) }}</span>
          </div>
          <p class="log-q">{{ log.question }}</p>
          <div class="log-meta">耗时: {{ log.duration_ms ?? "-" }} ms | 结果: {{ log.row_count ?? "-" }} 行</div>
        </article>
        <div v-if="logs.length === 0" class="empty-state">暂无日志。</div>
      </div>
    </aside>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";
import { apiRequest } from "../api/client";

// 原有逻辑原封不动
const loading = reactive({ query: false, logs: false });
const question = ref(""); const history = ref([]); const logs = ref([]);
const debugResult = ref(null); const connectionConfigured = ref(false);
const notice = ref(""); const noticeType = ref("info");

// 中文备注：处理setNotice相关业务数据并返回结果。
// 执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
function setNotice(message, type = "info") { notice.value = message; noticeType.value = type; }
// 中文备注：处理buildFieldInferenceMap相关业务数据并返回结果。
// 执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
function buildFieldInferenceMap(fieldInference) {
  const map = {};
  for (const item of fieldInference || []) { if (!item || !item.column) continue; map[item.column] = item; }
  return map;
}
// 中文备注：处理getFieldInference相关业务数据并返回结果。
// 执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
function getFieldInference(item, column) { return item?.field_inference_map?.[column] || null; }
// 中文备注：处理getFieldInferenceTip相关业务数据并返回结果。
// 执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
function getFieldInferenceTip(item, column) { const inference = getFieldInference(item, column); return inference?.reason || ""; }
// 中文备注：处理formatConfidence相关业务数据并返回结果。
// 执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
function formatConfidence(value) { const num = Number(value); if (!Number.isFinite(num)) return "-"; return `${Math.round(Math.max(0, Math.min(1, num)) * 100)}%`; }
// 中文备注：处理loadConnectionStatus相关业务数据并返回结果。
// 执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
async function loadConnectionStatus() { try { const data = await apiRequest("/text2sql/connection"); connectionConfigured.value = Boolean(data.configured); } catch { connectionConfigured.value = false; } }
// 中文备注：处理askQuestion相关业务数据并返回结果。
// 执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
async function askQuestion() {
  if (!question.value.trim()) { setNotice("请先输入问题", "error"); return; }
  loading.query = true;
  try {
    const data = await apiRequest("/text2sql/qa/query", { method: "POST", body: JSON.stringify({ question: question.value }) });
    const fieldInference = Array.isArray(data.field_inference) ? data.field_inference : [];
    history.value.unshift({ question: question.value, ...data, field_inference: fieldInference, field_inference_map: buildFieldInferenceMap(fieldInference) });
    question.value = ""; debugResult.value = null; await loadLogs(); setNotice("查询成功", "success");
  } catch (error) { setNotice(`查询失败：${error.message}`, "error"); } finally { loading.query = false; }
}
// 中文备注：处理debugGenerate相关业务数据并返回结果。
// 执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
async function debugGenerate() {
  if (!question.value.trim()) { setNotice("请先输入问题", "error"); return; }
  loading.query = true;
  try {
    debugResult.value = await apiRequest("/text2sql/qa/debug/generate", { method: "POST", body: JSON.stringify({ question: question.value }) });
    setNotice("SQL 生成完成", "success");
  } catch (error) { setNotice(`调试失败：${error.message}`, "error"); } finally { loading.query = false; }
}
// 中文备注：处理loadLogs相关业务数据并返回结果。
// 执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
async function loadLogs() { loading.logs = true; try { logs.value = await apiRequest("/text2sql/qa/logs?limit=20"); } catch { logs.value = []; } finally { loading.logs = false; } }
// 中文备注：处理formatTime相关业务数据并返回结果。
// 执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
function formatTime(value) { return value ? new Date(value).toLocaleString() : "-"; }

onMounted(async () => { await Promise.all([loadConnectionStatus(), loadLogs()]); });
</script>

<style scoped>
.qa-page { display: grid; grid-template-columns: 1fr 340px; gap: 24px; align-items: start; }
@media (max-width: 1024px) { .qa-page { grid-template-columns: 1fr; } }

.panel { background: var(--bg-panel); backdrop-filter: blur(16px); border: 1px solid rgba(255,255,255,0.8); border-radius: var(--radius); box-shadow: var(--shadow); padding: 24px; }
.main-panel { min-height: 80vh; }
.side-panel { position: sticky; top: 24px; max-height: calc(100vh - 48px); overflow-y: auto; }

.page-header { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--line); }
h2 { margin: 0 0 8px; font-size: 22px; font-weight: 700; color: var(--text-main); }
.header-content p { margin: 0; color: var(--text-muted); font-size: 14px; }
.quick-nav { display: flex; gap: 8px; }
.quick-link { text-decoration: none; padding: 6px 12px; border-radius: 8px; font-size: 13px; font-weight: 600; color: var(--accent); background: var(--accent-light); transition: 0.2s; }
.quick-link:hover { background: var(--accent); color: white; }

.query-box { background: #f8fafc; border-radius: 16px; padding: 20px; border: 1px solid var(--line); margin-bottom: 24px; }
.label-text { font-weight: 600; margin-bottom: 8px; display: inline-block; color: var(--text-main); }
.textarea-wrap { position: relative; }
textarea { width: 100%; border: 1px solid var(--line); border-radius: 12px; padding: 14px; font-size: 15px; resize: vertical; box-shadow: inset 0 2px 4px rgba(0,0,0,0.02); transition: 0.2s; }
textarea:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-light); }

.action-row { display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap; }
button { border: none; border-radius: 10px; font-weight: 600; padding: 12px 20px; cursor: pointer; transition: 0.2s; }
button:active:not(:disabled) { transform: scale(0.98); }
button:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-primary { background: var(--accent); color: white; box-shadow: 0 4px 12px rgba(79, 70, 229, 0.2); }
.btn-primary:hover:not(:disabled) { background: var(--accent-hover); }
.btn-outline { border: 1px solid var(--accent); color: var(--accent); background: transparent; }
.btn-outline:hover:not(:disabled) { background: var(--accent-light); }
.btn-ghost { background: transparent; color: var(--text-muted); border: 1px solid transparent; }
.btn-ghost:hover:not(:disabled) { background: #e2e8f0; color: var(--text-main); }

.section-title { font-size: 18px; font-weight: 700; margin: 0 0 16px; color: var(--text-main); }

/* Chat Bubbles */
.chat-container { display: flex; flex-direction: column; gap: 24px; }
.chat-row { display: flex; gap: 16px; margin-bottom: 16px; align-items: flex-start; }
.avatar { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; flex-shrink: 0; color: white; box-shadow: var(--shadow-sm); }
.user-avatar { background: #3b82f6; }
.bot-avatar { background: #10b981; }

.chat-content { padding: 16px; border-radius: 16px; max-width: 100%; box-shadow: var(--shadow-sm); line-height: 1.5; font-size: 15px; }
.user-msg { background: #eff6ff; color: #1e3a8a; border-top-left-radius: 4px; }
.bot-msg { background: #ffffff; border: 1px solid var(--line); border-top-left-radius: 4px; width: 100%; overflow: hidden; }

.sql-wrapper { background: #1e293b; border-radius: 8px; overflow: hidden; margin-bottom: 16px; }
.sql-header { background: #0f172a; color: #94a3b8; font-size: 12px; padding: 6px 12px; font-family: monospace; border-bottom: 1px solid #334155; }
.sql-code { margin: 0; padding: 16px; color: #e2e8f0; font-family: monospace; font-size: 13px; white-space: pre-wrap; word-break: break-all; }

.answer-text { font-weight: 500; color: #0f172a; margin-bottom: 8px; }
.meta-info { font-size: 12px; color: #64748b; }

/* Result Table */
.result-table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; }
.result-table { width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; }
.result-table th, .result-table td { padding: 10px 14px; border-bottom: 1px solid var(--line); }
.result-table th { background: #f8fafc; font-weight: 600; color: var(--text-muted); }
.result-table tr:hover td { background: #f1f5f9; }
.infer-tag { display: inline-block; background: #d1fae5; color: #065f46; font-size: 11px; padding: 2px 6px; border-radius: 4px; margin-top: 4px; font-weight: 500; }

/* Debug Block */
.debug-block { background: #fff; border: 1px solid var(--line); border-radius: 12px; padding: 16px; margin-bottom: 24px; border-left: 4px solid var(--accent); }
.debug-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.debug-header h3 { margin: 0; font-size: 16px; }
.status-badge { font-size: 12px; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
.status-badge.ok { background: #d1fae5; color: #065f46; }
.status-badge.warn { background: #fee2e2; color: #991b1b; }
.debug-sql-code {
  background: #0f172a;
  color: #f8fafc;
  border: 1px solid #1e293b;
  border-radius: 8px;
  opacity: 1;
}
.debug-sql-code code { color: inherit; opacity: 1; }
.debug-msg { color: #ef4444; font-size: 13px; margin-top: 8px; }
.route-msg { color: #334155; font-size: 14px; margin-top: 8px; }

/* Logs Sidebar */
.log-list { display: flex; flex-direction: column; gap: 12px; }
.log-item { background: #f8fafc; padding: 12px; border-radius: 8px; border: 1px solid #e2e8f0; font-size: 13px; }
.log-header { display: flex; justify-content: space-between; margin-bottom: 6px; }
.log-status { font-weight: bold; }
.log-status.success { color: #10b981; }
.log-status.error { color: #ef4444; }
.log-time { color: #94a3b8; font-size: 12px; }
.log-q { margin: 0 0 6px; font-weight: 500; color: #334155; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.log-meta { color: #64748b; font-size: 12px; }

.empty-state { text-align: center; color: var(--text-muted); padding: 32px 0; }
.empty-icon { font-size: 32px; margin-bottom: 8px; opacity: 0.5; }
.py-8 { padding-top: 32px; padding-bottom: 32px; } .mt-3 { margin-top: 12px; }

.notice { padding: 12px 16px; border-radius: 10px; font-size: 14px; font-weight: 500; margin-bottom: 20px; }
.notice.success { background: #d1fae5; color: #065f46; border: 1px solid #34d399; }
.notice.error { background: #fee2e2; color: #991b1b; border: 1px solid #f87171; }
</style>

<template>
  <section class="panel">
    <div class="panel-header">
      <h2>外部数据库连接</h2>
    </div>

    <div v-if="notice" class="notice" :class="noticeType">
      <span class="icon">ℹ️</span> {{ notice }}
    </div>

    <div class="form-container">
      <div class="grid-two">
        <label>
          <span>数据库类型</span>
          <select v-model="connection.db_type" @change="applyTypeDefaults">
            <option value="sqlserver">SQL Server</option>
          </select>
        </label>
        <label>
          <span>主机地址</span>
          <input v-model.trim="connection.host" placeholder="127.0.0.1" />
        </label>
        <label>
          <span>端口</span>
          <input v-model.number="connection.port" type="number" min="1" max="65535" />
        </label>
        <label>
          <span>数据库名</span>
          <input v-model.trim="connection.database" placeholder="school_db" />
        </label>
        <label>
          <span>架构（Schema）</span>
          <div class="inline-input">
            <input
              v-model.trim="connection.db_schema"
              list="schema-options"
              placeholder="SQL Server 常用 dbo，可留空"
            />
            <button class="btn-small" @click="loadSchemas" :disabled="loading.connection || loading.schemas">
              {{ loading.schemas ? "获取中" : "获取架构" }}
            </button>
          </div>
          <datalist id="schema-options">
            <option v-for="name in schemaOptions" :key="name" :value="name" />
          </datalist>
        </label>
        <label>
          <span>字符集</span>
          <input v-model.trim="connection.charset" placeholder="UTF-8" />
        </label>
        <label>
          <span>用户名</span>
          <input v-model.trim="connection.username" placeholder="qa_user" />
        </label>
        <label>
          <span>密码</span>
          <input v-model="connection.password" type="password" placeholder="留空则保持已保存密码" />
          <span v-if="connectionConfigured && hasPassword && !connection.password" class="field-tip">
            已保存密码；连接目标不变时可留空复用。
          </span>
        </label>
      </div>

      <div class="row-actions">
        <button class="btn-primary" @click="testConnection" :disabled="loading.connection">测试连接</button>
        <button class="btn-success" @click="saveConnection" :disabled="loading.connection">保存并切换连接</button>
        <div class="status-indicator" :class="connectionConfigured ? 'ok' : 'warn'">
          <span class="dot"></span>
          {{ connectionConfigured ? "已配置 SQL Server 数据库" : "未配置外部数据库" }}
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { apiRequest } from "../api/client";

const DB_DEFAULTS = {
  sqlserver: { port: 1433, charset: "UTF-8" },
};

const loading = reactive({ connection: false, schemas: false });
const connection = reactive({
  db_type: "sqlserver",
  host: "127.0.0.1",
  port: DB_DEFAULTS.sqlserver.port,
  username: "",
  password: "",
  database: "",
  db_schema: "",
  charset: DB_DEFAULTS.sqlserver.charset,
});

const connectionConfigured = ref(false);
const hasPassword = ref(false);
const schemaOptions = ref([]);
const notice = ref("");
const noticeType = ref("info");

function setNotice(message, type = "info") {
  notice.value = message;
  noticeType.value = type;
}

function applyTypeDefaults() {
  const defaults = DB_DEFAULTS[connection.db_type] || DB_DEFAULTS.sqlserver;
  connection.port = defaults.port;
  connection.charset = defaults.charset;
}

function buildPayload() {
  const password = String(connection.password || "").trim();
  const schema = String(connection.db_schema || "").trim();
  return {
    db_type: connection.db_type,
    host: connection.host.trim(),
    port: Number(connection.port),
    username: connection.username.trim(),
    password: password ? password : null,
    database: connection.database.trim(),
    db_schema: schema ? schema : null,
    charset: connection.charset.trim() || (DB_DEFAULTS[connection.db_type] || DB_DEFAULTS.sqlserver).charset,
  };
}

function validatePayload(payload) {
  if (!payload.host || !payload.username || !payload.database) {
    setNotice("主机、用户名和数据库名为必填项。", "error");
    return false;
  }
  if (!Number.isInteger(payload.port) || payload.port < 1 || payload.port > 65535) {
    setNotice("端口必须是 1 到 65535 之间的整数。", "error");
    return false;
  }
  return true;
}

async function loadConnection() {
  const data = await apiRequest("/text2sql/connection");
  connectionConfigured.value = Boolean(data.configured);
  hasPassword.value = Boolean(data.has_password);
  if (!data.configured) return;
  connection.db_type = data.db_type || "sqlserver";
  connection.host = data.host || "127.0.0.1";
  connection.port = data.port || (DB_DEFAULTS[connection.db_type] || DB_DEFAULTS.sqlserver).port;
  connection.username = data.username || "";
  connection.database = data.database || "";
  connection.db_schema = data.db_schema || "";
  connection.charset = data.charset || (DB_DEFAULTS[connection.db_type] || DB_DEFAULTS.sqlserver).charset;
  connection.password = "";
}

async function testConnection() {
  const payload = buildPayload();
  if (!validatePayload(payload)) return;

  loading.connection = true;
  try {
    const data = await apiRequest("/text2sql/connection/test", { method: "POST", body: JSON.stringify(payload) });
    setNotice(data.message || "外部数据库连接测试成功", "success");
  } catch (error) {
    setNotice(`连接测试失败：${error.message}`, "error");
  } finally {
    loading.connection = false;
  }
}

async function loadSchemas() {
  const payload = buildPayload();
  if (!validatePayload(payload)) return;

  loading.schemas = true;
  try {
    const data = await apiRequest("/text2sql/connection/schemas", { method: "POST", body: JSON.stringify(payload) });
    schemaOptions.value = Array.isArray(data.schemas) ? data.schemas : [];
    setNotice(schemaOptions.value.length ? `已获取 ${schemaOptions.value.length} 个架构。` : "未获取到可用架构。", "info");
  } catch (error) {
    setNotice(`获取架构失败：${error.message}`, "error");
  } finally {
    loading.schemas = false;
  }
}

async function saveConnection() {
  const payload = buildPayload();
  if (!validatePayload(payload)) return;

  loading.connection = true;
  try {
    const data = await apiRequest("/text2sql/connection", { method: "PUT", body: JSON.stringify(payload) });
    connectionConfigured.value = Boolean(data.configured);
    hasPassword.value = Boolean(data.has_password);
    connection.password = "";
    setNotice("外部数据库连接已保存并生效", "success");
  } catch (error) {
    setNotice(`保存外部连接失败：${error.message}`, "error");
  } finally {
    loading.connection = false;
  }
}

onMounted(async () => {
  try {
    await loadConnection();
  } catch (error) {
    setNotice(`初始化失败：${error.message}`, "error");
  }
});
</script>

<style scoped>
.panel {
  background: transparent;
  border: none;
  border-radius: 0;
  box-shadow: none;
  padding: clamp(16px, 3vw, 28px) 0;
  max-width: 1120px;
  margin: 0 auto;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 18px;
  margin-bottom: 28px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--line);
}

h2 {
  margin: 0;
  font-size: clamp(26px, 3vw, 38px);
  font-weight: 720;
  letter-spacing: 0;
  line-height: 1.08;
}

.form-container { display: flex; flex-direction: column; gap: 28px; }

.grid-two { display: grid; grid-template-columns: 1fr 1fr; gap: 18px 22px; }

label { display: flex; flex-direction: column; gap: 8px; font-size: 13px; font-weight: 620; color: var(--text-main); }
label span { color: var(--text-muted); }

input,
select {
  min-height: 42px;
  padding: 11px 12px;
}

.inline-input {
  display: flex;
  gap: 8px;
}
.inline-input input { flex: 1; min-width: 0; }

.field-tip {
  font-size: 12px;
  color: var(--text-muted);
}

.row-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: 4px; }

button {
  padding: 10px 14px;
  font-weight: 600; cursor: pointer; display: flex; justify-content: center; align-items: center;
}

.btn-small {
  padding: 0 14px;
  min-width: 92px;
  white-space: nowrap;
}

.status-indicator {
  display: flex; align-items: center; gap: 8px;
  min-height: 34px;
  font-size: 13px; font-weight: 560; padding: 7px 11px; border-radius: 7px; background: var(--surface-2); color: var(--text-muted);
}
.dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
.status-indicator.ok { color: var(--success); background: #ecfdf5; }
.status-indicator.warn { color: var(--warn); background: #fef2f2; }

.notice {
  margin-bottom: 22px; display: flex; align-items: center; gap: 10px;
  border-radius: 8px; font-size: 13px; padding: 11px 13px; font-weight: 560;
}
.notice.success { background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; }
.notice.error { background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }
.notice.info { background: #eff6ff; color: #1e40af; border: 1px solid #bfdbfe; }

@media (max-width: 760px) {
  .grid-two { grid-template-columns: 1fr; }
  .panel-header { align-items: flex-start; flex-direction: column; }
  .inline-input { flex-direction: column; }
  .btn-small { min-height: 40px; }
}
</style>

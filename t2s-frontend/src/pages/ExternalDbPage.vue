<template>
  <section class="panel">
    <div class="panel-header">
      <h2>外部数据库连接</h2>
      <div class="quick-nav">
        <RouterLink to="/table" class="quick-link">表开关 <span class="arrow">→</span></RouterLink>
        <RouterLink to="/field" class="quick-link">字段开关 <span class="arrow">→</span></RouterLink>
        <RouterLink to="/qa" class="quick-link">知识问答 <span class="arrow">→</span></RouterLink>
      </div>
    </div>

    <div v-if="notice" class="notice" :class="noticeType">
      <span class="icon">ℹ️</span> {{ notice }}
    </div>

    <div class="form-container">
      <div class="grid-two">
        <label>
          <span>主机地址</span>
          <input v-model.trim="connection.host" placeholder="127.0.0.1" />
        </label>
        <label>
          <span>端口</span>
          <input v-model.number="connection.port" type="number" />
        </label>
        <label>
          <span>数据库名</span>
          <input v-model.trim="connection.database" placeholder="school_db" />
        </label>
        <label>
          <span>字符集</span>
          <input v-model.trim="connection.charset" placeholder="utf8mb4" />
        </label>
        <label>
          <span>用户名</span>
          <input v-model.trim="connection.username" placeholder="qa_user" />
        </label>
        <label>
          <span>密码</span>
          <input v-model="connection.password" type="password" placeholder="留空则保持已保存密码" />
        </label>
      </div>

      <div class="row-actions">
        <button class="btn-primary" @click="testConnection" :disabled="loading.connection">测试连接</button>
        <button class="btn-success" @click="saveConnection" :disabled="loading.connection">保存并切换连接</button>
        <div class="status-indicator" :class="connectionConfigured ? 'ok' : 'warn'">
          <span class="dot"></span>
          {{ connectionConfigured ? "已配置外部数据库" : "未配置外部数据库" }}
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";
import { apiRequest } from "../api/client";

const loading = reactive({ connection: false });
const connection = reactive({
  db_type: "mysql", host: "127.0.0.1", port: 3306,
  username: "", password: "", database: "", charset: "utf8mb4",
});

const connectionConfigured = ref(false);
const notice = ref("");
const noticeType = ref("info");

function setNotice(message, type = "info") { notice.value = message; noticeType.value = type; }

async function loadConnection() {
  const data = await apiRequest("/text2sql/connection");
  connectionConfigured.value = Boolean(data.configured);
  if (!data.configured) return;
  connection.db_type = data.db_type || "mysql";
  connection.host = data.host || "127.0.0.1";
  connection.port = data.port || 3306;
  connection.username = data.username || "";
  connection.database = data.database || "";
  connection.charset = data.charset || "utf8mb4";
  connection.password = "";
}

async function testConnection() {
  loading.connection = true;
  try {
    await apiRequest("/text2sql/connection/test", { method: "POST", body: JSON.stringify(connection) });
    setNotice("外部数据库连接测试成功", "success");
  } catch (error) { setNotice(`连接测试失败：${error.message}`, "error"); }
  finally { loading.connection = false; }
}

async function saveConnection() {
  loading.connection = true;
  try {
    await apiRequest("/text2sql/connection", { method: "PUT", body: JSON.stringify(connection) });
    connectionConfigured.value = true;
    setNotice("外部数据库连接已保存并生效", "success");
  } catch (error) { setNotice(`保存外部连接失败：${error.message}`, "error"); }
  finally { loading.connection = false; }
}

onMounted(async () => {
  try { await loadConnection(); }
  catch (error) { setNotice(`初始化失败：${error.message}`, "error"); }
});
</script>

<style scoped>
.panel {
  background: var(--bg-panel);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255,255,255,0.6);
  border-radius: var(--radius);
  box-shadow: var(--shadow-lg);
  padding: 32px;
  max-width: 800px;
  margin: 0 auto;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--line);
}

h2 { margin: 0; font-size: 22px; font-weight: 700; }

.quick-nav { display: flex; gap: 12px; }
.quick-link {
  text-decoration: none; color: var(--accent);
  font-size: 14px; font-weight: 600; padding: 6px 12px;
  background: var(--accent-light); border-radius: 8px;
  transition: all 0.2s;
}
.quick-link:hover { background: var(--accent); color: white; }
.arrow { display: inline-block; transition: transform 0.2s; }
.quick-link:hover .arrow { transform: translateX(3px); }

.form-container { display: flex; flex-direction: column; gap: 24px; }

.grid-two { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }

label { display: flex; flex-direction: column; gap: 8px; font-size: 14px; font-weight: 500; color: var(--text-main); }
label span { color: var(--text-muted); }

input {
  background: #f8fafc; border: 1px solid var(--line);
  border-radius: 10px; padding: 12px 16px; color: var(--text-main);
  box-shadow: inset 0 1px 2px rgba(0,0,0,0.02);
}
input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-light); background: #ffffff; }

.row-actions { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; margin-top: 8px; }

button {
  border: none; border-radius: 10px; padding: 12px 24px;
  font-weight: 600; cursor: pointer; display: flex; justify-content: center; align-items: center;
}
button:active { transform: scale(0.98); }
button:disabled { opacity: 0.6; cursor: not-allowed; }

.btn-primary { background: var(--accent); color: white; box-shadow: 0 4px 12px rgba(79, 70, 229, 0.2); }
.btn-primary:hover:not(:disabled) { background: var(--accent-hover); }

.btn-success { background: var(--text-main); color: white; }
.btn-success:hover:not(:disabled) { background: #000; }

.status-indicator {
  display: flex; align-items: center; gap: 8px;
  font-size: 14px; font-weight: 500; padding: 8px 16px; border-radius: 999px; background: #f1f5f9; color: var(--text-muted);
}
.dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
.status-indicator.ok { color: var(--success); background: #ecfdf5; }
.status-indicator.warn { color: var(--warn); background: #fef2f2; }

.notice {
  margin-bottom: 24px; display: flex; align-items: center; gap: 10px;
  border-radius: 12px; font-size: 14px; padding: 12px 16px; font-weight: 500;
}
.notice.success { background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; }
.notice.error { background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }
.notice.info { background: #eff6ff; color: #1e40af; border: 1px solid #bfdbfe; }

@media (max-width: 640px) { .grid-two { grid-template-columns: 1fr; } }
</style>
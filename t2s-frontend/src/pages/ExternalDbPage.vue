<template>
  <section class="panel">
    <h2>外部数据库连接</h2>

    <div class="quick-nav">
      <RouterLink to="/table" class="quick-link">去表开关</RouterLink>
      <RouterLink to="/qa" class="quick-link">去知识问答</RouterLink>
    </div>

    <div v-if="notice" class="notice" :class="noticeType">{{ notice }}</div>

    <div class="grid-two">
      <label>主机地址<input v-model.trim="connection.host" placeholder="127.0.0.1" /></label>
      <label>端口<input v-model.number="connection.port" type="number" /></label>
      <label>数据库名<input v-model.trim="connection.database" placeholder="school_db" /></label>
      <label>字符集<input v-model.trim="connection.charset" placeholder="utf8mb4" /></label>
      <label>用户名<input v-model.trim="connection.username" placeholder="qa_user" /></label>
      <label>密码<input v-model="connection.password" type="password" placeholder="留空则保持已保存密码" /></label>
    </div>

    <div class="row">
      <button @click="testConnection" :disabled="loading.connection">测试连接</button>
      <button @click="saveConnection" :disabled="loading.connection">保存并切换连接</button>
      <span class="tag" :class="connectionConfigured ? 'ok' : 'warn'">
        {{ connectionConfigured ? "已配置外部数据库" : "未配置外部数据库" }}
      </span>
    </div>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";

import { apiRequest } from "../api/client";

const loading = reactive({
  connection: false,
});

const connection = reactive({
  db_type: "mysql",
  host: "127.0.0.1",
  port: 3306,
  username: "",
  password: "",
  database: "",
  charset: "utf8mb4",
});

const connectionConfigured = ref(false);
const notice = ref("");
const noticeType = ref("info");

function setNotice(message, type = "info") {
  notice.value = message;
  noticeType.value = type;
}

async function loadConnection() {
  const data = await apiRequest("/text2sql/connection");
  connectionConfigured.value = Boolean(data.configured);

  if (!data.configured) {
    return;
  }

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
    await apiRequest("/text2sql/connection/test", {
      method: "POST",
      body: JSON.stringify(connection),
    });
    setNotice("外部数据库连接测试成功", "success");
  } catch (error) {
    setNotice(`连接测试失败：${error.message}`, "error");
  } finally {
    loading.connection = false;
  }
}

async function saveConnection() {
  loading.connection = true;
  try {
    await apiRequest("/text2sql/connection", {
      method: "PUT",
      body: JSON.stringify(connection),
    });
    connectionConfigured.value = true;
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

input {
  background: var(--bg-card);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 10px 12px;
  color: var(--text-main);
}

.grid-two {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 12px 0 0;
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

@media (max-width: 980px) {
  .grid-two {
    grid-template-columns: 1fr;
  }
}
</style>

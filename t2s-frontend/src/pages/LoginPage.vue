<template>
  <main class="login-page">
    <section class="login-card" aria-labelledby="login-title">
      <div class="login-kicker">湖南师范大学智慧校园数据平台</div>
      <h1 id="login-title">统一身份认证</h1>
      <p v-if="loggedOut" class="logout-notice">已安全退出当前账号。</p>
      <p class="login-copy">使用学校统一身份认证登录后，即可进入数据与文档问答平台。</p>
      <a class="login-button" :href="loginUrl">
        使用统一身份认证登录
      </a>
      <small>账号和密码仅在学校统一身份认证平台输入，本系统不会接触你的密码。</small>

      <div v-if="devLoginEnabled" class="dev-login">
        <div>
          <strong>本地开发登录</strong>
          <p>仅 Vite 开发模式可见，不需要学校 OAuth 凭据。</p>
        </div>
        <div class="dev-actions">
          <button
            type="button"
            :disabled="Boolean(devLoading)"
            @click="devLogin('chat_user')"
          >
            {{ devLoading === "chat_user" ? "登录中..." : "普通用户" }}
          </button>
          <button
            type="button"
            :disabled="Boolean(devLoading)"
            @click="devLogin('info_admin')"
          >
            {{ devLoading === "info_admin" ? "登录中..." : "管理员" }}
          </button>
        </div>
        <p v-if="devError" class="dev-error">{{ devError }}</p>
      </div>
    </section>
  </main>
</template>

<script setup>
import { ref } from "vue";

import { API_BASE, apiRequest } from "../api/client.js";

const query = new URLSearchParams(window.location.search);
const loggedOut = query.get("logged_out") === "1";
const requestedNext = query.get("next") || "/chat";
const nextPath = requestedNext.startsWith("/") && !requestedNext.startsWith("//")
  ? requestedNext
  : "/chat";
const loginUrl = `${API_BASE}/auth/login?next=${encodeURIComponent(nextPath)}`;
const devLoginEnabled = import.meta.env.DEV;
const devLoading = ref("");
const devError = ref("");

async function devLogin(role) {
  devLoading.value = role;
  devError.value = "";

  try {
    await apiRequest(`/dev/auth/login?role=${encodeURIComponent(role)}`, {
      method: "POST",
    });
    window.location.href = role === "info_admin" ? "/admin" : nextPath;
  } catch (error) {
    devError.value = error?.message || "本地登录失败，请确认后端开发登录已启用。";
    devLoading.value = "";
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100dvh;
  display: grid;
  place-items: center;
  padding: 24px;
}

.login-card {
  width: min(480px, 100%);
  padding: clamp(28px, 5vw, 48px);
  border: 1px solid var(--line);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: var(--shadow-lg);
}

.login-kicker {
  margin-bottom: 18px;
  color: var(--accent);
  font-size: 13px;
  font-weight: 720;
  letter-spacing: 0.04em;
}

h1 {
  margin: 0;
  font-size: clamp(30px, 6vw, 44px);
  line-height: 1.08;
}

.login-copy,
.logout-notice {
  line-height: 1.7;
}

.login-copy {
  margin: 18px 0 24px;
  color: var(--text-muted);
}

.logout-notice {
  margin: 18px 0 0;
  padding: 10px 12px;
  border: 1px solid rgba(4, 120, 87, 0.16);
  border-radius: 8px;
  background: var(--success-light);
  color: var(--success);
}

.login-button {
  display: flex;
  min-height: 46px;
  align-items: center;
  justify-content: center;
  padding: 0 18px;
  border: 1px solid var(--accent);
  border-radius: 8px;
  background: var(--accent);
  color: #ffffff;
  font-weight: 700;
  text-decoration: none;
  box-shadow: 0 12px 28px rgba(var(--accent-rgb), 0.2);
}

.login-button:hover {
  border-color: var(--accent-hover);
  background: var(--accent-hover);
  transform: translateY(-1px);
}

small {
  display: block;
  margin-top: 16px;
  color: var(--text-soft);
  line-height: 1.6;
}

.dev-login {
  margin-top: 28px;
  padding-top: 22px;
  border-top: 1px solid var(--line);
}

.dev-login strong {
  font-size: 14px;
}

.dev-login p {
  margin: 6px 0 14px;
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.6;
}

.dev-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.dev-actions button {
  min-height: 40px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #ffffff;
  color: var(--text-main);
  cursor: pointer;
}

.dev-actions button:hover:not(:disabled) {
  border-color: rgba(var(--accent-rgb), 0.28);
  background: var(--accent-light);
  color: var(--accent);
}

.dev-login .dev-error {
  margin-bottom: 0;
  color: var(--error);
}
</style>

<template>
  <div class="app-shell">
    <header class="hero fade-in">
      <div class="hero-content">
        <h1>Text2SQL <span class="badge">Pro</span></h1>
        <p>数据库连接、表开关、字段开关与知识问答管理终端</p>
      </div>
      <nav class="top-nav">
        <RouterLink to="/connection" class="nav-link" active-class="nav-link-active">外部数据库连接</RouterLink>
        <RouterLink to="/table" class="nav-link" active-class="nav-link-active">表开关</RouterLink>
        <RouterLink to="/field" class="nav-link" active-class="nav-link-active">字段开关</RouterLink>
        <RouterLink to="/knowledge" class="nav-link" active-class="nav-link-active">知识库上传</RouterLink>
        <RouterLink to="/qa" class="nav-link" active-class="nav-link-active">知识问答</RouterLink>
      </nav>
    </header>

    <main class="page-wrap fade-in" style="animation-delay: 0.1s;">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { RouterLink, RouterView } from "vue-router";
</script>

<style scoped>
.app-shell {
  max-width: 1440px;
  margin: 0 auto;
  padding: 32px 24px;
}

.hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 32px;
  text-align: center;
}

.hero h1 {
  margin: 0;
  font-size: 38px;
  font-weight: 800;
  color: #1e293b;
  letter-spacing: -0.5px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.badge {
  font-size: 14px;
  background: var(--accent);
  color: white;
  padding: 4px 10px;
  border-radius: 8px;
  vertical-align: middle;
}

.hero p {
  margin: 12px 0 24px;
  color: var(--text-muted);
  font-size: 16px;
}

.top-nav {
  display: inline-flex;
  gap: 4px;
  flex-wrap: wrap;
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(12px);
  padding: 6px;
  border-radius: 999px;
  box-shadow: var(--shadow-sm);
  border: 1px solid rgba(255, 255, 255, 0.8);
}

.nav-link {
  text-decoration: none;
  color: var(--text-muted);
  border-radius: 999px;
  padding: 10px 20px;
  font-size: 15px;
  font-weight: 600;
  transition: all 0.3s ease;
}

.nav-link:hover {
  color: var(--text-main);
  background: rgba(255, 255, 255, 0.5);
}

.nav-link-active {
  color: var(--accent);
  background: #ffffff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.page-wrap {
  min-height: 600px;
}
</style>

<template>
  <div class="app-shell">
    <header class="hero fade-in">
      <h1>Text2SQL</h1>
      <p>外部数据库连接、表开关配置与知识问答分离为三个页面</p>
      <nav class="top-nav">
        <RouterLink to="/connection" class="nav-link" active-class="nav-link-active">外部数据库连接</RouterLink>
        <RouterLink to="/table" class="nav-link" active-class="nav-link-active">表开关</RouterLink>
        <RouterLink to="/qa" class="nav-link" active-class="nav-link-active">知识问答</RouterLink>
      </nav>
    </header>

    <main class="page-wrap fade-in">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { RouterLink, RouterView } from "vue-router";
</script>

<style scoped>
.app-shell {
  max-width: 1380px;
  margin: 0 auto;
  padding: 24px;
}

.hero {
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
  border-radius: 20px;
  padding: 20px;
  margin-bottom: 16px;
}

.hero h1 {
  margin: 0;
  font-family: "Bricolage Grotesque", "Space Grotesk", sans-serif;
  font-size: 32px;
}

.hero p {
  margin: 8px 0 12px;
  color: var(--text-muted);
}

.top-nav {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.nav-link {
  text-decoration: none;
  color: var(--text-main);
  border: 1px solid var(--line);
  background: #ffffff;
  border-radius: 999px;
  padding: 8px 14px;
  font-weight: 600;
}

.nav-link-active {
  color: #ffffff;
  background: var(--accent);
  border-color: var(--accent);
}

.page-wrap {
  min-height: 400px;
}
</style>

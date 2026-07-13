<template>
  <RouterView v-if="isStandaloneRoute" />

  <div v-else class="admin-shell">
    <a class="skip-link" href="#main-content">跳到主内容</a>

    <aside class="admin-sidebar" aria-label="后台管理导航">
      <div class="brand-panel">
        <img class="brand-emblem" :src="hnuEmblemUrl" alt="湖南师范大学校徽" />
        <span>
          <strong>湖南师范大学智慧校园数据平台</strong>
          <small>Smart Campus Data Platform</small>
        </span>
      </div>

      <nav class="sidebar-nav" aria-label="后台管理">
        <section v-for="group in adminGroups" :key="group.label" class="nav-group">
          <button
            type="button"
            class="nav-group-trigger"
            :aria-expanded="isGroupExpanded(group.label)"
            @click="toggleGroup(group.label)"
          >
            <span>
              <strong>{{ group.label }}</strong>
              <small>{{ group.description }}</small>
            </span>
            <span class="group-toggle" aria-hidden="true">{{ isGroupExpanded(group.label) ? "-" : "+" }}</span>
          </button>

          <div v-if="isGroupExpanded(group.label)" class="nav-group-items">
            <RouterLink
              v-for="item in group.items"
              :key="item.to"
              :to="item.to"
              class="sidebar-link"
              :class="{ 'sidebar-link-active': isActiveNav(item) }"
            >
              <span>{{ item.label }}</span>
              <small>{{ item.caption }}</small>
            </RouterLink>
          </div>
        </section>
      </nav>
    </aside>

    <div class="admin-content">
      <header class="admin-header">
        <div class="header-title-block">
          <span class="section-kicker">{{ currentSection }}</span>
          <h1>{{ currentTitle }}</h1>
          <div class="admin-user-line">
            <span>{{ currentUserName }}</span>
            <a :href="ssoLogoutUrl">退出登录</a>
          </div>
        </div>

        <aside class="header-context" aria-label="当前工作区快捷入口">
          <div class="context-copy">
            <span>当前工作区</span>
            <strong>{{ currentGroupDescription }}</strong>
            <p>{{ currentItemCaption }}</p>
          </div>
          <nav v-if="relatedItems.length" class="context-links" aria-label="相关功能">
            <RouterLink v-for="item in relatedItems" :key="item.to" :to="item.to">
              <span>{{ item.label }}</span>
              <small>{{ item.caption }}</small>
            </RouterLink>
          </nav>
        </aside>
      </header>

      <main id="main-content" class="page-wrap">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, inject, reactive } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";
import { API_BASE } from "./api/client.js";

const route = useRoute();
const userState = inject("userState");
const ssoLogoutUrl = `${API_BASE}/auth/logout/sso`;
const hnuEmblemUrl = "https://www.hunnu.edu.cn/__local/1/61/8A/173AEDD84CE6448B5C06DA216DE_E94DFBE9_60EF.jpg";

const adminGroups = [
  {
    label: "Text2SQL",
    description: "数据源、语义配置、知识与调试",
    items: [
      {
        to: "/admin/text2sql/connection",
        matchPrefix: "/admin/text2sql/connection",
        label: "数据连接",
        caption: "外部数据库",
      },
      {
        to: "/admin/text2sql/relation",
        matchPrefix: "/admin/text2sql/relation",
        label: "表关系",
        caption: "关系白名单",
      },
      {
        to: "/admin/text2sql/annotations",
        matchPrefix: "/admin/text2sql/annotations",
        label: "字段注释",
        caption: "语义补充",
      },
      {
        to: "/admin/text2sql/code-dict",
        matchPrefix: "/admin/text2sql/code-dict",
        label: "码值字典",
        caption: "枚举映射",
      },
      {
        to: "/admin/text2sql/qa",
        matchPrefix: "/admin/text2sql/qa",
        label: "QA 调试",
        caption: "链路验证",
      },
    ],
  },
  {
    label: "文档问答",
    description: "文档知识库、表格语义树与问答调试",
    items: [
      {
        to: "/admin/document-qa/document-upload",
        matchPrefix: "/admin/document-qa/document-upload",
        label: "普通文档处理与上传",
        caption: "解析docx等无结构文档",
      },
      {
        to: "/admin/document-qa/upload",
        matchPrefix: "/admin/document-qa/upload",
        label: "高基表解析与上传",
        caption: "处理高基表",
      },
      {
        to: "/admin/document-qa/debug",
        matchPrefix: "/admin/document-qa/debug",
        label: "问答调试",
        caption: "检索与回答验证",
      },
    ],
  },
  {
    label: "数据问答平台功能管理",
    description: "功能配置及数据管理",
    items: [
      {
        to: "/admin/model-config",
        matchPrefix: "/admin/model-config",
        label: "模型运行配置",
        caption: "Provider 与密钥",
      },
      {
        to: "/admin/model-config/knowledge",
        matchPrefix: "/admin/model-config/knowledge",
        label: "知识库",
        caption: "文档与表格",
      },
    ],
  },
];

const expandedGroups = reactive({
  Text2SQL: true,
  文档问答: true,
  模型配置: true,
});

const isStandaloneRoute = computed(() => route.meta.layout === "standalone");
const currentTitle = computed(() => route.meta.title || "后台管理");
const currentSection = computed(() => route.meta.section || "Admin");
const currentUserName = computed(() => userState?.user?.name || "已登录用户");
const activeNavItem = computed(() => (
  adminGroups
    .flatMap((group) => group.items)
    .filter((item) => (
      route.path === item.to || route.path.startsWith(`${item.matchPrefix}/`)
    ))
    .sort((left, right) => right.matchPrefix.length - left.matchPrefix.length)[0] || null
));
const currentGroup = computed(() => (
  adminGroups.find((group) => group.items.some((item) => isActiveNav(item))) || null
));
const currentItem = computed(() => (
  currentGroup.value?.items.find((item) => isActiveNav(item)) || null
));
const currentGroupDescription = computed(() => (
  currentGroup.value?.description || "集中配置数据连接、知识处理与问答链路"
));
const currentItemCaption = computed(() => (
  currentItem.value?.caption || "选择左侧功能开始管理"
));
const relatedItems = computed(() => (
  (currentGroup.value?.items || [])
    .filter((item) => item.to !== currentItem.value?.to)
    .slice(0, 3)
));

function isActiveNav(item) {
  return activeNavItem.value?.to === item.to;
}

function isGroupExpanded(label) {
  return expandedGroups[label] !== false;
}

function toggleGroup(label) {
  expandedGroups[label] = !isGroupExpanded(label);
}
</script>

<style scoped>
.admin-shell {
  min-height: 100dvh;
  display: grid;
  grid-template-columns: 272px minmax(0, 1fr);
  background:
    radial-gradient(circle at 18% 0%, rgba(255, 246, 247, 0.95), transparent 28rem),
    linear-gradient(180deg, #ffffff 0%, var(--bg-main) 44%, #eef1f6 100%);
}

.admin-sidebar {
  position: sticky;
  top: 0;
  height: 100dvh;
  display: flex;
  flex-direction: column;
  gap: 22px;
  padding: 18px 14px;
  border-right: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(18px);
  overflow-y: auto;
}

.brand-panel {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 8px 16px;
  border-bottom: 1px solid var(--line);
}

.brand-emblem {
  width: 42px;
  height: 42px;
  flex: 0 0 auto;
  object-fit: contain;
}

.brand-panel strong {
  display: block;
  color: var(--accent);
  font-size: 14px;
  line-height: 1.25;
  letter-spacing: 0;
}

.brand-panel small {
  display: block;
  margin-top: 2px;
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.2;
}

.sidebar-nav,
.nav-group {
  display: flex;
  flex-direction: column;
}

.sidebar-nav {
  gap: 20px;
}

.nav-group {
  gap: 6px;
}

.nav-group-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  width: 100%;
  min-height: 58px;
  padding: 9px 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.64);
  color: var(--text-main);
  text-align: left;
  cursor: pointer;
}

.nav-group-trigger:hover {
  border-color: rgba(var(--accent-rgb), 0.24);
  background: #ffffff;
}

.nav-group-trigger:active {
  transform: translateY(1px);
}

.nav-group-trigger strong {
  display: block;
  color: var(--text-main);
  font-size: 13px;
  font-weight: 720;
  line-height: 1.2;
  letter-spacing: 0;
}

.nav-group-trigger small {
  display: block;
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 560;
  line-height: 1.25;
}

.group-toggle {
  display: inline-grid;
  place-items: center;
  width: 24px;
  height: 24px;
  flex: 0 0 auto;
  border: 1px solid var(--line);
  border-radius: 7px;
  color: var(--accent);
  background: var(--accent-light);
  font-size: 15px;
  font-weight: 720;
  line-height: 1;
}

.nav-group-items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sidebar-link {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-height: 48px;
  padding: 9px 10px;
  border: 1px solid transparent;
  border-radius: 8px;
  color: var(--text-muted);
  text-decoration: none;
}

.sidebar-link span {
  color: inherit;
  font-size: 13px;
  font-weight: 680;
  line-height: 1.2;
}

.sidebar-link small {
  color: var(--text-soft);
  font-size: 12px;
  line-height: 1.2;
}

.sidebar-link:hover {
  border-color: var(--line);
  background: rgba(255, 255, 255, 0.74);
  color: var(--text-main);
}

.sidebar-link-active {
  border-color: rgba(var(--accent-rgb), 0.14);
  background: linear-gradient(90deg, rgba(var(--accent-rgb), 0.1), rgba(var(--accent-rgb), 0.04));
  color: var(--accent);
  box-shadow: inset 3px 0 0 var(--accent), var(--shadow-hairline);
}

.admin-content {
  min-width: 0;
  padding: 18px clamp(16px, 3vw, 36px) 48px;
}

.admin-header {
  max-width: 1480px;
  margin: 0 auto;
  padding: 8px 0 18px;
  border-bottom: 1px solid var(--line);
  display: grid;
  grid-template-columns: minmax(220px, 0.72fr) minmax(420px, 1.28fr);
  align-items: end;
  gap: clamp(28px, 5vw, 72px);
}

.section-kicker {
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 650;
}

.admin-header h1 {
  margin: 5px 0 0;
  color: var(--text-main);
  font-size: clamp(22px, 2.4vw, 34px);
  font-weight: 730;
  line-height: 1.08;
  letter-spacing: 0;
}

.admin-user-line {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
  color: var(--text-muted);
  font-size: 13px;
}

.admin-user-line a {
  color: var(--accent);
  font-weight: 680;
  text-decoration: none;
}

.admin-user-line a:hover {
  text-decoration: underline;
}

.header-context {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(180px, 0.8fr) minmax(260px, 1.2fr);
  gap: 24px;
  padding-left: clamp(20px, 3vw, 38px);
  border-left: 1px solid var(--line-strong);
}

.context-copy {
  min-width: 0;
}

.context-copy > span {
  display: block;
  margin-bottom: 7px;
  color: var(--accent);
  font-size: 11px;
  font-weight: 720;
  letter-spacing: 0.08em;
}

.context-copy strong {
  display: block;
  color: var(--text-main);
  font-size: 14px;
  font-weight: 700;
  line-height: 1.45;
}

.context-copy p {
  margin: 5px 0 0;
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.context-links {
  min-width: 0;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.context-links a {
  min-width: 0;
  padding: 10px 11px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.58);
  color: var(--text-main);
  text-decoration: none;
}

.context-links a:hover {
  border-color: rgba(var(--accent-rgb), 0.24);
  background: #ffffff;
  color: var(--accent);
  transform: translateY(-1px);
}

.context-links a:active {
  transform: translateY(1px);
}

.context-links span,
.context-links small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.context-links span {
  font-size: 12px;
  font-weight: 690;
}

.context-links small {
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 11px;
}

.page-wrap {
  max-width: 1480px;
  margin: 0 auto;
  padding-top: 20px;
}

.skip-link {
  position: fixed;
  top: 12px;
  left: 12px;
  z-index: 100;
  transform: translateY(-140%);
  padding: 8px 10px;
  border-radius: 8px;
  background: #17202a;
  color: #ffffff;
  text-decoration: none;
  transition: transform 160ms ease;
}

.skip-link:focus {
  transform: translateY(0);
}

@media (prefers-reduced-motion: no-preference) {
  .header-context {
    animation: context-enter 360ms cubic-bezier(0.16, 1, 0.3, 1) both;
  }

  @keyframes context-enter {
    from {
      opacity: 0;
      transform: translateY(6px);
    }

    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
}

@media (max-width: 1180px) {
  .admin-header {
    grid-template-columns: 1fr;
    align-items: start;
    gap: 18px;
  }

  .header-context {
    grid-template-columns: minmax(180px, 0.7fr) minmax(0, 1.3fr);
    padding: 16px 0 0;
    border-top: 1px solid var(--line);
    border-left: none;
  }
}

@media (max-width: 900px) {
  .admin-shell {
    grid-template-columns: 1fr;
  }

  .admin-sidebar {
    position: relative;
    height: auto;
    border-right: none;
    border-bottom: 1px solid var(--line);
  }

  .sidebar-nav {
    display: grid;
    grid-template-columns: 1fr;
  }

  .nav-group {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .nav-group-trigger,
  .nav-group-items {
    grid-column: 1 / -1;
  }
}

@media (max-width: 560px) {
  .admin-content {
    padding-inline: 14px;
  }

  .nav-group {
    grid-template-columns: 1fr;
  }

  .header-context {
    grid-template-columns: 1fr;
    gap: 14px;
  }

  .context-links {
    grid-template-columns: 1fr;
  }
}
</style>

import { createRouter, createWebHistory } from "vue-router";

import ExternalDbPage from "../pages/ExternalDbPage.vue";
import ChatPage from "../pages/ChatPage.vue";
import QaPage from "../pages/QaPage.vue";
import KnowledgeBasePage from "../pages/KnowledgeBasePage.vue";
import KnowledgeBaseDetailPage from "../pages/KnowledgeBaseDetailPage.vue";
import RelationPage from "../pages/RelationPage.vue";
import SchemaAnnotationPage from "../pages/SchemaAnnotationPage.vue";
import CodeDictPage from "../pages/CodeDictPage.vue";
import ModelConfigPage from "../pages/ModelConfigPage.vue";

const adminMeta = {
  layout: "admin",
  requiresAdmin: true,
};

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      redirect: "/chat",
    },
    {
      path: "/chat",
      name: "chat",
      component: ChatPage,
      meta: { layout: "standalone", title: "数据问答", section: "Chat" },
    },
    {
      path: "/admin",
      redirect: "/admin/text2sql/connection",
    },
    {
      path: "/admin/text2sql/connection",
      name: "admin-text2sql-connection",
      component: ExternalDbPage,
      meta: { ...adminMeta, title: "数据连接", section: "Text2SQL" },
    },
    {
      path: "/admin/text2sql/relation",
      name: "admin-text2sql-relation",
      component: RelationPage,
      meta: { ...adminMeta, title: "表关系配置", section: "Text2SQL" },
    },
    {
      path: "/admin/text2sql/annotations",
      name: "admin-text2sql-annotations",
      component: SchemaAnnotationPage,
      meta: { ...adminMeta, title: "字段注释导入", section: "Text2SQL" },
    },
    {
      path: "/admin/text2sql/code-dict",
      name: "admin-text2sql-code-dict",
      component: CodeDictPage,
      meta: { ...adminMeta, title: "码值字典导入", section: "Text2SQL" },
    },
    {
      path: "/admin/text2sql/knowledge",
      name: "admin-text2sql-knowledge",
      component: KnowledgeBasePage,
      meta: { ...adminMeta, title: "知识库管理", section: "Text2SQL" },
    },
    {
      path: "/admin/text2sql/knowledge/:kbId",
      name: "admin-text2sql-knowledge-detail",
      component: KnowledgeBaseDetailPage,
      meta: { ...adminMeta, title: "知识库文件管理", section: "Text2SQL" },
    },
    {
      path: "/admin/text2sql/qa",
      name: "admin-text2sql-qa",
      component: QaPage,
      meta: { ...adminMeta, title: "QA 调试", section: "Text2SQL" },
    },
    {
      path: "/admin/model-config",
      name: "admin-model-config",
      component: ModelConfigPage,
      meta: { ...adminMeta, title: "模型配置", section: "模型配置" },
    },
    {
      path: "/settings",
      redirect: "/admin/text2sql/connection",
    },
    {
      path: "/connection",
      redirect: "/admin/text2sql/connection",
    },
    {
      path: "/models",
      redirect: "/admin/model-config",
    },
    {
      path: "/relation",
      redirect: "/admin/text2sql/relation",
    },
    {
      path: "/annotations",
      redirect: "/admin/text2sql/annotations",
    },
    {
      path: "/code-dict",
      redirect: "/admin/text2sql/code-dict",
    },
    {
      path: "/qa",
      redirect: "/admin/text2sql/qa",
    },
    {
      path: "/knowledge",
      redirect: "/admin/text2sql/knowledge",
    },
    {
      path: "/knowledge/:kbId",
      redirect: (to) => `/admin/text2sql/knowledge/${to.params.kbId}`,
    },
  ],
});

export default router;

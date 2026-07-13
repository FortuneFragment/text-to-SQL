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
import DocumentQaPage from "../pages/DocumentQaPage.vue";
import DocumentUploadPage from "../pages/DocumentUploadPage.vue";
import LoginPage from "../pages/LoginPage.vue";

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
      path: "/login",
      name: "login",
      component: LoginPage,
      meta: { layout: "standalone", title: "统一身份认证", public: true },
    },
    {
      path: "/chat",
      name: "chat",
      component: ChatPage,
      meta: { layout: "standalone", title: "智能问答", section: "Chat" },
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
      path: "/admin/text2sql/qa",
      name: "admin-text2sql-qa",
      component: QaPage,
      meta: { ...adminMeta, title: "QA 调试", section: "Text2SQL" },
    },
    {
      path: "/admin/document-qa",
      redirect: "/admin/document-qa/document-upload",
    },
    {
      path: "/admin/document-qa/document-upload",
      name: "admin-document-qa-document-upload",
      component: DocumentUploadPage,
      meta: { ...adminMeta, title: "普通文档处理与上传", section: "文档问答" },
    },
    {
      path: "/admin/document-qa/upload",
      name: "admin-document-qa-upload",
      component: DocumentQaPage,
      props: { mode: "upload" },
      meta: { ...adminMeta, title: "高基表解析与上传", section: "文档问答" },
    },
    {
      path: "/admin/document-qa/debug",
      name: "admin-document-qa-debug",
      component: DocumentQaPage,
      props: { mode: "debug" },
      meta: { ...adminMeta, title: "问答调试", section: "文档问答" },
    },
    {
      path: "/admin/model-config",
      name: "admin-model-config",
      component: ModelConfigPage,
      meta: { ...adminMeta, title: "模型配置", section: "模型配置" },
    },
    {
      path: "/admin/model-config/knowledge",
      name: "admin-model-config-knowledge",
      component: KnowledgeBasePage,
      meta: { ...adminMeta, title: "知识库管理", section: "模型配置" },
    },
    {
      path: "/admin/model-config/knowledge/:kbId",
      name: "admin-model-config-knowledge-detail",
      component: KnowledgeBaseDetailPage,
      meta: { ...adminMeta, title: "知识库文件管理", section: "模型配置" },
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
      redirect: "/admin/model-config/knowledge",
    },
    {
      path: "/knowledge/:kbId",
      redirect: (to) => `/admin/model-config/knowledge/${to.params.kbId}`,
    },
    {
      path: "/admin/text2sql/knowledge",
      redirect: "/admin/model-config/knowledge",
    },
    {
      path: "/admin/text2sql/knowledge/:kbId",
      redirect: (to) => `/admin/model-config/knowledge/${to.params.kbId}`,
    },
    {
      path: "/admin/document-qa/knowledge",
      redirect: "/admin/model-config/knowledge",
    },
    {
      path: "/admin/document-qa/knowledge/:kbId",
      redirect: (to) => `/admin/model-config/knowledge/${to.params.kbId}`,
    },
    {
      path: "/document-qa",
      redirect: "/admin/document-qa/document-upload",
    },
  ],
});

export default router;

import { createRouter, createWebHistory } from "vue-router";

import ExternalDbPage from "../pages/ExternalDbPage.vue";
import TableSwitchPage from "../pages/TableSwitchPage.vue";
import FieldSwitchPage from "../pages/FieldSwitchPage.vue";
import QaPage from "../pages/QaPage.vue";
import KnowledgeBasePage from "../pages/KnowledgeBasePage.vue";
import KnowledgeBaseDetailPage from "../pages/KnowledgeBaseDetailPage.vue";
import RelationPage from "../pages/RelationPage.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      redirect: "/qa",
    },
    {
      path: "/settings",
      redirect: "/connection",
    },
    {
      path: "/connection",
      name: "connection",
      component: ExternalDbPage,
    },
    {
      path: "/table",
      name: "table",
      component: TableSwitchPage,
    },
    {
      path: "/field",
      name: "field",
      component: FieldSwitchPage,
    },
    {
      path: "/relation",
      name: "relation",
      component: RelationPage,
    },
    {
      path: "/qa",
      name: "qa",
      component: QaPage,
    },
    {
      path: "/knowledge",
      name: "knowledge",
      component: KnowledgeBasePage,
    },
    {
      path: "/knowledge/:kbId",
      name: "knowledge-detail",
      component: KnowledgeBaseDetailPage,
    },
  ],
});

export default router;

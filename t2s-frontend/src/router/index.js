import { createRouter, createWebHistory } from "vue-router";

import ExternalDbPage from "../pages/ExternalDbPage.vue";
import TableSwitchPage from "../pages/TableSwitchPage.vue";
import FieldSwitchPage from "../pages/FieldSwitchPage.vue";
import QaPage from "../pages/QaPage.vue";

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
      path: "/qa",
      name: "qa",
      component: QaPage,
    },
  ],
});

export default router;

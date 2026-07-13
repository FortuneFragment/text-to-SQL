import { createApp, reactive } from "vue";

import App from "./App.vue";
import router from "./router";
import "./style.css";
import { API_BASE, apiRequest } from "./api/client.js";

const state = reactive({
  user: null,
});

function redirectToAuthentication(nextPath) {
  if (import.meta.env.DEV) {
    const query = new URLSearchParams({ next: nextPath });
    window.location.href = `/login?${query.toString()}`;
    return;
  }

  const next = encodeURIComponent(nextPath);
  window.location.href = `${API_BASE}/auth/login?next=${next}`;
}

async function loadCurrentUser() {
  try {
    const data = await apiRequest("/auth/me");
    return data;
  } catch (error) {
    if (error.status === 401) {
      redirectToAuthentication(
        `${window.location.pathname}${window.location.search}${window.location.hash}`,
      );
    }
    throw error;
  }
}

async function init() {
  const initialRoute = router.resolve(
    `${window.location.pathname}${window.location.search}${window.location.hash}`,
  );

  if (!initialRoute.meta.public) {
    try {
      state.user = await loadCurrentUser();
    } catch (e) {
      console.error("Failed to load user:", e);
      return;
    }
  }

  router.beforeEach((to, from, next) => {
    if (to.meta.public) {
      next();
      return;
    }

    if (!state.user) {
      redirectToAuthentication(to.fullPath || "/chat");
      return;
    }

    const isAdmin = state.user?.permissions?.includes("admin:access");
    if (to.meta.requiresAdmin && !isAdmin) {
      next("/chat");
    } else {
      next();
    }
  });

  const app = createApp(App);
  app.provide("userState", state);
  app.use(router).mount("#app");
}

init();

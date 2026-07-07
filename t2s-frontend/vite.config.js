import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

const proxyTarget = process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8000";

function createApiProxy() {
  return {
    "/api": {
      target: proxyTarget,
      changeOrigin: true,
      configure(proxy) {
        proxy.on("error", (error, request) => {
          const method = request?.method || "GET";
          const url = request?.url || "/api";
          console.error(`[vite proxy] ${method} ${url} -> ${proxyTarget} failed: ${error.message}`);
        });
      },
    },
  };
}

export default defineConfig({
  plugins: [vue()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: createApiProxy(),
  },
  preview: {
    host: "0.0.0.0",
    port: 4173,
    proxy: createApiProxy(),
  },
});

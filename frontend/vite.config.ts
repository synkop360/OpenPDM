import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";
import { API_PROXY_PATHS } from "./src/apiRoutes";

export default defineConfig(({ mode }) => {
  const environment = loadEnv(mode, ".", "");
  const apiProxyTarget = environment.VITE_API_PROXY_TARGET || "http://localhost:18000";

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: Object.fromEntries(
        API_PROXY_PATHS.map((path) => [path, apiProxyTarget]),
      ),
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: "./src/test/setup.ts",
    },
  };
});

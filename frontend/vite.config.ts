import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const environment = loadEnv(mode, ".", "");
  const apiProxyTarget = environment.VITE_API_PROXY_TARGET || "http://localhost:8000";

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: Object.fromEntries(
        [
          "/health",
          "/foundation",
          "/auth",
          "/organizations",
          "/projects",
          "/assets",
          "/revisions",
          "/blobs",
          "/metadata",
          "/notifications",
          "/search",
          "/plugins",
          "/platform",
        ].map((path) => [path, apiProxyTarget]),
      ),
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: "./src/test/setup.ts",
    },
  };
});

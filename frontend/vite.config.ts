import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";
import { configDefaults } from "vitest/config";
import { API_PROXY_PATHS } from "./src/apiRoutes";

export default defineConfig(({ mode }) => {
  const environment = loadEnv(mode, ".", "");
  const apiProxyTarget = environment.VITE_API_PROXY_TARGET || "http://localhost:18000";

  return {
    plugins: [react()],
    server: {
      port: 5173,
      // Every path below is also a prefix the Web UI's own client-side routes can use
      // (e.g. /projects/:id/:tab). A browser page navigation (hard refresh, bookmark,
      // direct URL) must fall through to the SPA shell instead of being proxied to the
      // backend, while fetch()/XHR API calls continue to be proxied as normal. See
      // ADR-0050 (Adopt Asset-Addressable Deep-Linking URL Scheme).
      proxy: Object.fromEntries(
        API_PROXY_PATHS.map((path) => [
          path,
          {
            target: apiProxyTarget,
            bypass(req: { headers: { accept?: string } }) {
              if (req.headers.accept?.includes("text/html")) {
                return "/index.html";
              }
            },
          },
        ]),
      ),
    },
    preview: {
      proxy: {},
    },
    test: {
      environment: "jsdom",
      exclude: [...configDefaults.exclude, "e2e/**"],
      globals: true,
      setupFiles: "./src/test/setup.ts",
    },
  };
});

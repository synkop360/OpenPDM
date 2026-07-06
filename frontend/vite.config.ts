import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/health": "http://localhost:18000",
      "/foundation": "http://localhost:18000",
      "/auth": "http://localhost:18000",
      "/organizations": "http://localhost:18000",
      "/projects": "http://localhost:18000",
      "/assets": "http://localhost:18000",
      "/revisions": "http://localhost:18000",
      "/blobs": "http://localhost:18000",
      "/metadata": "http://localhost:18000",
      "/search": "http://localhost:18000",
      "/plugins": "http://localhost:18000"
    }
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts"
  }
});

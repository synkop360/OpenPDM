import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/health": "http://localhost:8000",
      "/foundation": "http://localhost:8000",
      "/auth": "http://localhost:8000",
      "/organizations": "http://localhost:8000",
      "/projects": "http://localhost:8000",
      "/assets": "http://localhost:8000",
      "/revisions": "http://localhost:8000",
      "/blobs": "http://localhost:8000",
      "/metadata": "http://localhost:8000",
      "/search": "http://localhost:8000",
      "/plugins": "http://localhost:8000"
    }
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts"
  }
});

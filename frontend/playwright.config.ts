import { defineConfig, devices } from "@playwright/test";

const viewports = [
  { name: "mobile-390", width: 390, height: 844 },
  { name: "tablet-768", width: 768, height: 1024 },
  { name: "desktop", width: 1440, height: 1000 },
];

export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  webServer: {
    command: "pnpm.cmd build && pnpm.cmd exec vite preview --host 127.0.0.1 --port 4173",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "retain-on-failure",
  },
  projects: [
    ...viewports.map((viewport) => ({
      name: `chromium-${viewport.name}`,
      use: { ...devices["Desktop Chrome"], viewport: { width: viewport.width, height: viewport.height } },
    })),
    ...viewports.map((viewport) => ({
      name: `firefox-${viewport.name}`,
      use: { ...devices["Desktop Firefox"], viewport: { width: viewport.width, height: viewport.height } },
    })),
    ...viewports.map((viewport) => ({
      name: `webkit-${viewport.name}`,
      use: { ...devices["Desktop Safari"], viewport: { width: viewport.width, height: viewport.height } },
    })),
  ],
});

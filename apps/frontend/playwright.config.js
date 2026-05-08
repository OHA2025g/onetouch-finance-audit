// @ts-check
const { defineConfig, devices } = require("@playwright/test");

// Docker compose maps frontend to :5175 (nginx) by default
const baseURL = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:5175";

module.exports = defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  reporter: [["html", { open: "never" }], ["list"]],
});


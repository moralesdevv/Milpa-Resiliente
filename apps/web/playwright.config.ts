import { defineConfig, devices } from "@playwright/test";

// A pre-installed Chromium can be used when `npx playwright install` is not possible:
//   PLAYWRIGHT_CHROMIUM_EXECUTABLE=C:\path\to\chrome.exe npm run web:test:e2e
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined;

export default defineConfig({
  // Interface-state tests live in apps/web/e2e; acceptance tests (T-A) in tests/acceptance.
  testDir: "../..",
  testMatch: ["apps/web/e2e/**/*.spec.ts", "tests/acceptance/**/*.spec.ts"],
  testIgnore: ["**/node_modules/**", "**/references/**"],
  // The mock keeps in-memory state, so tests run one at a time and reset it.
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  timeout: 45_000,
  expect: { timeout: 7_000 },
  use: {
    baseURL: "http://localhost:5175",
    trace: "retain-on-failure",
    locale: "es-GT",
    ...devices["Desktop Chrome"],
    launchOptions: executablePath ? { executablePath } : {},
  },
  webServer: {
    command: "npm run dev:mock -- --host localhost --port 5175",
    url: "http://localhost:5175",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});

import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["src/**/*.test.{ts,tsx}"],
    exclude: ["src/lint/copy-linter.test.ts"],
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    restoreMocks: true,
  },
});

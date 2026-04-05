import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // Unit tests: engine.test.ts (mocked fetch, fast)
    // Integration tests: integration.test.ts (real server, separate run)
    include: ["tests/engine.test.ts"],
  },
});

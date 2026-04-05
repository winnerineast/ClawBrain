import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests/integration.test.ts"],
    globalSetup: ["tests/global-setup.ts"],
    testTimeout: 30_000,   // server startup + each test
    hookTimeout: 20_000,
    pool: "forks",         // global-setup runs once, all tests share the server
    poolOptions: { forks: { singleFork: true } },
  },
});

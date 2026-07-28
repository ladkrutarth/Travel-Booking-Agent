import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 90000,
  use: {
    baseURL: "http://127.0.0.1:3000",
    headless: true,
  },
});

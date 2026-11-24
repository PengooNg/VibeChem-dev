// SPDX-License-Identifier: GPL-3.0-or-later
// app/playwright.config.ts — end-to-end tests of the desktop app in Electron mode (`pnpm e2e`).
//
// `pnpm e2e` builds main + preload first; Playwright serves the renderer with Vite and each
// test launches Electron, which starts the dev engine (main/engine.ts, needs `uv sync`).
import { defineConfig } from "@playwright/test";

export const RENDERER_PORT = 5179;

export default defineConfig({
  testDir: "e2e",
  timeout: 120_000, // first engine start imports numpy, pyarrow and FastAPI
  workers: 1,
  retries: process.env["CI"] ? 1 : 0,
  reporter: process.env["CI"] ? [["list"], ["html", { open: "never" }]] : "list",
  use: { trace: "retain-on-failure" },
  webServer: {
    command: `vite --config e2e/vite.renderer.config.ts --port ${String(RENDERER_PORT)} --strictPort`,
    url: `http://localhost:${String(RENDERER_PORT)}`,
    reuseExistingServer: !process.env["CI"],
  },
});

// SPDX-License-Identifier: GPL-3.0-or-later
// app/vitest.config.ts — unit/component tests for the renderer (jsdom).
import { resolve } from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": resolve(import.meta.dirname, "renderer/src") } },
  test: {
    environment: "jsdom",
    include: ["renderer/src/**/*.test.{ts,tsx}"],
  },
});

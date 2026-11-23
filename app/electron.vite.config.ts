// SPDX-License-Identifier: GPL-3.0-or-later
// app/electron.vite.config.ts — build config for the Electron main process and the React renderer.
import { resolve } from "node:path";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "electron-vite";

export default defineConfig({
  main: {
    build: {
      rollupOptions: {
        input: { index: resolve(import.meta.dirname, "main/index.ts") },
      },
    },
  },
  renderer: {
    root: resolve(import.meta.dirname, "renderer"),
    resolve: {
      alias: { "@": resolve(import.meta.dirname, "renderer/src") },
    },
    plugins: [react(), tailwindcss()],
    build: {
      // Ship every asset (fonts included) as a file: the CSP allows `font-src 'self'`, not data: URIs.
      assetsInlineLimit: 0,
      rollupOptions: {
        input: { index: resolve(import.meta.dirname, "renderer/index.html") },
      },
    },
  },
});

// SPDX-License-Identifier: GPL-3.0-or-later
// app/main/index.ts — Electron main process: opens the app window.
import { join } from "node:path";

import { app, BrowserWindow } from "electron";

function createWindow(): void {
  const window = new BrowserWindow({
    width: 1280,
    height: 800,
    show: false,
    webPreferences: {
      // TECH_STACK.md §10: the renderer is sandboxed and has no Node.js access.
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
    },
  });
  // TECH_STACK.md §10: never load remote URLs — no new windows, no navigation away from the app.
  window.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  window.webContents.on("will-navigate", (event) => {
    event.preventDefault();
  });
  window.once("ready-to-show", () => {
    window.show();
  });

  // electron-vite sets ELECTRON_RENDERER_URL to the Vite dev server in `pnpm dev`.
  const devServerUrl = process.env["ELECTRON_RENDERER_URL"];
  if (!app.isPackaged && devServerUrl) {
    void window.loadURL(devServerUrl);
  } else {
    void window.loadFile(join(import.meta.dirname, "../renderer/index.html"));
  }
}

void app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

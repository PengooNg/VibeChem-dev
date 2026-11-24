// SPDX-License-Identifier: GPL-3.0-or-later
// app/main/index.ts — Electron main process: starts the engine and opens the app window.
import { dirname, join } from "node:path";

import { app, BrowserWindow, ipcMain } from "electron";

import { type DevEngine, startDevEngine } from "./engine";

let engine: DevEngine | null = null;

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
      preload: join(import.meta.dirname, "../preload/index.cjs"),
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
  // In development the app folder is `app/` inside the repository and the engine runs from
  // the repository's uv environment. The packaged engine comes in T0.11.
  if (!app.isPackaged) {
    engine = startDevEngine(dirname(app.getAppPath()));
    engine.connection.catch((error: unknown) => {
      console.error("[engine]", error);
    });
  }
  ipcMain.handle("engine:connection", () =>
    engine === null
      ? Promise.reject(new Error("no engine in packaged builds before T0.11"))
      : engine.connection,
  );
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("will-quit", () => {
  engine?.stop();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

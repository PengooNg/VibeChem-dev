// SPDX-License-Identifier: GPL-3.0-or-later
// app/main/index.ts — Electron main process: starts the engine and opens the app window.
import { dirname, join } from "node:path";
import { pathToFileURL } from "node:url";

import { app, BrowserWindow, ipcMain, net, protocol } from "electron";

import { APP_ORIGIN, APP_SCHEME, isTrustedSenderUrl, resolveAppFile } from "./appOrigin";
import { devEngineCommand, type Engine, packagedEngineCommand, startEngine } from "./engine";

let engine: Engine | null = null;

// electron-vite sets ELECTRON_RENDERER_URL to the Vite dev server in `pnpm dev` (and the e2e
// config sets it to its own Vite server). Never used by the packaged app.
const devServerUrl = app.isPackaged ? null : (process.env["ELECTRON_RENDERER_URL"] ?? null);

// `app:` behaves like https (standard + secure), so the page origin is `app://vibechem`.
// Must be registered before the app is ready.
protocol.registerSchemesAsPrivileged([
  { scheme: APP_SCHEME, privileges: { standard: true, secure: true, supportFetchAPI: true } },
]);

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

  void window.loadURL(devServerUrl ?? `${APP_ORIGIN}/index.html`);
}

void app.whenReady().then(() => {
  // Step 1: serve the built renderer (out/renderer) from app://vibechem/.
  const rendererDir = join(import.meta.dirname, "../renderer");
  protocol.handle(APP_SCHEME, (request) => {
    const file = resolveAppFile(rendererDir, request.url);
    if (file === null) return new Response(null, { status: 404 });
    return net.fetch(pathToFileURL(file).toString());
  });

  // Step 2: start the engine — the bundled one in the packaged app, else the repository's
  // uv environment (the app folder is `app/` inside the repository).
  engine = startEngine(
    app.isPackaged
      ? packagedEngineCommand(process.resourcesPath, process.platform, process.env)
      : devEngineCommand(dirname(app.getAppPath()), process.platform, process.env),
  );
  engine.connection.catch((error: unknown) => {
    console.error("[engine]", error);
  });

  // Step 3: hand port + token only to our own page (TECH_STACK.md §10).
  ipcMain.handle("engine:connection", (event) => {
    const senderUrl = event.senderFrame?.url ?? "";
    if (!isTrustedSenderUrl(senderUrl, devServerUrl)) {
      return Promise.reject(new Error("engine:connection refused for an untrusted page"));
    }
    return engine === null ? Promise.reject(new Error("engine not started")) : engine.connection;
  });

  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("will-quit", () => {
  engine?.stop();
});
// Also when the main process ends without a normal quit (e.g. electron-vite restarting it after
// a main/ change). A hard kill of the main process still leaves the engine running.
process.on("exit", () => {
  engine?.stop();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

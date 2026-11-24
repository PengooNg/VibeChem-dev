// SPDX-License-Identifier: GPL-3.0-or-later
// app/main/preload.ts — the renderer's only bridge to the main process (TECH_STACK.md §10).
//
// Sandboxed preload: bundled as CommonJS and limited to Electron's renderer modules.
import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("vibechem", {
  /** Port + session token of the local engine (DATA_MODEL.md §1). */
  engine: (): Promise<unknown> => ipcRenderer.invoke("engine:connection"),
});

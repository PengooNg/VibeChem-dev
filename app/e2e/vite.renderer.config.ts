// SPDX-License-Identifier: GPL-3.0-or-later
// app/e2e/vite.renderer.config.ts — the renderer part of electron.vite.config.ts as a plain Vite config.
//
// The e2e tests serve the renderer with Vite (`electron-vite dev` would also start its own
// Electron) and launch Electron themselves. A dev-server page keeps an `http://localhost:<port>`
// origin, which the dev-mode engine accepts (DATA_MODEL.md §1 "Origin check").
import config from "../electron.vite.config";

export default config.renderer;

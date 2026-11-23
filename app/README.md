<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

# VibeChem app (`app/`)

**Status:** stub. The pnpm workspace is set up in T0.04.

**Purpose:** the desktop app.

- `main/`: Electron main process and preload (TypeScript). It starts and stops the engine and holds no business logic.
- `renderer/src/`: React + TypeScript UI (canvas, inspector, plots, jobs, library, state, ui, i18n `en`/`ja`/`vi`).
- `e2e/`: Playwright end-to-end tests.

**Allowed dependencies** (TECH_STACK.md §3.1): the renderer talks to the engine **only through the HTTP/WS API** and never uses Node.js APIs (it is sandboxed). `main/` uses Electron and child-process control of the engine.

**Tests:** Vitest next to the code (T0.04), Playwright in `e2e/` (from T0.10).

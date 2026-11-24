<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

# VibeChem app (`app/`)

**Status:** walking skeleton (T0.10, T0.11). The app starts the engine, shows a fixed Dataset → SNV pipeline, and Run plots the gasoline NIR spectra raw and after SNV. This works in development and in the installers for Windows, macOS and Linux.

**Purpose:** the desktop app.

- `main/`: Electron main process and preload (TypeScript). It starts and stops the engine and holds no business logic. `engine.ts` runs `python -m vibechem_engine.api` from the repository's `.venv` in development (dev mode, `VIBECHEM_DEV=1`), or the bundled PyInstaller engine `<resources>/engine/vibechem-engine` in the packaged app, and reads its port + token; `index.ts` hands them over IPC only to the app's own page; `preload.ts` (bundled as CommonJS because the renderer is sandboxed) exposes them as `window.vibechem.engine()`. Outside the Vite dev server the built renderer is served from `app://vibechem` (`appOrigin.ts`), the origin the engine accepts.
- `renderer/src/`: React + TypeScript UI (canvas, inspector, plots, jobs, library, state, ui, i18n `en`/`ja`/`vi`).
- `e2e/`: Playwright end-to-end tests.

**Allowed dependencies** (TECH_STACK.md §3.1): the renderer talks to the engine **only through the HTTP/WS API** and never uses Node.js APIs (it is sandboxed). `main/` uses Electron and child-process control of the engine.

## Commands (from the repo root)

| Command                                            | What it does                                                        |
| -------------------------------------------------- | ------------------------------------------------------------------- |
| `pnpm --dir app install`                           | Install dependencies (also downloads the Electron binary)           |
| `pnpm --dir app dev`                               | Vite dev server + Electron window with hot reload                   |
| `pnpm --dir app dev:cdp`                           | Same, with the Chrome DevTools Protocol on port 9339 (visual check) |
| `pnpm --dir app build`                             | Build main and renderer into `app/out/`                             |
| `pnpm --dir app lint`                              | ESLint + Prettier check                                             |
| `pnpm --dir app typecheck`                         | TypeScript (strict) for main and renderer                           |
| `pnpm --dir app test`                              | Vitest                                                              |
| `uv run python scripts/check.py --fast --only app` | lint + typecheck + tests, as one health summary                     |
| `pnpm --dir app e2e`                               | Build main + preload, serve the renderer, run Playwright (Electron) |
| `pnpm --dir app gen:api`                           | Regenerate `renderer/src/api/schema.d.ts` from the engine OpenAPI   |
| `uv run python scripts/build_engine.py`            | Freeze the engine with PyInstaller into `build/engine/`             |
| `pnpm --dir app dist`                              | Build the installers into `app/dist/` (needs the frozen engine)     |

pnpm is pinned in `package.json` (`packageManager`). Run `corepack install -g pnpm@<that version>` once per machine so `pnpm --dir app …` from the repo root uses it (TECH_STACK.md §2).

## Layout

- `electron.vite.config.ts`: electron-vite config (main entry `main/index.ts`, renderer root `renderer/`, alias `@` = `renderer/src`).
- `electron-builder.yml`: installers (NSIS, dmg, AppImage + deb, unsigned). The engine bundle and `testdata/` go into the app's resources folder. Every npm package is a devDependency because electron-vite bundles them, so no `node_modules` ship.
- `renderer/src/ui/tokens.css`: design tokens from UI_GUIDE.md §2–3; `renderer/src/index.css` maps them to Tailwind and shadcn/ui names.
- `components.json`: shadcn/ui config (components go to `renderer/src/ui/components`).
- `renderer/src/i18n/{en,ja,vi}/common.json`: UI strings. Every key must exist in all three files (a Vitest test checks this).
- Fonts (Inter, JetBrains Mono, Noto Sans JP) come from `@fontsource-variable/*` and are bundled by Vite; nothing loads from the web.

## Visual check with Playwright CLI (CLAUDE.md §13.1)

1. `pnpm --dir app dev:cdp`
2. `pnpm --dir app exec playwright-cli attach --cdp=http://localhost:9339`, then
   `pnpm --dir app exec playwright-cli screenshot --filename=<path outside the repo>.png`, then `… detach`.
   Snapshots and logs land in `app/.playwright-cli/` (git-ignored).
3. Attach the screenshots to the PR. Don't commit them.

**Tests:** Vitest next to the code (`*.test.ts(x)`, renderer in jsdom, `main/` in node), Playwright in `e2e/`. The e2e tests serve the renderer with plain Vite (`e2e/vite.renderer.config.ts`, port 5179) and launch Electron themselves, so the page keeps a `http://localhost` origin that the dev-mode engine accepts. `pnpm dev` and `pnpm e2e` need `uv sync` first (the engine runs from `.venv`). `e2e/packaged.spec.ts` runs only when `VIBECHEM_PACKAGED_APP` points at a packaged executable (the installers workflow sets it); it checks that the packaged app runs the pipeline from `app://vibechem`.

**API types:** never hand-write engine field names (TECH_STACK.md §6). After changing an engine endpoint, run `pnpm --dir app gen:api` and commit `schema.d.ts`.

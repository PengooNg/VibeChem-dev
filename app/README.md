<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

# VibeChem app (`app/`)

**Status:** workspace set up (T0.04). The window shows only the app name in EN/JA/VI; the skeleton UI comes in T0.10.

**Purpose:** the desktop app.

- `main/`: Electron main process and preload (TypeScript). It starts and stops the engine and holds no business logic.
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

pnpm is pinned in `package.json` (`packageManager`). Run `corepack install -g pnpm@<that version>` once per machine so `pnpm --dir app …` from the repo root uses it (TECH_STACK.md §2).

## Layout

- `electron.vite.config.ts`: electron-vite config (main entry `main/index.ts`, renderer root `renderer/`, alias `@` = `renderer/src`).
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

**Tests:** Vitest next to the code (`*.test.tsx`), Playwright in `e2e/` (from T0.10).

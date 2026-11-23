# VibeChem — Progress log

> Written by Claude Code in every step PR (CLAUDE.md §6.9); newest rows first. Quan reads **Now** and **Needs you**.
> Live view between merges: the phase PR `[PHASE N] …` on GitHub, PRs labelled `needs-quan` / `paused`, or `/status`.

## Now
| Phase | Branch | Phase PR | Last merged step | Next step | Updated | Machine |
|---|---|---|---|---|---|---|
| 0 | `phase-0` | #8 | T0.05 | T0.06 | 2026-11-23 | laptop |

## Needs you
<!-- One line per open item: date · step · stop code · exact action · PR. Remove the line when resolved (move it to Stops with "resolved"). -->
- (none)

## Step log
| Date | Step | Result | PR | Size est → actual (cp) | Reuse decision | Notes |
|---|---|---|---|---|---|---|
| 2026-11-23 | T0.05 | `packages/native` (CMake + scikit-build-core 1.1.2 + nanobind 2.9.2, stable ABI cp312) built by `uv sync` on Windows (MSVC 14.52 / VS 2026, generator "Visual Studio 18 2026"); stub `row_mean(X, n_threads)` (std::jthread row blocks, GIL released); wrapper with NumPy fallback (`BACKEND`); 34 pytest equivalence/fallback tests; Catch2 v3.16.1 test via `-DVIBECHEM_BUILD_TESTS=ON` (4 cases, Release + Debug); `check.py --only native` | #11 | M → 4 | reuse — nanobind_example / nanobind packaging-guide config | Laptop has VS Community 2026, not VS 2022 Build Tools (TECH_STACK §1.1/§2 say 2022; works fine); nanobind 3.x is out but §1.4 says 2.x, so 2.9.2 pinned; stub reference lives in `vibechem_native/_reference.py` (no core counterpart); Catch2 not run by check.py or CI yet (T0.06); check.py crashes with UnicodeEncodeError (cp932 console) when printing failure output containing non-cp932 characters, workaround `PYTHONIOENCODING=utf-8` (pre-existing, not fixed) |
| 2026-11-23 | T0.04 | pnpm 10 workspace in `app/` (Electron 45.2.3, electron-vite 5, React 19.2, TS 6.0 strict, Tailwind 4.3, shadcn config, UI_GUIDE tokens, @fontsource fonts, i18next EN/JA/VI), ESLint 9 + Prettier + Vitest; `check.py --only app`; @playwright/test + @playwright/cli; playwright-cli skill and four Emil skills vendored; dev window screenshot via playwright-cli over CDP | #10 | M → 4 | reuse — electron-vite 5 (react-ts template layout), shadcn manual-install config, @fontsource-variable fonts | `shadcn init` cannot detect electron-vite, so components.json/theme were written from its manual guide; Electron 45 downloads its binary lazily, so `postinstall: install-electron` is needed for electron-vite; pnpm must be pinned per machine with `corepack install -g pnpm@10.34.9` (TECH_STACK §2); Node comes from fnm, which is not in the Bash profile — agents must `eval "$(fnm env --shell bash)"` before check.py; ESLint 9 is now marked deprecated on npm (ESLint 10 out) |
| 2026-11-23 | T0.03 | uv workspace (core, engine; Python 3.14.10), ruff, pyright strict, pytest, pre-commit (local ruff hooks); `scripts/check.py` with health summary; fresh clone on Windows passes | #9 | M → 3 | reuse — scientific-python/cookie settings + `uv_build` layout; build — `check.py` (stdlib, required by TASKS) | `scripts/tests/test_merge_step.py` reformatted by ruff (format only) and unittest-style rules PT009/PT027 ignored for `scripts/tests`; ruff excludes vendored `.claude/`; boundaries/reference/coverage lines SKIP until T0.07; CI does not run check.py until T0.06 |
| 2026-11-23 | T0.02 | skeleton tree, legal/community files, PR template, issue forms, 10 labels, `merge_step.py` (28 unit tests); HUMAN_STEP (Quan merges) | #7 | M → 4 | reuse — GPL-3.0 text already in repo (verbatim FSF), Keep-a-Changelog 1.1.0; build — `merge_step.py` (stdlib + `gh`, required by TASKS) | check.py not yet available (T0.03): tests run with `uv run --no-project python -m unittest discover -s scripts/tests`; CI smoke does not run them yet; CITATION.cff lacks ORCID and DOI (TODOs for Quan); ui-ux-pro-max vendored commit not recorded in THIRD_PARTY.md |
| 2026-11-23 | T0.01 | ci-smoke green on 3 OS; HUMAN_STEP (Quan merges) | #4 | S → 2 | reuse — existing `ci-smoke.yml` from PR #1 (actions/checkout, actions/setup-python) | PR #1 went straight to `main`; triggers narrowed to PRs/pushes on `main` and `phase-*`; check.py not yet available (T0.03); labels not yet created (T0.02) |

## Stops
| Date | Step | Code | What was needed | Resolved (date, how) |
|---|---|---|---|---|

## Phase gates
<!-- Gate report per CLAUDE.md §14.4: exit criteria + evidence, health summary, estimate accuracy, reuse ratio, ADR recommendations, QA §9.1 items, open issues, Quan's decision. -->

## K review backlog (until demo v0 = Beta)
| Step | PR | Area | What K should check | Done |
|---|---|---|---|---|
| T0.05 | #11 | C++ / build / dependency | `packages/native/CMakeLists.txt` (C++20, `/W4 /WX` and `-Wall -Wextra -Wpedantic -Werror`, kernels as static lib shared by extension and tests, `nanobind_add_module(_core STABLE_ABI NB_STATIC NB_SUPPRESS_WARNINGS)`); `pyproject.toml` pins (scikit-build-core==1.1.2, nanobind==2.9.2), `wheel.py-api = "cp312"`, `build-dir`, uv `cache-keys`; Catch2 v3.16.1 via FetchContent (network at test configure); `row_mean` threading (std::jthread blocks, determinism vs n_threads) and GIL release with `nb::call_guard`; output buffer allocated in Python; hand-written `_core.pyi`; fallback on ImportError only (no runtime fallback on kernel errors yet — DATA_MODEL `native.fallback` event comes later); no sanitizer/clang-tidy/clang-format config yet (T0.06 CI) | [ ] |
| T0.04 | #10 | build / dependency | `app/package.json` pins (exact versions, newest ≥ 2 weeks old) and `pnpm-lock.yaml`; `pnpm-workspace.yaml` (`onlyBuiltDependencies: esbuild`) and root `postinstall: install-electron`; electron-vite config and custom layout (`main/`, `renderer/`); `BrowserWindow` webPreferences + CSP meta (TECH_STACK §10) — no preload yet; tsconfig split (node/web); ESLint flat config; new deps beyond §1 names: electron-vite, clsx, tailwind-merge, @fontsource-variable/* (fonts), jsdom, eslint-plugin-react-hooks/-refresh, globals; `check.py` app area (pnpm via PATH, FAIL when pnpm/node_modules missing, merged summary lines) | [ ] |
| T0.03 | #9 | build / dependency | Root `pyproject.toml` (virtual uv workspace, ruff rule set, pyright strict scope incl. `scripts/`, pytest `--import-mode=importlib`, `filterwarnings=error`); `uv_build` backend pin `>=0.13.9,<0.14`; dev group (ruff, pyright[nodejs], pytest, pre-commit) and `uv.lock`; `.pre-commit-config.yaml` local hooks; `scripts/check.py` structure (areas, SKIP semantics, exit codes, log) | [ ] |
| T0.02 | #7 | CI / repo tooling | `scripts/merge_step.py` guards (base `phase-*`, not draft, checks `pass`/`skipping` and ≥ 1 check, title prefix, 👤 read from TASKS.md on the base branch, `--match-head-commit`, remote-only branch delete via `gh api` instead of `--delete-branch`); `.gitattributes` LF policy and binary list; `.gitignore`; `.github/CODEOWNERS`; package README stubs vs §3.1 boundaries | [ ] |
| T0.01 | #4 | CI | `ci-smoke.yml` triggers (`main`, `phase-*`), action versions (checkout@v5, setup-python@v5, Python 3.14); workflow to be deleted in T0.06 | [ ] |

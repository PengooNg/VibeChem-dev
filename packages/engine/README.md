<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# vibechem-engine (`vibechem_engine`)

**Status:** walking skeleton. `vibechem_engine.api` (T0.09) is the only code so far; the pipeline engine arrives in Phase 2.

**Purpose:** runs pipelines. It covers port types, the pipeline graph and file format, the compiler, cache, executor, scheduler, runners, projects, the local HTTP/WebSocket API and the CLI.

**Public API:**
- `python -m vibechem_engine.api [--testdata-dir PATH]` — start the HTTP API (DATA_MODEL.md §1 "Start-up"); `VIBECHEM_DEV=1` allows the Vite dev server origin. The desktop app ships this entry point frozen with PyInstaller (`scripts/build_engine.py` → `vibechem-engine[.exe]`; `__main__` calls `multiprocessing.freeze_support()` first).
- `vibechem_engine.api.create_app(token, *, testdata_dir, dev=False)` — the FastAPI app: `/api/v1/health`, `/api/v1/blocks` (static SNV entry), temporary `/api/v1/skeleton/run` (§2.12, removed in T4.01).

Later: the Python API and CLI (T2.11) and the rest of the HTTP/WS API in `docs/DATA_MODEL.md`.

**Allowed dependencies** (TECH_STACK.md §3.1): `vibechem_core`, numpy, loky, fastapi (+ starlette, pydantic), uvicorn, pyarrow. pyarrow has no type information; it is imported only in `api/arrow.py`, which turns off pyright's unknown-type checks for that file.
**Never imports:** renderer code.

**Tests:** `packages/engine/tests/`, which mirrors `src/vibechem_engine/`.

<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# vibechem-engine (`vibechem_engine`)

**Status:** stub. The package is set up in T0.03; the first code arrives in T0.09 (walking skeleton) and Phase 2.

**Purpose:** runs pipelines. It covers port types, the pipeline graph and file format, the compiler, cache, executor, scheduler, runners, projects, the local HTTP/WebSocket API and the CLI.

**Public API:** none yet. It will cover the Python API and CLI (T2.11) and the HTTP/WS API in `docs/DATA_MODEL.md`.

**Allowed dependencies** (TECH_STACK.md §3.1): `vibechem_core`, loky, fastapi, pyarrow.
**Never imports:** renderer code.

**Tests:** `packages/engine/tests/`, which mirrors `src/vibechem_engine/`.

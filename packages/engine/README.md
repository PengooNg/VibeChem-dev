<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# vibechem-engine (`vibechem_engine`)

**Status:** walking skeleton plus the first Phase 2 pieces: `vibechem_engine.api` (T0.09), `vibechem_engine.ports` (T2.01) and `vibechem_engine.graph` (T2.02).

**Purpose:** runs pipelines. It covers port types, the pipeline graph and file format, the compiler, cache, executor, scheduler, runners, projects, the local HTTP/WebSocket API and the CLI.

**Public API:**
- `python -m vibechem_engine.api [--testdata-dir PATH]` — start the HTTP API (DATA_MODEL.md §1 "Start-up"); `VIBECHEM_DEV=1` allows the Vite dev server origin. The desktop app ships this entry point frozen with PyInstaller (`scripts/build_engine.py` → `vibechem-engine[.exe]`; `__main__` calls `multiprocessing.freeze_support()` first).
- `vibechem_engine.api.schemas` (T1.03): pydantic models of the `GET /blocks/{block_id}` object (`BlockDetail`, parameter entries discriminated by `type`), i.e. DATA_MODEL.md §5 as a model; `BlockDetail.model_json_schema()` is its JSON Schema. Not yet served by a route.
- `vibechem_engine.ports` (T2.01): `PORT_TYPE_REGISTRY` (DATA_MODEL.md §4.1), `COMPATIBILITY` (§4.4), `is_compatible(from_type, to_type)`, `edge_rule(from_type, to_type)` (the conversion rule, `None` for equal types, `ValueError` for an incompatible pair), `port_types_payload()` (`GET /port-types` body). Unknown type names raise `ValueError`.
- `vibechem_engine.graph` (T2.02): `validate_graph(pipeline, registry)` checks a pipeline document (DATA_MODEL.md §2.6) against the blocks' ports and returns every §4.4 graph problem as a `GraphIssue` (`to_dict()` = one `POST …/validate` issue): `PIPELINE_PORT_TYPE_MISMATCH`, `PIPELINE_INPUT_MULTIPLE_EDGES`, `PIPELINE_REQUIRED_INPUT_MISSING`, `PIPELINE_CYCLE`. Unknown block, node or port and a repeated `node_id` raise `ValueError`.
- `vibechem_engine.api.create_app(token, *, testdata_dir, dev=False)` — the FastAPI app: `/api/v1/health`, `/api/v1/blocks` (static SNV entry), temporary `/api/v1/skeleton/run` (§2.12, removed in T4.01).

Later: the Python API and CLI (T2.11) and the rest of the HTTP/WS API in `docs/DATA_MODEL.md`.

**Allowed dependencies** (TECH_STACK.md §3.1): `vibechem_core`, numpy, loky, fastapi (+ starlette, pydantic), uvicorn, pyarrow. pyarrow has no type information; it is imported only in `api/arrow.py`, which turns off pyright's unknown-type checks for that file.
**Never imports:** renderer code.

**Tests:** `packages/engine/tests/`, which mirrors `src/vibechem_engine/`.

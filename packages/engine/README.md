<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# vibechem-engine (`vibechem_engine`)

**Status:** walking skeleton plus the first Phase 2 pieces: `vibechem_engine.api` (T0.09), `vibechem_engine.ports` (T2.01), `vibechem_engine.graph` (T2.02), `vibechem_engine.formats` (T2.03) and `vibechem_engine.compiler` (T2.04).

**Purpose:** runs pipelines. It covers port types, the pipeline graph and file format, the compiler, cache, executor, scheduler, runners, projects, the local HTTP/WebSocket API and the CLI.

**Public API:**
- `python -m vibechem_engine.api [--testdata-dir PATH]` — start the HTTP API (DATA_MODEL.md §1 "Start-up"); `VIBECHEM_DEV=1` allows the Vite dev server origin. The desktop app ships this entry point frozen with PyInstaller (`scripts/build_engine.py` → `vibechem-engine[.exe]`; `__main__` calls `multiprocessing.freeze_support()` first).
- `vibechem_engine.api.schemas` (T1.03): pydantic models of the `GET /blocks/{block_id}` object (`BlockDetail`, parameter entries discriminated by `type`), i.e. DATA_MODEL.md §5 as a model; `BlockDetail.model_json_schema()` is its JSON Schema. Not yet served by a route.
- `vibechem_engine.ports` (T2.01): `PORT_TYPE_REGISTRY` (DATA_MODEL.md §4.1), `COMPATIBILITY` (§4.4), `is_compatible(from_type, to_type)`, `edge_rule(from_type, to_type)` (the conversion rule, `None` for equal types, `ValueError` for an incompatible pair), `port_types_payload()` (`GET /port-types` body). Unknown type names raise `ValueError`.
- `vibechem_engine.graph` (T2.02): `validate_graph(pipeline, registry)` checks a pipeline document (DATA_MODEL.md §2.6) against the blocks' ports and returns every §4.4 graph problem as a `GraphIssue` (`to_dict()` = one `POST …/validate` issue): `PIPELINE_PORT_TYPE_MISMATCH`, `PIPELINE_INPUT_MULTIPLE_EDGES`, `PIPELINE_REQUIRED_INPUT_MISSING`, `PIPELINE_CYCLE`. Unknown block, node or port and a repeated `node_id` raise `ValueError`.
- `vibechem_engine.formats` (T2.03): the file formats of DATA_MODEL.md §6 as strict pydantic models — `PipelineFile` (`load_pipeline`/`save_pipeline`), `ProjectFile` (`load_project`/`save_project`), `ModelManifest` + `ModelPackage` (`read_model`/`write_model`, the `.vcm` zip with states in the `save_state` layout). Invalid files raise `FormatError` (`PIPELINE_FILE_INVALID`, `PROJECT_FILE_INVALID`, `MODEL_PACKAGE_INVALID`, `params.reason` per §6.1); missing files raise `OSError`. `formats.migrations`: `CURRENT_VERSIONS`, `@migration(kind, from_version)`, `migrate()` (§6.5). JSON Schemas in `formats/schemas/`, kept in sync by `tests/formats/test_pipeline.py` (`VIBECHEM_UPDATE_SCHEMAS=1` rewrites them).
- `vibechem_engine.compiler` (T2.04): `compile_pipeline(pipeline, registry)` → `CompiledPipeline` (`tasks`, `fold_plans`, `issues`). Stateless blocks become `run` tasks, fitted blocks `fit` + `apply` (the fit task's one output `state` is what the block's `Model`/`Transform` ports carry); implicit §4.4 conversions are the task input's `rule`. A node with a connected `refit_per_fold` input gets a `FoldPlan`; the runner calls `plan.expand(fold, repeat)` per fold for `select` + per-fold `fit`/`apply` tasks (fit on `train` rows only). `PIPELINE_FOLDS_SOURCE_MISMATCH` when the re-fitted subgraph is not downstream of the fold source (DATA_MODEL §4.6). `fold_rows(data, fold, part)` selects fold rows by `row_index` via core `SpectralDataset.rows`. Leaky inputs into the subgraph are rejected by T2.05, not here.
- `vibechem_engine.api.create_app(token, *, testdata_dir, dev=False)` — the FastAPI app: `/api/v1/health`, `/api/v1/blocks` (static SNV entry), temporary `/api/v1/skeleton/run` (§2.12, removed in T4.01).

Later: the Python API and CLI (T2.11) and the rest of the HTTP/WS API in `docs/DATA_MODEL.md`.

**Allowed dependencies** (TECH_STACK.md §3.1): `vibechem_core`, numpy, loky, fastapi (+ starlette, pydantic), uvicorn, pyarrow. pyarrow has no type information; it is imported only in `api/arrow.py`, which turns off pyright's unknown-type checks for that file.
**Never imports:** renderer code.

**Tests:** `packages/engine/tests/`, which mirrors `src/vibechem_engine/`.

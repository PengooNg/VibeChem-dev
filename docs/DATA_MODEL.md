# VibeChem — Data Model & Engine API

> Status: DRAFT v0.3 · Last updated: 2026-11-18 · Reviewers: K (API, formats), Quan (scientific fields)
> v0.3: dev-mode origin rule; temporary skeleton endpoint (§2.12); PDF export only via the desktop app; `EXPORT_FORMAT_UNAVAILABLE`.
> Source of truth for field names. Claude Code must not invent fields: if something is missing, add it here first (with K's approval), then implement.
> §1–§3 and §7 written; §4 (TASKS T0.14), §5 (T1.03), §6 (T2.03) are filled in by those steps.
> Based on ARCHITECTURE.md ADR-003 (HTTP + WebSocket on loopback, *Proposed*); changes there update this file.

## Contents
1. Conventions
2. Engine API — REST endpoints
3. Engine API — WebSocket events
4. Port types *(T0.14)*
5. Block parameter schema *(T1.03)*
6. File formats: project, pipeline, model *(T2.03)*
7. Error codes catalogue

---

## 1. Conventions

| Topic | Rule |
|---|---|
| Base URL | `http://127.0.0.1:{port}/api/v1` — port chosen at random by the engine on start-up and passed to Electron |
| Authentication | Header `Authorization: Bearer {session_token}` on every request; token generated per launch, never written to disk |
| Origin check | Production: requests must come from the packaged app origin (exact value fixed in T0.11, e.g. `app://vibechem`) or have no Origin. Dev mode only (`VIBECHEM_DEV=1`): the Vite dev server origin (`http://localhost:<vite-port>`) is also allowed. All others → `403` |
| Field naming | `snake_case` everywhere (JSON, files, Python). Generated TypeScript types keep `snake_case` — no renaming layer |
| IDs | Prefixed ULIDs: `prj_…` project, `ds_…` dataset, `imp_…` import, `ppl_…` pipeline, `nd_…` node, `run_…` run, `exp_…` export, `prd_…` prediction |
| Result keys | `res_` + 64-hex SHA-256 content hash (cache key) |
| Timestamps | ISO 8601 UTC strings, e.g. `"2026-11-17T05:40:12Z"` |
| Concurrency control | Pipelines carry an integer `revision`; `PUT` requires header `If-Match: {revision}`; mismatch → `409` |
| Long operations | Never block a request > 1 s. Return `202 Accepted` with a job id (run, export, prediction); progress via WebSocket |
| Binary data | Arrow IPC stream, `Content-Type: application/vnd.apache.arrow.stream` |
| Errors | RFC 9457 problem details, `Content-Type: application/problem+json` (see below) |
| Versioning | Breaking changes → `/api/v2`. Additive fields allowed in v1; clients must ignore unknown fields |
| Projects | One open project per engine process in v1; paths still include `{project_id}` so the web Lite edition can reuse them |

### Error body
```json
{
  "type": "https://vibechem.org/errors/port-type-mismatch",
  "title": "Incompatible connection",
  "status": 422,
  "code": "PIPELINE_PORT_TYPE_MISMATCH",
  "message_key": "errors.pipeline.port_type_mismatch",
  "params": { "from_port": "model", "to_port": "spectra", "from_type": "Model", "to_type": "Spectra" },
  "node_id": "nd_01JD8Q…",
  "trace_id": "tr_01JD8R…"
}
```
- `message_key` + `params` are translated in the UI (EN/JA/VI); `title` is an English fallback.
- `code` values are listed in §7.
- **Block errors during a run** (e.g. `BLOCK_CONSTANT_SPECTRA`) are not HTTP errors: they set the node to `error` and arrive as a `node.state` event with `code`, `message_key` + `params` (§3).

### Standard status codes
`200` OK · `201` created · `202` accepted (async job) · `204` no content · `400` malformed request · `401` missing/bad token · `403` bad origin · `404` not found · `409` revision conflict / project busy · `413` file too large · `422` valid JSON but semantically invalid · `500` engine bug (always logged with `trace_id`) · `503` engine starting or shutting down.

---

## 2. Engine API — REST endpoints

### 2.1 Summary
| Method | Path | Purpose | Async |
|---|---|---|---|
| GET | `/health` | Liveness + readiness | |
| GET | `/system` | Versions, cores, memory, native kernels status | |
| GET / PUT | `/settings` | App settings (cores, cache cap, language, tooltips) | |
| GET | `/blocks` | Block registry (list) | |
| GET | `/blocks/{block_id}` | One block's full definition | |
| GET | `/port-types` | Port type registry + compatibility rules | |
| POST | `/projects` | Create a project folder | |
| POST | `/projects/open` | Open an existing project folder | |
| GET | `/projects/{project_id}` | Project manifest | |
| POST | `/projects/{project_id}/close` | Close project (flush, stop runs) | |
| POST | `/projects/{project_id}/imports` | Inspect file(s) → preview + suggested column roles | |
| POST | `/projects/{project_id}/imports/{import_id}/commit` | Confirm roles → create dataset | |
| GET | `/projects/{project_id}/datasets` | List datasets | |
| GET / DELETE | `/projects/{project_id}/datasets/{dataset_id}` | Dataset metadata / remove | |
| GET | `/templates` | Built-in and user pipeline templates | |
| GET / POST | `/projects/{project_id}/pipelines` | List / create (blank or from template) | |
| GET / PUT / DELETE | `/projects/{project_id}/pipelines/{pipeline_id}` | Read / replace / delete | |
| POST | `/projects/{project_id}/pipelines/{pipeline_id}/validate` | Graph + type + leakage validation, no run | |
| POST | `/projects/{project_id}/pipelines/{pipeline_id}/save-as-template` | Save as user template | |
| GET | `/projects/{project_id}/pipelines/{pipeline_id}/nodes/{node_id}/outputs` | Latest result keys per output port | |
| POST | `/projects/{project_id}/runs` | Start a run | ✔ |
| GET | `/projects/{project_id}/runs` | Recent runs | |
| GET | `/projects/{project_id}/runs/{run_id}` | Run state snapshot (resync) | |
| DELETE | `/projects/{project_id}/runs/{run_id}` | Cancel run | |
| GET | `/projects/{project_id}/results/{result_key}` | Result summary (JSON) | |
| GET | `/projects/{project_id}/results/{result_key}/preview` | Plot-ready preview (Arrow) | |
| GET | `/projects/{project_id}/results/{result_key}/data` | Full data (Arrow) | |
| POST | `/projects/{project_id}/exports` | Report / model / Python script / project archive | ✔ |
| GET | `/projects/{project_id}/exports/{export_id}` | Export status + output path | |
| POST | `/projects/{project_id}/predictions` | Apply a model package to a dataset | ✔ |
| GET | `/projects/{project_id}/predictions/{prediction_id}` | Prediction status + result key | |
| GET | `/projects/{project_id}/cache` | Cache size, entries, cap | |
| POST | `/projects/{project_id}/cache/clear` | Clear cache (all or unused) | |
| GET | `/events` (WebSocket) | Live events (§3) | |
| POST | `/skeleton/run` | **Temporary** (T0.09–T4.01 only) — §2.12 | |

### 2.2 System and settings

**`GET /health`** → `200`
```json
{ "status": "ready", "engine_version": "0.2.0", "api_version": "v1", "uptime_s": 132 }
```
`status`: `starting` | `ready` | `shutting_down` (non-ready also returns `503`).

**`GET /system`** → `200`
```json
{
  "engine_version": "0.2.0",
  "python_version": "3.14.8",
  "os": "windows",
  "arch": "x86_64",
  "cpu_cores_logical": 16,
  "cpu_cores_physical": 8,
  "memory_total_bytes": 17179869184,
  "memory_available_bytes": 9123456789,
  "native_kernels": { "available": true, "version": "0.1.0", "fallback_active": [] },
  "block_count": 47
}
```

**`GET /settings`**, **`PUT /settings`** (full object)
```json
{
  "language": "ja",
  "show_student_tips": true,
  "cores_to_use": 7,
  "memory_budget_fraction": 0.7,
  "cache_cap_bytes": 5368709120,
  "default_seed": 20261117
}
```
Validation: `language` ∈ {`en`,`ja`,`vi`}; `1 ≤ cores_to_use ≤ cpu_cores_logical`; `0.2 ≤ memory_budget_fraction ≤ 0.9`.

### 2.3 Blocks and port types

**`GET /blocks`** → `200` — list used by the block library panel.
```json
{
  "blocks": [
    {
      "block_id": "preprocess.snv",
      "version": "1.0.0",
      "block_class": "preprocess",
      "title_key": "blocks.preprocess.snv.title",
      "tooltip_key": "blocks.preprocess.snv.tip",
      "icon": "glyph-snv",
      "fitted": false,
      "tier": "P0",
      "inputs": [ { "port_id": "spectra", "port_type": "Spectra", "required": true, "multiple": false } ],
      "outputs": [ { "port_id": "spectra", "port_type": "Spectra" } ]
    }
  ]
}
```

**`GET /blocks/{block_id}`** → `200` — adds parameter schema (§5), references, implementation and help.
```json
{
  "block_id": "preprocess.savgol",
  "version": "1.0.0",
  "block_class": "preprocess",
  "fitted": false,
  "inputs": [ { "port_id": "spectra", "port_type": "Spectra", "required": true, "multiple": false } ],
  "outputs": [ { "port_id": "spectra", "port_type": "Spectra" } ],
  "params": [
    { "param_id": "window", "type": "int", "default": 15, "min": 5, "max": 101, "odd_only": true,
      "label_key": "blocks.preprocess.savgol.params.window", "tooltip_key": "…window.tip", "advanced": false },
    { "param_id": "polyorder", "type": "int", "default": 2, "min": 0, "max": 6,
      "constraint": "polyorder < window", "advanced": false },
    { "param_id": "deriv", "type": "enum", "default": 0, "choices": [0, 1, 2], "advanced": false }
  ],
  "references": ["savitzky1964"],
  "implementation": { "library": "scipy", "function": "scipy.signal.savgol_filter" },
  "help_key": "blocks.preprocess.savgol.help",
  "custom_panel": null
}
```
`implementation.library` is `"vibechem"` for our own code; reports use it to cite reused libraries (PROJECT.md §5.1).

**`GET /port-types`** → `200`
```json
{
  "port_types": [
    { "name": "Spectra", "description_key": "ports.spectra", "shape_icon": "circle" },
    { "name": "Model", "description_key": "ports.model", "shape_icon": "diamond" }
  ],
  "compatibility": [ { "from": "Spectra", "to": "Table", "rule": "implicit_view" } ]
}
```

### 2.4 Projects

**`POST /projects`** body → `201`
```json
{ "path": "C:/Users/quan/Research/HoneyNIR.vibechem", "name": "Honey NIR adulteration" }
```
Response: project manifest (same as `GET /projects/{project_id}`):
```json
{
  "project_id": "prj_01JD8P…",
  "name": "Honey NIR adulteration",
  "path": "C:/Users/quan/Research/HoneyNIR.vibechem",
  "format_version": 1,
  "created_at": "2026-11-17T05:40:12Z",
  "updated_at": "2026-11-17T05:40:12Z",
  "datasets": [],
  "pipelines": []
}
```
Errors: path exists and is not empty → `409 PROJECT_PATH_NOT_EMPTY`; not writable → `422 PROJECT_PATH_NOT_WRITABLE`.

**`POST /projects/open`** `{ "path": "…" }` → `200` manifest. Older `format_version` is migrated in place after creating a backup (`project.json.bak-{timestamp}`). Another project open → `409 PROJECT_ALREADY_OPEN`.

**`POST /projects/{project_id}/close`** → `204`. Cancels running jobs, flushes writes.

### 2.5 Imports and datasets (two-step)
The desktop engine reads files directly from disk (Electron passes paths from the file dialog), so large files are never uploaded through HTTP. The web Lite edition will add a multipart variant.

**Step 1 — `POST /projects/{project_id}/imports`** → `200`
```json
{ "paths": ["D:/data/honey_nir.csv"], "format_hint": "auto" }
```
Response:
```json
{
  "import_id": "imp_01JD8S…",
  "detected_format": "csv",
  "n_rows": 240,
  "n_columns": 1562,
  "preview_rows": [ ["S001", "A", "0.12", "0.31", "…"] ],
  "suggested_roles": {
    "sample_id": "Sample",
    "group_id": "Batch",
    "y": ["Adulteration_pct"],
    "class_label": null,
    "metadata": ["Origin"],
    "spectral_columns": { "from": "1100", "to": "2498", "count": 1557, "axis_unit": "nm" }
  },
  "warnings": [ { "code": "IMPORT_DUPLICATE_SAMPLE_IDS", "params": { "count": 3 } } ]
}
```
`format_hint`: `auto` | `csv` | `tsv` | `xlsx` | `jcamp` | `spc`. Multiple paths are concatenated (Multifile behaviour); axis mismatch → warning + `needs_interpolation: true`.

**Step 2 — `POST /projects/{project_id}/imports/{import_id}/commit`** → `201` dataset
```json
{
  "name": "Honey NIR 2026",
  "roles": {
    "sample_id": "Sample",
    "group_id": "Batch",
    "y": ["Adulteration_pct"],
    "class_label": null,
    "metadata": ["Origin"],
    "spectral_columns": { "from": "1100", "to": "2498" },
    "axis_unit": "nm",
    "signal_unit": "absorbance"
  },
  "interpolate_to": null
}
```
Dataset object (also `GET …/datasets/{dataset_id}`):
```json
{
  "dataset_id": "ds_01JD8T…",
  "name": "Honey NIR 2026",
  "n_samples": 240,
  "n_variables": 1557,
  "axis": { "unit": "nm", "min": 1100.0, "max": 2498.0, "step": 0.9 },
  "signal_unit": "absorbance",
  "y_columns": ["Adulteration_pct"],
  "class_columns": [],
  "metadata_columns": ["Origin"],
  "has_groups": true,
  "n_groups": 80,
  "source_files": [ { "path": "D:/data/honey_nir.csv", "sha256": "9f2c…" } ],
  "result_key": "res_4ab1…",
  "created_at": "2026-11-17T05:42:00Z"
}
```
`DELETE` → `204`; used by a pipeline → `409 DATASET_IN_USE` unless `?force=true`.

### 2.6 Pipelines
Full pipeline document (exact schema in §6; this is its API shape):
```json
{
  "pipeline_id": "ppl_01JD8V…",
  "name": "NIR PLS – nested CV",
  "revision": 12,
  "format_version": 1,
  "nodes": [
    { "node_id": "nd_a", "block_id": "data.dataset", "block_version": "1.0.0",
      "params": { "dataset_id": "ds_01JD8T…" }, "position": { "x": 80, "y": 120 }, "label": null },
    { "node_id": "nd_b", "block_id": "preprocess.snv", "block_version": "1.0.0",
      "params": { "ddof": 1 }, "position": { "x": 300, "y": 120 }, "label": null }
  ],
  "edges": [
    { "edge_id": "eg_1", "from_node": "nd_a", "from_port": "spectra", "to_node": "nd_b", "to_port": "spectra" }
  ],
  "created_at": "2026-11-17T05:45:00Z",
  "updated_at": "2026-11-17T06:02:31Z"
}
```

| Endpoint | Body | Response |
|---|---|---|
| `POST …/pipelines` | `{ "name": "…", "template_id": "tpl_nir_pls" \| null }` | `201` pipeline |
| `GET …/pipelines` | — | `200` `{ "pipelines": [ {pipeline_id, name, revision, updated_at} ] }` |
| `PUT …/pipelines/{id}` | full pipeline, header `If-Match: 12` | `200` pipeline with `revision: 13`; stale revision → `409 PIPELINE_REVISION_CONFLICT` |
| `DELETE …/pipelines/{id}` | — | `204` (running → `409 PIPELINE_RUNNING`) |

The canvas autosaves with `PUT` (debounced ~500 ms). Saving never runs anything; it only marks changed nodes `stale`.

**`POST …/pipelines/{id}/validate`** → `200`
```json
{
  "valid": false,
  "issues": [
    { "severity": "error", "code": "PIPELINE_REQUIRED_INPUT_MISSING", "node_id": "nd_f", "port_id": "folds",
      "message_key": "errors.pipeline.required_input_missing", "params": {} },
    { "severity": "warning", "code": "VALIDATION_GROUPS_IGNORED", "node_id": "nd_e",
      "message_key": "warnings.validation.groups_ignored", "params": { "n_groups": 80 } }
  ],
  "leakage_safe": true,
  "stale_nodes": ["nd_b", "nd_c"]
}
```
Leakage problems are `error` severity — a leaky pipeline cannot run (F-42).

**`GET …/pipelines/{id}/nodes/{node_id}/outputs`** → `200`
```json
{
  "node_id": "nd_b",
  "state": "done",
  "outputs": [ { "port_id": "spectra", "port_type": "Spectra", "result_key": "res_77c0…", "summary": { "shape": [240, 1557] } } ]
}
```
`state` ∈ `idle | queued | running | done | stale | error`. The UI's "data here" marker uses these states.

### 2.7 Runs
**`POST /projects/{project_id}/runs`** → `202`
```json
{
  "pipeline_id": "ppl_01JD8V…",
  "revision": 13,
  "targets": ["nd_g"],
  "mode": "incremental",
  "cores": null,
  "seed": null
}
```
- `targets`: node ids to compute (plus everything upstream that is stale); `[]` = whole pipeline.
- `mode`: `incremental` (use cache) | `full` (ignore cache).
- `cores`, `seed`: `null` = use settings.

Response:
```json
{ "run_id": "run_01JD8X…", "status": "queued", "planned_tasks": 1240, "cached_tasks": 310, "first_seq": 5021 }
```
Errors: revision not current → `409 PIPELINE_REVISION_CONFLICT`; invalid pipeline → `422` with the same `issues` list as validate; another run on the same pipeline → `409 RUN_ALREADY_ACTIVE` (UI offers "cancel and restart").

**`GET …/runs/{run_id}`** → `200` — snapshot for resync after missed events.
```json
{
  "run_id": "run_01JD8X…",
  "pipeline_id": "ppl_01JD8V…",
  "revision": 13,
  "status": "running",
  "started_at": "2026-11-17T06:03:00Z",
  "finished_at": null,
  "seed": 20261117,
  "cores_used": 7,
  "progress": { "done_tasks": 512, "total_tasks": 930, "eta_s": 41 },
  "nodes": [
    { "node_id": "nd_b", "state": "done" },
    { "node_id": "nd_g", "state": "running", "progress": { "done": 37, "total": 100 } }
  ],
  "last_seq": 5733
}
```
`status` ∈ `queued | running | succeeded | failed | cancelled`.

**`DELETE …/runs/{run_id}`** → `202` `{ "status": "cancelling" }`; final `run.finished` event follows.

### 2.8 Results
**`GET …/results/{result_key}`** → `200` summary (small JSON; type-specific `content`):
```json
{
  "result_key": "res_9e12…",
  "port_type": "Results",
  "producer": { "node_id": "nd_g", "block_id": "validate.nested_cv", "block_version": "1.0.0" },
  "created_at": "2026-11-17T06:04:10Z",
  "size_bytes": 482133,
  "content": {
    "metrics": { "rmsecv": 0.84, "r2cv": 0.962, "bias": -0.02, "rpd": 5.1, "rpiq": 6.3, "n_lv": 7 },
    "y_unit": "%",
    "leakage_safe": true
  }
}
```

**`GET …/results/{result_key}/preview`** → `200` Arrow IPC
Query parameters:
| Param | Values | Default |
|---|---|---|
| `view` | `spectra` \| `scatter` \| `table` \| `image` \| `curve` | per port type |
| `width` | plot width in pixels (64–4096) | 1200 |
| `rows` | comma list or range of sample indices | all |
| `color_by` | column name (Y, class, metadata) | none |
| `max_lines` | max spectra drawn as lines | 500 |
| `x_range` | `min,max` in axis units | full |

Behaviour for `view=spectra`:
- n ≤ `max_lines`: each spectrum decimated to ≈ `width` points (shape-preserving); columns `x` (float32), `y_{i}` (float32), plus `color` values.
- n > `max_lines`: **density mode** — a 2-D density raster (width × 256, uint16 counts) plus mean, ±1 SD, and the selected rows as lines.
- Response header `X-VibeChem-Preview-Mode: lines | density`.

**`GET …/results/{result_key}/data`** → `200` full data as Arrow IPC (used by table view, export, Python bridge). Above 512 MB → `413 RESULT_TOO_LARGE_USE_EXPORT`.

### 2.9 Exports
**`POST /projects/{project_id}/exports`** → `202`
```json
{
  "kind": "report",
  "pipeline_id": "ppl_01JD8V…",
  "node_id": "nd_g",
  "format": "html",
  "output_path": "C:/Users/quan/Research/HoneyNIR.vibechem/reports/nested_cv.html",
  "options": { "language": "en", "include_methods_paragraph": true, "include_bibliography": true, "bib_format": "bibtex" }
}
```
| `kind` | `format` | Output |
|---|---|---|
| `report` | `html` | Report with methods paragraph + references (F-72, F-75). **PDF:** the desktop app converts the HTML with print-to-PDF; requesting `pdf` from the engine directly → `422 EXPORT_FORMAT_UNAVAILABLE` |
| `model` | `vcm` | Model package (F-70) |
| `python` | `py` | Runnable script (F-73) |
| `project` | `vcz` | Zipped project; option `include_cache: false` |
| `figure` | `svg` \| `png` | Publication figure (options: `width_mm`, `dpi`); PDF figures via the desktop app as above |

**`GET …/exports/{export_id}`** → `{ "export_id", "status": "queued|running|succeeded|failed", "output_path", "error": null | problem }`

### 2.10 Predictions (Predict mode, F-71)
**`POST /projects/{project_id}/predictions`** → `202`
```json
{ "model_path": "D:/models/honey_pls_v3.vcm", "dataset_id": "ds_01JD9A…" }
```
**`GET …/predictions/{prediction_id}`** → `200`
```json
{
  "prediction_id": "prd_01JD9B…",
  "status": "succeeded",
  "model": { "name": "honey_pls_v3", "vibechem_version": "1.0.0", "trained_at": "2026-11-17T06:10:00Z" },
  "result_key": "res_c3d9…",
  "applicability": {
    "n_samples": 40,
    "n_outside_t2": 2,
    "n_outside_q": 1,
    "axis_check": "ok",
    "y_range_warning": false
  }
}
```
Axis mismatch the model can't handle → `422 MODEL_AXIS_MISMATCH` with `params.expected` / `params.found`. Packages are loaded without pickle (ADR-007); invalid manifest → `422 MODEL_PACKAGE_INVALID`.

### 2.11 Cache
**`GET …/cache`** → `{ "size_bytes": 1830492011, "cap_bytes": 5368709120, "entries": 4120 }`
**`POST …/cache/clear`** `{ "scope": "unused" | "all" }` → `200` `{ "freed_bytes": 912004112 }`. `all` during a run → `409 RUN_ALREADY_ACTIVE`.

### 2.12 Temporary skeleton endpoint (Phase 0 walking skeleton only)
**`POST /skeleton/run`** → `200` Arrow IPC (same format as §2.8 preview, `view=spectra`)
```json
{ "dataset": "reference_nir", "apply_snv": true, "width": 1200 }
```
- `dataset`: name of a bundled reference dataset from `testdata/datasets/`.
- Returns raw spectra when `apply_snv` is false, SNV spectra when true.
- Removed in T4.01 when the real run/preview endpoints exist; a test asserts it is absent from production builds after that.

---

## 3. Engine API — WebSocket events

**Connect:** `ws://127.0.0.1:{port}/api/v1/events`. The first client message must be
`{ "type": "auth", "token": "{session_token}" }` within 2 s, otherwise the server closes with code `4401`. (Browsers can't set headers on WebSocket, so the token travels in the first message, not the URL.)

**Envelope (server → client):**
```json
{ "seq": 5734, "ts": "2026-11-17T06:03:41Z", "type": "node.state", "project_id": "prj_…", "run_id": "run_…", "data": { } }
```
- `seq` increases by 1 per event per engine session. A gap means events were missed → client calls `GET /runs/{run_id}`.
- Delivery is at-most-once; the snapshot endpoint is the recovery path.
- Progress events are throttled to ≤ 4 per second per node.

| `type` | `data` fields | When |
|---|---|---|
| `engine.ready` | `engine_version` | After start-up |
| `engine.health` | `memory_available_bytes`, `workers_alive`, `cores_used` | Every 5 s |
| `run.started` | `pipeline_id`, `revision`, `planned_tasks`, `cached_tasks` | Run begins |
| `node.state` | `node_id`, `state`, `code?`, `message_key?`, `params?` | Any node state change |
| `node.progress` | `node_id`, `done`, `total`, `eta_s` | Long node (CV, search) |
| `run.progress` | `done_tasks`, `total_tasks`, `eta_s` | Whole run |
| `run.finished` | `status`, `duration_s`, `failed_nodes[]` | Run ends |
| `log` | `level` (`debug\|info\|warning\|error`), `message`, `node_id?`, `block_id?`, `trace_id?` | Engine/block logs |
| `native.fallback` | `block_id`, `kernel`, `reason` | C++ kernel failed → Python reference used |
| `memory.throttled` | `old_workers`, `new_workers` | Memory guard reduced concurrency |
| `export.finished` | `export_id`, `status`, `output_path?` | Export done |
| `prediction.finished` | `prediction_id`, `status` | Prediction done |
| `cache.evicted` | `freed_bytes` | LRU eviction ran |

**Client → server messages (v1):** only `auth` and `ping` (`{ "type": "ping" }` → server replies `{ "type": "pong" }`). All commands go through REST.

---

## 4. Port types *(filled in by TASKS.md T0.14)*
To define: `Spectra`, `Table`, `Model`, `Transform`, `Folds`, `Results`, `ImageCube`; fields of each; implicit conversions; multi-input rules (e.g. PDS `master`, `slave`, `transfer_samples`).

## 5. Block parameter schema *(filled in by T1.03)*
To define: parameter types (`int`, `float`, `bool`, `enum`, `string`, `range`, `column_ref`, `wavelength_range`, `list`), units, conditional visibility (`visible_if`), cross-field constraints, `advanced` flag, translation keys.

## 6. File formats *(filled in by T2.03)*
To define: `project.json`, `pipelines/*.vcp.json` (JSON Schema), `models/*.vcm` (zip: `manifest.json` + `.npy`), `.vcz` project archive, cache index; versioning and migrations.

## 7. Error codes catalogue
Each code is defined in exactly one module (listed), so searching for a code finds its origin (QA.md §5).
| Code | HTTP / where | Defined in | Meaning |
|---|---|---|---|
| `AUTH_TOKEN_INVALID` | 401 | `engine/api` | Missing or wrong session token |
| `ORIGIN_FORBIDDEN` | 403 | `engine/api` | Request not from the app |
| `PROJECT_PATH_NOT_EMPTY` | 409 | `engine/project` | Create into a non-empty folder |
| `PROJECT_PATH_NOT_WRITABLE` | 422 | `engine/project` | No write permission |
| `PROJECT_ALREADY_OPEN` | 409 | `engine/project` | Another project is open |
| `IMPORT_FORMAT_UNKNOWN` | 422 | `core/io` | File type not recognised |
| `IMPORT_DUPLICATE_SAMPLE_IDS` | warning | `core/io` | Repeated sample IDs |
| `DATASET_IN_USE` | 409 | `engine/project` | Dataset referenced by a pipeline |
| `PIPELINE_REVISION_CONFLICT` | 409 | `engine/api` | Stale `If-Match` revision |
| `PIPELINE_PORT_TYPE_MISMATCH` | 422 | `engine/graph` | Incompatible edge |
| `PIPELINE_REQUIRED_INPUT_MISSING` | 422 | `engine/graph` | Unconnected required port |
| `PIPELINE_CYCLE` | 422 | `engine/graph` | Graph has a cycle |
| `PIPELINE_LEAKAGE` | 422 | `engine/compiler` | Fit step would see validation/test data |
| `PIPELINE_RUNNING` | 409 | `engine/api` | Change blocked during run |
| `RUN_ALREADY_ACTIVE` | 409 | `engine/scheduler` | Run already active on this pipeline/project |
| `RESULT_TOO_LARGE_USE_EXPORT` | 413 | `engine/api` | Use export for very large data |
| `EXPORT_FORMAT_UNAVAILABLE` | 422 | `engine/api` | Format needs the desktop app (e.g. PDF) |
| `MODEL_PACKAGE_INVALID` | 422 | `engine/formats` | Bad or unsafe model file |
| `MODEL_AXIS_MISMATCH` | 422 | `engine/formats` | New data's axis doesn't match the model |
| `VALIDATION_GROUPS_IGNORED` | warning | `engine/graph` | Groups exist but CV ignores them |
| `BLOCK_CONSTANT_SPECTRA` | node error | `core/blocks/preprocess` | A spectrum has zero variance (e.g. SNV cannot scale it) |

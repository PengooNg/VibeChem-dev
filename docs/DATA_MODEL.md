# VibeChem — Data Model & Engine API

> Status: DRAFT v0.9 · Last updated: 2026-11-27 · Reviewer: Quan (API, formats, scientific fields)
> v0.9: §3 `native.fallback` `reason` value `worker_crashed`; §7 `RUN_OUT_OF_MEMORY` proposed (T2.09).
> v0.8: §6.6 cache key and cache folder layout (T2.06).
> v0.7: §4.7.2 decided (Quan, 2026-11-27): validation via the `refit_per_fold` port, no container nodes; §4.6 gives the fold scope the compiler derives (T2.04).
> v0.6: §6 file formats drafted (T2.03): common rules, `project.json`, pipeline file, `.vcm` model package, migrations; codes `PIPELINE_FILE_INVALID`, `PROJECT_FILE_INVALID` proposed in §7.
> v0.5: §5 block parameter schema drafted (T1.03): types, units, `visible_if`, constraints, value validation; `/blocks/{id}` fields spelled out in §2.3; new error code `BLOCK_PARAM_INVALID` in §7.
> v0.4: §4 port types drafted (T0.14): seven types with fields, compatibility rules, port declaration fields, multi-input rules (PDS, ImageCube), fold/refit semantics; five new error codes in §7.
> v0.3: dev-mode origin rule; temporary skeleton endpoint (§2.12); PDF export only via the desktop app; `EXPORT_FORMAT_UNAVAILABLE`.
> Source of truth for field names. Claude Code must not invent fields: if something is missing, add it here first (with Quan's approval), then implement.
> §1–§7 written (§4, §5, §6 draft).
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
| Start-up | `python -m vibechem_engine.api [--testdata-dir PATH]` binds `127.0.0.1` on a random free port, then writes **one JSON line** to stdout before serving: `{"event": "engine.listening", "port": 52114, "token": "…"}`. Electron main reads port + token from it and hands them to the renderer over IPC, only to its own page (dev mode since T0.10). The packaged app runs the same entry point frozen with PyInstaller (`<resources>/engine/vibechem-engine[.exe]`, T0.11). Until T4.01, `--testdata-dir` points at the repository `testdata/` folder used by §2.12 (default: found above the package; the packaged app ships a copy in `<resources>/testdata`) |
| Origin check | Production: requests must come from the app origin `app://vibechem` (Electron main serves the built renderer from this custom scheme, T0.11) or have no Origin. Dev mode only (`VIBECHEM_DEV=1`): the Vite dev server origin (`http://localhost:<vite-port>`) is also allowed. All others → `403` |
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
The `/blocks/{id}` object is the `/blocks` entry (`title_key`, `tooltip_key`, `icon`, `tier` included) plus `params` (§5), `references`, `implementation`, `help_key` (`blocks.<block_id>.help`) and `custom_panel` (`null` or the panel's id, ADR-005). The example above abbreviates: every param entry carries `label_key`, `tooltip_key` and `advanced` (§5.1).

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
  "warnings": [ { "code": "IMPORT_DUPLICATE_SAMPLE_IDS", "params": { "count": 3 } } ],
  "needs_interpolation": false
}
```
`format_hint`: `auto` | `csv` | `tsv` | `xlsx` | `jcamp` | `spc` | `spa` | `perkinelmer` | `wdf` | `opus` *(the last four proposed T1.06b)*. Role suggestions and parsing rules for CSV/TSV/Excel (comment lines, headerless axis + spectra files, the spectral column run, the axis-unit guess) are documented in `vibechem_core/io/table.py` (T1.05); JCAMP-DX (`.jdx`, `.dx`, `.jcamp`) and Galactic SPC (`.spc`) rules in `vibechem_core/io/jcamp.py` and `io/spc.py` (T1.06), Thermo OMNIC SPA (`.spa`), PerkinElmer (`.sp`), Renishaw WiRE (`.wdf`) and Bruker OPUS (`.0`, `.1`, …) rules in `io/spa.py`, `io/perkinelmer.py`, `io/wdf.py` and `io/opus.py` (T1.06b; maps and data series → `IMPORT_FILE_INVALID` reason `unsupported`; the OPUS data block is the file's first unless the reader's `block` option asks for absorbance, sample or reference — not yet an API field): one row per spectrum (per SPC subfile, per WDF spectrum), a `title` text column, spectral columns named by their axis value, the axis unit taken from the file when it is nm, cm⁻¹ or µm. `axis_unit` is a guess the user confirms at commit. Multiple paths are concatenated (Multifile behaviour, `vibechem_core/io/multifile.py`): a `source_file` text column first, columns matched by name, spectral columns by axis value on the union axis; axis mismatch (also between the subfiles of one SPC file) → warning `IMPORT_AXIS_MISMATCH` + `needs_interpolation: true` *(proposed T1.06)*.

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
    "metrics": { "rmsecv": 0.84, "r2cv": 0.962, "secv": 0.84, "bias_cv": -0.02, "rpd_cv": 5.1, "rpiq_cv": 6.3, "press": 42.3, "n_lv": 7 },
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
{ "dataset": "gasoline_nir", "apply_snv": true, "width": 1200 }
```
- `dataset`: name of a bundled reference dataset from `testdata/datasets/` (`gasoline_nir` or `olive_oil_ftir`, see `PROVENANCE.md` there).
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
| `native.fallback` | `block_id`, `kernel`, `reason` | C++ kernel failed → Python reference used (`reason`: `worker_crashed` *(proposed T2.09)*) |
| `memory.throttled` | `old_workers`, `new_workers` | Memory guard reduced concurrency |
| `export.finished` | `export_id`, `status`, `output_path?` | Export done |
| `prediction.finished` | `prediction_id`, `status` | Prediction done |
| `cache.evicted` | `freed_bytes` | LRU eviction ran |

**Client → server messages (v1):** only `auth` and `ping` (`{ "type": "ping" }` → server replies `{ "type": "pong" }`). All commands go through REST.

---

## 4. Port types *(DRAFT, T0.14 — Quan reviews)*
A port is a named, typed input or output of a block (PRD F-07). Every edge connects one output port to one input port. The engine checks types **statically** when a pipeline is validated (`PIPELINE_PORT_TYPE_MISMATCH`, §2.6 validate); checks that depend on the data (matching rows, axes, presence of Y) run when the block runs and set the node to `error` (§3 `node.state`). Implemented in T2.01 (`vibechem_engine/ports/`); the Python classes behind the types come from T1.01 (`SpectralDataset`) and T1.02a/b (block contract).

### 4.1 Type registry
Seven types in v1. Names are case-sensitive and appear as `port_type` in `/blocks` (§2.3) and in pipeline files (§6).
| `name` | Carries | Python object (core) | `shape_icon` (UI_GUIDE §6) | `description_key` |
|---|---|---|---|---|
| `Spectra` | n samples × p variables on one spectral axis, plus sample annotations | `SpectralDataset` | `circle` | `ports.spectra` |
| `Table` | Rows × named columns (metadata, scores, metric tables, ID lists) | mapping column name → 1-D NumPy array, all of one length (no pyarrow in core, T1.05); the engine converts it to an Arrow table | `circle` | `ports.table` |
| `Model` | Fitted state of a predictive block (regression, classification, projection, one-class) | `ModelState` | `diamond` | `ports.model` |
| `Transform` | Fitted state of a non-predictive block that maps spectra to spectra (scaler, MSC reference, PDS/DS matrix, EPO projection) | `TransformState` | `diamond_outline` *(proposed; add to UI_GUIDE §6)* | `ports.transform` |
| `Folds` | Row-index sets for validation: k folds, repeats, or one train/test hold-out | `FoldSet` | `triangle` | `ports.folds` |
| `Results` | Outcome of an evaluation: metrics, per-sample predictions, per-candidate search table | `ResultSet` | `square` | `ports.results` |
| `ImageCube` | Hyperspectral image: height × width × p on one spectral axis (P2) | `ImageCube` | `hexagon` | `ports.image_cube` |

No `Any` type: a block that accepts several kinds of data declares a `Table` input and relies on the implicit views in §4.4 (e.g. export accepts `Spectra`, `Table` and `Results`).

### 4.2 Fields of each type
Fields are the logical content; storage in the cache is `.npy` for arrays and Arrow/Parquet for tables (ARCHITECTURE.md §2.3). `row_index` is the key to leakage safety: every row-bearing type keeps, per row, its index in the **source dataset** (the `data.dataset` node it came from), so the compiler can map folds onto any downstream object.

**`Spectra`**
| Field | Type | Notes |
|---|---|---|
| `X` | float64 array (n, p) | Signal values |
| `axis` | `{ "values": float64[p], "unit": str }` | `unit` ∈ `nm` \| `cm-1` \| `um` \| `index`; strictly monotonic |
| `signal_unit` | str | e.g. `absorbance`, `reflectance`, `transmittance`, `counts`, `arbitrary` |
| `sample_ids` | str[n] | Unique within the object |
| `row_index` | int64[n] | Row in the source dataset (see above) |
| `source_id` | str | `dataset_id` of the source dataset |
| `group_ids` | str[n] \| null | Replicate / batch groups (group CV) |
| `y` | float64 array (n, k) \| null | With `y_columns: str[k]`, `y_units: str[k]` |
| `classes` | str[n] \| null | With `class_column: str` |
| `metadata` | Table (n rows) \| null | Other columns kept from import |
| `spatial` | `{ "height": int, "width": int, "pixel": int64[n], "cube_id": str }` \| null | Set only when the rows were unfolded from an `ImageCube` (§4.4); `pixel` = row-major pixel index |
| `history` | str[] | Applied steps, e.g. `"SNV(ddof=1)"` |

Result summary `content` (§2.8): `{ "shape": [n, p], "axis": {unit, min, max}, "signal_unit", "y_columns", "has_classes", "has_groups", "has_spatial" }`.

**`Table`**
| Field | Type | Notes |
|---|---|---|
| `columns` | `[{ "name": str, "dtype": "float64" \| "int64" \| "bool" \| "string", "unit": str \| null }]` | Column names unique |
| `data` | Arrow table | |
| `row_index` | int64[n] \| null | Present when rows are samples of a source dataset; null for summary tables (e.g. ANOVA table) |
| `source_id` | str \| null | |

Summary `content`: `{ "shape": [n, m], "columns": [...] }`.

**`Model`** and **`Transform`** (same layout; separate types so a transform can never be wired where a predictor is expected)
| Field | Type | Notes |
|---|---|---|
| `kind` | Model: `regression` \| `classification` \| `projection` \| `one_class`; Transform: `preprocess` \| `transfer` | |
| `producer` | `{ "block_id", "block_version", "params" }` | Block that was fitted |
| `state` | JSON object + named arrays | Serialised without pickle (ADR-007); exact content per block |
| `input_axis` | `{ "unit", "min", "max", "p" }` | Axis the state was fitted on; applying to a different axis → `BLOCK_INPUT_AXIS_MISMATCH` |
| `output_axis` | same \| null | Transform only (e.g. range cut changes p) |
| `y_columns` / `classes` | str[] \| null | Model only |
| `fitted_rows` | `{ "source_id": str, "row_index_sha256": str, "n": int }` | Fingerprint of the training rows; lets the leakage audit (T2.05) and reports prove what a state was fitted on |

Summary `content`: `{ "kind", "producer", "n_fitted": n, ... block-specific (e.g. "n_lv") }`.

**`Folds`**
| Field | Type | Notes |
|---|---|---|
| `scheme` | `kfold` \| `venetian` \| `contiguous` \| `loo` \| `repeated_kfold` \| `monte_carlo` \| `group_kfold` \| `holdout` \| `custom` | `holdout` = one train/test split (random, KS, SPXY, by column) |
| `source_id` | str | Dataset the indices refer to |
| `n_samples` | int | Rows of the source covered |
| `folds` | `[{ "fold": int, "repeat": int, "train": int64[], "validation": int64[] }]` | Values are `row_index` values, not positions; for `holdout` one entry where `validation` is the test set |
| `groups_respected` | bool | true when no group is split across train/validation |
| `seed` | int \| null | Seed used (null for deterministic schemes) |

Summary `content`: `{ "scheme", "n_folds", "n_repeats", "n_samples", "groups_respected" }`.
Core: `vibechem_core.data.FoldSet` with `Fold(fold, repeat, train, validation)` entries *(T1.10)*. Hold-out split blocks set `groups_respected: false` when the input has `group_ids` and `group_aware` is off; the engine turns that into `VALIDATION_GROUPS_IGNORED`. A block with several data outputs returns a dict keyed by output `port_id` (accepted, Quan 2026-11-26); a block with one output returns the object itself. CV fold blocks (T1.11) set `groups_respected: false` when the input has `group_ids` and the scheme ignores them (k-fold, venetian blinds, contiguous blocks, repeated k-fold); leave-one-out with groups is leave-one-group-out, and group k-fold `requires: ["groups"]`.

**`Results`**
| Field | Type | Notes |
|---|---|---|
| `kind` | `cv` \| `nested_cv` \| `test_set` \| `permutation` \| `search` \| `statistics` | |
| `metrics` | object: name → number | Names from METHODS.md §8, one per metric and set (e.g. `rmsecv`, `r2cv`, `bias_cv`, `rpd_cv`, `rss_c`); original Y units |
| `y_unit` | str \| null | |
| `predictions` | Table \| null | Columns `row_index`, `sample_id`, `fold`, `repeat`, `y_true_<col>`, `y_pred_<col>` (classification: `class_true`, `class_pred`, `score_<class>`) |
| `candidates` | Table \| null | `search` / `nested_cv`: one row per parameter candidate with its metrics |
| `leakage_safe` | bool | Copied from validation (§2.6) |
| `details` | JSON object | Block-specific (e.g. LV curve, permutation distribution) |

Summary `content` = the `metrics`, `y_unit`, `leakage_safe` object already shown in §2.8, plus `kind`.
Core: `vibechem_core.data.Results` (same fields; `predictions` and `candidates` are column name → NumPy array mappings like every core table) *(proposed T2.10a)*. Classification metric names: METHODS.md §8 (N22, proposed T2.10a).

**`ImageCube`** (P2; the type is fixed now so imaging blocks need no format change)
| Field | Type | Notes |
|---|---|---|
| `data` | float32 or float64 array (height, width, p) | Memory-mapped `.npy` or chunked Zarr (ARCHITECTURE.md §2.3); processed in tiles |
| `axis`, `signal_unit` | as `Spectra` | |
| `mask` | bool array (height, width) \| null | true = pixel used (ROI / background removal) |
| `pixel_size` | `{ "x": float, "y": float, "unit": str }` \| null | |
| `cube_id` | str | Stable id, referenced by `Spectra.spatial.cube_id` |
| `history` | str[] | |

Summary `content`: `{ "shape": [h, w, p], "axis": {...}, "n_masked": int }`.

### 4.3 Port declaration (in `/blocks`, §2.3)
Inputs: `port_id`, `port_type`, `required`, `multiple` (already in §2.3) plus these optional fields; outputs: `port_id`, `port_type`.
| Field | Default | Meaning |
|---|---|---|
| `requires` | `[]` | Content the data must have: `y`, `classes`, `groups`, `spatial`. Checked at run time → `BLOCK_INPUT_REQUIREMENT_MISSING` |
| `rows_match` | null | `port_id` of another input of the same block whose `sample_ids` this input must match (§4.5). Checked at run time → `BLOCK_INPUT_ROWS_MISMATCH` |
| `axis_match` | null | `port_id` of another input whose axis this input must equal. Checked at run time → `BLOCK_INPUT_AXIS_MISMATCH` |
| `refit_per_fold` | false | Only on `Model`/`Transform` inputs of validation blocks: the upstream subgraph that produced this state is re-fitted per fold (§4.6) instead of being applied as is |

`port_id` is `snake_case`, unique per direction within a block. i18n: `blocks.<block_id>.ports.<port_id>` (label) and `….tip`.

### 4.4 Compatibility rules
An edge `from_type → to_type` is valid if the types are equal **or** the pair is listed here. Everything else → `PIPELINE_PORT_TYPE_MISMATCH` (params `from_port`, `to_port`, `from_type`, `to_type`, §1 error body). Rules are returned by `GET /port-types` as `compatibility`.
| `from` | `to` | `rule` | What the receiving block sees |
|---|---|---|---|
| `Spectra` | `Table` | `implicit_view` | Columns `sample_id`, `group_id`?, Y columns, class column, metadata columns, then one `float64` column per axis value (name = value as text); `row_index` kept |
| `Results` | `Table` | `implicit_view` | The `predictions` table; a `Results` without predictions → `BLOCK_INPUT_REQUIREMENT_MISSING` |
| `ImageCube` | `Spectra` | `implicit_unfold` | One row per unmasked pixel (row-major), `sample_ids` = `px_<pixel>`, `spatial` filled; no Y. Large cubes are processed in tiles by the scheduler |

Not convertible, on purpose: `Model ↔ Transform` (a predictor is not a preprocessing step), anything `→ Folds` (folds come only from split/fold blocks), `Spectra → ImageCube` (refolding is the explicit block `imaging.refold`, input `spectra` with `requires: ["spatial"]`).
Graph rules (validated statically, T2.02):
- **Fan-out:** an output port may feed any number of inputs.
- **One edge per single input:** an input with `multiple: false` takes at most one edge → `PIPELINE_INPUT_MULTIPLE_EDGES`.
- **`multiple: true` inputs** (e.g. model comparison over several `Results`, concatenate several `Spectra`) receive their edges in the order they appear in the pipeline's `edges` array; the UI shows that order and lets the user reorder it.
- **Required inputs** unconnected → `PIPELINE_REQUIRED_INPUT_MISSING` (§2.6). Optional unconnected inputs are `None` in `apply`.
- The graph is a DAG (`PIPELINE_CYCLE`).

### 4.5 Multi-input rules
**Row matching (`rows_match`).** Rows of two inputs are paired by `sample_id`, not by position. The block receives both inputs reordered to the order of the referenced port; ids present in only one input are dropped and counted in a `log` warning. No common id, or fewer than the block's minimum → `BLOCK_INPUT_ROWS_MISMATCH` (params `port_id`, `other_port_id`, `n_common`, `n_required`).
**Axis matching (`axis_match`).** Equal unit and values (relative tolerance 1e-9). Otherwise `BLOCK_INPUT_AXIS_MISMATCH` (params `port_id`, `expected`, `found`); the fix is an interpolation block upstream — the engine never interpolates silently.

Reference port layouts (block ids indicative; the blocks themselves are P1/P2):
| Block | Inputs | Outputs |
|---|---|---|
| PDS / DS (`transfer.pds`, `transfer.ds`) | `master: Spectra` (required) · `slave: Spectra` (required, `rows_match: master`; PDS also `axis_match: master`, DS allows a different axis) · `transfer_samples: Table` (optional, column `sample_id`; absent = all ids common to master and slave) | `transform: Transform` (`kind: transfer`, fitted on the transfer samples only) · `corrected: Spectra` (all `slave` rows mapped to the master space) |
| Apply transform (`transfer.apply`) | `transform: Transform` · `spectra: Spectra` (new slave data) | `spectra: Spectra` |
| Transfer-sample selection (`transfer.select_ks`) | `spectra: Spectra` (master) | `transfer_samples: Table` (`sample_id` column) |
| Slope/bias correction | `model: Model` · `reference: Spectra` (`requires: ["y"]`) | `model: Model` |
| Domain adaptation (di-PLS) | `source: Spectra` (`requires: ["y"]`) · `target: Spectra` (`axis_match: source`, Y not needed) | `model: Model` |
| Prediction map (`imaging.predict_map`) | `cube: ImageCube` · `model: Model` | `map: ImageCube` (one band per predicted Y column / class score) |
| PLS regression (`model.pls`) *(accepted, Quan 2026-11-26)* | `spectra: Spectra` (`requires: ["y"]`) · `y_transform: Transform` (optional; a y scaling fitted with `target = y`, kept in the model state so every prediction is mapped back to original Y units, METHODS.md §1) | `predictions: Table` (`row_index`, `sample_id`, `y_pred_<col>` with all fitted LVs) · `model: Model` (`kind: regression`; state holds means, W, P, Q, R, T, B, explained variance and the `algorithm` (`nipals` / `simpls`; for SIMPLS, W = R with unit columns, METHODS.md#simpls); LV sweep and VIP from the state (VIP, algorithm: decided, Quan 2026-11-26)) |
| Cross-validation (`validate.cv`) *(proposed T2.10a)* | `model: Model` (`refit_per_fold: true`; PLS1 in T2.10a) · `folds: Folds` | `results: Results` (`kind: cv`, METHODS.md#cv; LV curve in `details`). Params: `aggregation`, `lv_rule` (`global_min`, `one_se`, `ttest`, `wold`, `haaland_thomas`, `van_der_voet`), `alpha`, `wold_threshold`, `f_alpha`, `randomisation_alpha`, `n_randomisations`, `seed` (METHODS.md#cv). The `model` output (refit at the chosen LV count) comes with nested CV (T2.10b). The engine runner hands the block the per-fold states and validation spectra |
| Refold (`imaging.refold`) | `spectra: Spectra` (`requires: ["spatial"]`) | `cube: ImageCube` |
| ROI / mask (`imaging.roi`) | `cube: ImageCube` | `cube: ImageCube` (with `mask`) · `mean_spectra: Spectra` (one row per ROI) |

**ImageCube inside ordinary pipelines.** Every P0 preprocessing block works on a cube through `implicit_unfold`; its output is `Spectra` with `spatial` set, and `imaging.refold` turns it back into a cube. Fitted blocks applied to unfolded pixels follow the same fit/apply rules as any `Spectra` (a model is fitted on calibration spectra, then applied to pixels).

### 4.6 Fitted states, folds and validation (leakage)
- A fitted block has the usual data outputs plus an optional state output (`model: Model` or `transform: Transform`). Inside a pipeline the compiler splits it into fit and apply tasks (ARCHITECTURE.md §3.2); the state port exists so a state can be applied to other data or exported.
- **Split and fold blocks** take `spectra: Spectra` and output `folds: Folds`. Hold-out splits (random, KS, SPXY) also output `train: Spectra` and `test: Spectra` for convenience; both carry `row_index`, so a later `fit` on `test` rows is still detected.
- **Validation blocks** (CV, nested CV, permutation, grid search) take `model: Model` with `refit_per_fold: true` and `folds: Folds`, and output `results: Results` and `model: Model` (refit on all training rows). The compiler re-runs the whole upstream subgraph between the dataset node and the `model` port once per fold, with every `fit` task restricted to that fold's `train` rows and `apply` tasks run on train and validation rows. The `Folds` and the model's subgraph must come from the same source dataset → `PIPELINE_FOLDS_SOURCE_MISMATCH`. Exact scope (compiler, T2.04): the fold source is the `Spectra` stream feeding the block that produced the `folds` input (e.g. a hold-out `train` output when the folds are made on it); the re-fitted subgraph is every node downstream of that stream that feeds the `refit_per_fold` port. A `refit_per_fold` source that is not downstream of the fold source → `PIPELINE_FOLDS_SOURCE_MISMATCH`; a fitted block upstream of the fold source (fitted once on rows that are some fold's validation rows) → `PIPELINE_LEAKAGE` on that node, so fold blocks go on the data before any fitted preprocessing. Fold rows are selected by `row_index` (`SpectralDataset.rows`), never by position. A fitted block upstream of a block whose `train`/`test` output is used is `PIPELINE_LEAKAGE` too (fitted on the test rows). Row provenance (T2.05, `engine/compiler/leakage.py`): every node without input edges is a data source, identified by `block_id` + `params`; an output port named `train` or `test` (hold-out splits) and, inside a fold, the fold source stream narrow the rows a stream holds. The first declared input of a fitted block holds its training rows. Any other fit input from the same source must hold a subset of them, and no fit input may hold `test` rows; inside a fold every fit input from the fold source's dataset must be the fold's `train` rows; otherwise → `PIPELINE_LEAKAGE` on that node and port (e.g. MSC `reference` from the unsplit dataset, a `y_transform` fitted on all rows). Inputs from another source are allowed. Nested CV adds an inner `inner_folds: Folds` input or an inner scheme parameter (decided in T2.10).
- **External test set** (`validate.test_set`): `model: Model` (`refit_per_fold: false`, applied as is) · `spectra: Spectra` (`requires: ["y"]` or `["classes"]`) → `results: Results`. If the test rows overlap `Model.fitted_rows` → `PIPELINE_LEAKAGE`. Checked statically (T2.05): a `Model`/`Transform` input whose state did not pass the split's `train` output, on a node that also receives that split's `test` rows → `PIPELINE_LEAKAGE` on the state port; the run-time `fitted_rows` check comes with the block.
- **Container blocks (UI_GUIDE §6).** A nested-CV or grid-search container on the canvas is a drawing of a validation block plus the subgraph feeding its `refit_per_fold` port; it is not a separate port type. How the pipeline file records which nodes sit inside a frame is decided in T2.03 (§6).

### 4.7 Open points for review
1. `Transform` shape `diamond_outline` is new — UI_GUIDE §6 lists shapes only for the other six types.
2. **Decided (Quan, 2026-11-27): option 1.** Validation via `refit_per_fold` on a `Model` input (above), no explicit container nodes with inner input/output ports. Format v1 stays without frames (§6.3); the per-fold scope is derived from the subgraph feeding `refit_per_fold` (§4.6).
3. `transfer_samples` as a `Table` of ids (above) vs. a `Spectra` subset of the master set.

## 5. Block parameter schema *(DRAFT, T1.03 — Quan reviews)*
The `params` list of `GET /blocks/{block_id}` (§2.3). The inspector form is generated from it (ADR-005), pipeline files store the values (`nodes[].params`, §2.6/§6), and the engine validates those values against it. Source of truth in code: `Param(...)` fields of a block's params dataclass (`vibechem_core.block`); `BlockMeta.to_detail_dict()` produces the `/blocks/{id}` object; `vibechem_engine.api.schemas.BlockDetail` (pydantic) is this section as a model and gives its JSON Schema.

### 5.1 Parameter entry
Fields present for every type:
| Field | Type | Meaning |
|---|---|---|
| `param_id` | str, `snake_case` | Unique within the block; the key in `nodes[].params` |
| `type` | see §5.2 | Parameter type |
| `default` | JSON value of `type` | Used when the pipeline does not set the parameter. Never `null` (no nullable parameters in v1) |
| `label_key` | str | Default `blocks.<block_id>.params.<param_id>` |
| `tooltip_key` | str | Default `blocks.<block_id>.params.<param_id>.tip` |
| `advanced` | bool | `true` = shown under "Advanced" in the inspector |

Optional fields, present only when set:
| Field | Types | Meaning |
|---|---|---|
| `min`, `max` | `int`, `float` | Inclusive bounds (numbers) |
| `odd_only` | `int` | `true` = value must be odd (e.g. Savitzky–Golay window) |
| `choices` | `enum` (required there) | Allowed values: a non-empty list of JSON scalars of one kind (all str, all int, all float or all bool), no duplicates; `default` is one of them |
| `unit` | `int`, `float` | Display unit of the value, e.g. `nm`, `cm-1`, `%`, `s`; text, not translated |
| `constraint` | `int`, `float` | Cross-field rule `"<param_id> <op> <operand>"`: the left side is this parameter, `<op>` ∈ `<` `<=` `>` `>=` `!=`, `<operand>` is another `int`/`float` parameter of the block or a number. Example: `"polyorder < window"`. Single spaces around `<op>`; parsed, never evaluated as code |
| `visible_if` | any | `{ "param_id": "<other>", "values": [...] }`: the inspector shows this field only while the other parameter (type `bool` or `enum`) has one of `values`. A hidden parameter keeps its value and is still validated |

### 5.2 Types
| `type` | JSON value | Extra fields | Status |
|---|---|---|---|
| `int` | integer (not `true`/`false`) | `min`, `max`, `odd_only`, `unit`, `constraint` | implemented |
| `float` | number, finite; integers are accepted and stored as float | `min`, `max`, `unit`, `constraint` | implemented |
| `bool` | `true` / `false` | — | implemented |
| `enum` | one of `choices` (same kind: `1` does not match `true`, `"1"` does not match `1`; JSON has one number type, so an integer matches a float choice: `1` selects `1.0`) | `choices` | implemented |
| `string` | string | — | implemented |
| `range` | `[low, high]` numbers, `low <= high` | `min`, `max`, `unit` | *reserved*: shape fixed, `Param` refuses it until the first block that needs it |
| `wavelength_range` | `[low, high]` in the unit of the input spectral axis; checked against the axis at run time | — | *reserved* |
| `wavelength_ranges` | `[[a, b], ...]`: at least one pair of finite numbers in the unit of the input spectral axis, each pair in either order (stored as `[min, max]` when parsed); checked against the axis at run time by the block: no axis point selected → `BLOCK_PARAM_INVALID` reason `constraint` | — | implemented *(T1.07)* |
| `column_ref` | string: a column name of the input data | `roles`: subset of `y`, `class`, `group`, `metadata` the column may have | *reserved* |
| `list` | array of scalars | `item_type` (`int`\|`float`\|`string`), `min_items`, `max_items` | *reserved* |
A reserved type is implemented (and this table updated to "implemented") in the step of the first block that needs it.

### 5.3 Validation of values
`vibechem_core.block.parse_params(params_type, values)` turns the `nodes[].params` object into the block's params dataclass. Missing parameters take their `default`. The first problem found raises `BLOCK_PARAM_INVALID` (§7) with `params`: `param_id`, `reason` and, when it helps the message, `value` (scalars only) and `constraint`. When `params` itself is not a JSON object: `reason` `type` without `param_id`.
| `reason` | When |
|---|---|
| `unknown` | Key that is not a `param_id` of the block |
| `type` | Value of the wrong JSON type, or a non-finite float; for `wavelength_ranges` also an empty list or an item that is not a pair of finite numbers |
| `below_min` / `above_max` | Outside `min` / `max` |
| `not_odd` | `odd_only` and the value is even |
| `not_a_choice` | `enum` value not in `choices` |
| `constraint` | A `constraint` is false (checked after every value is valid) |
In `POST …/validate` (§2.6) it is an `error` issue with `node_id`; raised while a block runs, it sets the node to `error` (§3). Block definitions are checked when a block is registered: defaults must pass the same rules, and `constraint`/`visible_if` must name another parameter of a suitable type (definition mistakes raise `TypeError`/`ValueError`, not a code).

### 5.4 Open points for review
1. Constraint as a restricted string (above, keeps the §2.3 form) vs. a structured object `{ "left", "op", "right" }`.
2. One code `BLOCK_PARAM_INVALID` with a `reason` param vs. one code per reason.
3. `visible_if` with one condition only; `and`/`or` combinations wait for a block that needs them.

## 6. File formats *(DRAFT, T2.03 — Quan reviews)*
Code: `vibechem_engine.formats` (pydantic models, `load_*`/`save_*`, `read_model`/`write_model`). JSON Schemas (exported from the models, kept in sync by a test): `packages/engine/src/vibechem_engine/formats/schemas/{pipeline,project,model_manifest}.schema.json`. No pickle anywhere (ADR-007; a test scans `packages/*/src`).

### 6.1 Common rules
- UTF-8 JSON, `snake_case` keys, timestamps `YYYY-MM-DDTHH:MM:SS[.fff]Z`. Written with LF line endings, through a temporary file that replaces the target (no half-written file after a crash).
- Every file carries an integer `format_version`. **Unknown keys are rejected**; any field change bumps `format_version` and ships a migration (§6.5). (The API's "ignore unknown fields" rule, §1, is for HTTP clients, not files.)
- Values must have their exact JSON type (no `"12"` for `12`, no `true` for `1`); integers are accepted where a number is expected. `NaN`, `Infinity`, numbers that overflow to infinity (e.g. `1e400`) and a key repeated within one object are rejected. Timestamps must be real dates and times in ASCII digits.
- A JSON file larger than 16 MiB is rejected before parsing.
- An invalid file raises the format's code (§7) with `params.reason`:
| `reason` | Extra params | When |
|---|---|---|
| `json` | `detail` | Not UTF-8, not JSON, not an object, NaN/Infinity/overflow, repeated key |
| `too_large` | `limit` (bytes) | Over the size limit |
| `schema` | `location` (dotted path, e.g. `nodes.1.node_id`; `""` for whole-document rules), `detail` (English) | First field that breaks the schema or a rule below; also a migration that fails on a malformed old file |
| `version` | `found` (int or null), `supported` | `format_version` missing, newer than this app, or without a migration path |
| `zip`, `entry`, `state` | see §6.4 | Model packages only |

### 6.2 Project folder and `project.json`
Folder layout (ARCHITECTURE.md §2.3): `project.json` · `data/<dataset_id>/` (dataset storage: defined by the project/dataset step) · `pipelines/<pipeline_id>.vcp.json` · `cache/` (index and entries: T2.06) · `models/*.vcm` · `reports/`. All references inside the folder are relative (ADR-006).

`project.json` (format 1):
| Field | Type | Notes |
|---|---|---|
| `format_version` | `1` | |
| `project_id` | `prj_…` | |
| `name` | str, non-empty | |
| `created_at`, `updated_at` | timestamp | |
| `datasets` | `ds_…`[] | Unique; order = display order; each is `data/<dataset_id>/` |
| `pipelines` | `ppl_…`[] | Unique; order = display order; each is `pipelines/<pipeline_id>.vcp.json` |
No absolute `path`: the API manifest's `path` (§2.4) is where the engine opened the folder. Loading migrates in memory; writing the upgraded file back after the `project.json.bak-{timestamp}` backup (§2.4) is done by project open. Invalid → `PROJECT_FILE_INVALID`.

### 6.3 Pipeline file `pipelines/<pipeline_id>.vcp.json`
The pipeline document of §2.6, format 1:
| Field | Type | Notes |
|---|---|---|
| `format_version` | `1` | |
| `pipeline_id` | `ppl_…` | |
| `name` | str, non-empty | |
| `revision` | int ≥ 0 | §1 concurrency control |
| `nodes` | node[] | `node_id` unique |
| `edges` | edge[] | `edge_id` unique; order = order of a `multiple: true` input's edges (§4.4) |
| `created_at`, `updated_at` | timestamp | |

Node: `node_id` (`nd_…`), `block_id` (as in the block registry), `block_version` (`MAJOR.MINOR.PATCH`), `params` (JSON object, values checked against the block's schema by `parse_params`, §5.3), `position` `{x, y}` (numbers), `label` (str or null). Edge: `edge_id` (`eg_…`), `from_node`, `from_port`, `to_node`, `to_port` (port ids `snake_case`). Ids after the prefix are `[0-9A-Za-z]+` (ULIDs in practice).
Checked at load beyond the JSON Schema: unique node and edge ids, every edge names existing nodes (RISKS R50). Port names, port types, required inputs and cycles are graph validation (`vibechem_engine.graph`, §4.4), not file validity. Invalid → `PIPELINE_FILE_INVALID`.
**Container frames (§4.6):** v1 stores no frame. A nested-CV or grid-search frame is derived from the graph: the validation node plus the subgraph feeding its `refit_per_fold` port. §4.7.2 is decided for this (`refit_per_fold`, Quan 2026-11-27).

### 6.4 Model package `models/<name>.vcm`
A zip (stored or deflate) with exactly these entries:
```
manifest.json
states/<i>/state.json          i = 0 … len(states) − 1
states/<i>/arrays/<j>.npy      layout of vibechem_core.block.save_state (T1.02b)
```
State layout (T1.02b, adopted): `state.json` = `{"state_version": 1, "values": {<JSON>}, "arrays": ["<name>", …]}`, `arrays/<j>.npy` for the j-th name (files named by position, so names never become paths), loaded with `allow_pickle=False`.
`manifest.json` (format 1):
| Field | Type | Notes |
|---|---|---|
| `format_version` | `1` | |
| `name` | str, non-empty | §2.10 `model.name` |
| `vibechem_version` | str | App version that wrote it |
| `trained_at` | timestamp | |
| `pipeline` | pipeline document (§6.3) | The nodes needed to apply the model; which nodes, and the applicability-domain content, are defined by the export / predict steps (F-70, F-71) |
| `states` | `[{node_id, block_id, block_version}]` | One per fitted node; `states[i]` is stored in `states/<i>/`. Each must match a pipeline node's `block_id` and `block_version`, `node_id` unique — so a state can never be given to another block (RISKS R35) |
Reading refuses (code `MODEL_PACKAGE_INVALID`): not a zip / corrupt / truncated / encrypted or patched entries / other compression → `reason: zip` (`detail`); any other entry name, a repeated entry, a missing `manifest.json`, or a `states/<i>/` with no manifest entry → `reason: entry` (`entry`); more than 10 000 entries, total declared uncompressed size > 2 GiB or `manifest.json` > 16 MiB → `too_large`; state indexes are ASCII without leading zeros, at most 9 digits; a state `load_state` rejects (pickled or object array, bad `state.json`, missing file, an extra array file, a `.npy` header whose shape needs more bytes than the file holds) → `reason: state` (`index`, `detail`); manifest problems → `json` / `schema` / `version` as §6.1. The embedded pipeline is migrated with the pipeline migrations; its `version` error carries `location: "pipeline"`. Unpacking writes only to a temporary folder, under names that passed the entry check.

### 6.5 Versions and migrations
`vibechem_engine.formats.migrations`: `CURRENT_VERSIONS` (`pipeline`, `project`, `model`: all 1) and one function per step, registered with `@migration(kind, from_version)`, that takes the parsed JSON of version n and returns version n + 1 (it must set `format_version`). Loading runs the chain up to the current version, then validates. A file newer than the app, or with no path, → `reason: version`. Example (in `tests/formats/test_pipeline.py`): a format 2 that renames node `label` to `title`. Block versions (`block_version`) are separate: a block's own parameter changes are handled by the block (later step), not by the file format.

### 6.6 `.vcz` project archive and cache index
`.vcz` = zip of the project folder (`cache/` left out unless `include_cache`), to be read with entry checks like §6.4; built and specified in detail by the export step.

**Cache folder `cache/` (T2.06, `vibechem_engine.cache`).** Key: `result_key` = `res_` + SHA-256 of the canonical JSON (sorted keys, `","`/`":"` separators, ASCII, no NaN) of `{key_version: 1, kind, block_id, block_version, params, inputs: [[port_id, input result key, rule], …] (sorted by port, edge order kept within a port), seed, fold, part, output}`, one key per task output. Task and node ids are not hashed.
```
cache/entries/<64 hex>/state.json       one State, layout of save_state (§6.4)
cache/entries/<64 hex>/arrays/<j>.npy
cache/entries/<64 hex>/entry.json       {"entry_version": 1, "key": "res_…", "size_bytes": int, "files": {"state.json": "<sha256>", "arrays/0.npy": "<sha256>", …}}
cache/tmp/                              staging; an entry is written here and renamed into entries/
```
There is no global index file: the index is the set of `entry.json` files, read when the cache is opened (`tmp/` is emptied then). `size_bytes` = the data files (not `entry.json`); recency (LRU) = the `entry.json` modification time, set on every put and hit. After a put, least recently used entries are deleted until the total is ≤ `cache_cap_bytes` (§2.2 settings), never the entry just written; the freed bytes are the `cache.evicted` event's `freed_bytes`. An entry whose `entry.json` is invalid, whose folder name differs from its key, or whose file fails its checksum or `load_state` is deleted and counts as a miss (recompute, ARCHITECTURE §3.6).

## 7. Error codes catalogue
Each code is defined in exactly one module (listed), so searching for a code finds its origin (QA.md §5). This table is the single registry of codes, errors and warnings alike (ARCHITECTURE.md ADR-010). Rows marked *warning* use the translation key `warnings.<area>.<name>` instead of `errors.<area>.<name>`; a block warning (*warning (node)*) is raised as `VibeChemWarning` and does not stop the node.
| Code | HTTP / where | Defined in | Meaning |
|---|---|---|---|
| `AUTH_TOKEN_INVALID` | 401 | `engine/api` | Missing or wrong session token |
| `ORIGIN_FORBIDDEN` | 403 | `engine/api` | Request not from the app |
| `PROJECT_PATH_NOT_EMPTY` | 409 | `engine/project` | Create into a non-empty folder |
| `PROJECT_PATH_NOT_WRITABLE` | 422 | `engine/project` | No write permission |
| `PROJECT_ALREADY_OPEN` | 409 | `engine/project` | Another project is open |
| `IMPORT_FORMAT_UNKNOWN` | 422 | `core/io` | File type not recognised (`params.format`: the extension or `format_hint`) |
| `IMPORT_FILE_INVALID` | 422 | `core/io` | The file cannot be read as a table: `params.reason` ∈ `encoding` (not UTF-8), `empty` (also: a spectrum with fewer than 2 points), `no_spectra` (headerless file with one column), `row_length` (+ `row`, `expected`, `found`), `duplicate_column` (+ `column`; also a clash between merged files), `corrupt` (unreadable Excel, JCAMP-DX, SPC, SPA, PerkinElmer, WDF or OPUS file, e.g. truncated, or a point count that disagrees with the header) *(proposed T1.05; vendor formats T1.06b)*; `unsupported` (+ `feature` ∈ `compound`, `peak_table` for JCAMP-DX, `spc_version` + `version` for SPC; `wdf_map` for WDF maps, `opus_block` + `block` and `opus_series` for OPUS *(proposed T1.06b)*), `axis` (axis values not finite and strictly monotonic) *(proposed T1.06)* |
| `IMPORT_DUPLICATE_SAMPLE_IDS` | warning | `core/io` | Repeated sample IDs (`params.count`: number of IDs that occur more than once) |
| `IMPORT_NON_NUMERIC_VALUES` | warning | `core/io` | Spectral cells that are empty or not finite numbers, read as NaN (`params.count`, `params.column`: the first such column) *(proposed T1.05)* |
| `IMPORT_AXIS_MISMATCH` | warning | `core/io` | Spectra on different axes were put on the union axis, missing points NaN; the import result has `needs_interpolation: true` (`params.axes`: number of distinct axes) *(proposed T1.06)* |
| `DATASET_IN_USE` | 409 | `engine/project` | Dataset referenced by a pipeline |
| `PIPELINE_REVISION_CONFLICT` | 409 | `engine/api` | Stale `If-Match` revision |
| `PIPELINE_PORT_TYPE_MISMATCH` | 422 | `engine/graph` | Incompatible edge |
| `PIPELINE_REQUIRED_INPUT_MISSING` | 422 | `engine/graph` | Unconnected required port |
| `PIPELINE_CYCLE` | 422 | `engine/graph` | Graph has a cycle |
| `PIPELINE_INPUT_MULTIPLE_EDGES` | 422 | `engine/graph` | Second edge into an input with `multiple: false` (§4.4) |
| `PIPELINE_FOLDS_SOURCE_MISMATCH` | 422 | `engine/compiler` | Folds and the re-fitted subgraph come from different datasets (§4.6) |
| `PIPELINE_LEAKAGE` | 422 | `engine/compiler` | Fit step would see validation/test data |
| `PIPELINE_RUNNING` | 409 | `engine/api` | Change blocked during run |
| `RUN_ALREADY_ACTIVE` | 409 | `engine/scheduler` | Run already active on this pipeline/project |
| `RUN_OUT_OF_MEMORY` | node error | `engine/scheduler` | A task ran out of memory again after the concurrency was halved and it was retried alone; the message advises fewer cores, a higher memory budget or smaller data *(proposed T2.09)* |
| `RESULT_TOO_LARGE_USE_EXPORT` | 413 | `engine/api` | Use export for very large data |
| `EXPORT_FORMAT_UNAVAILABLE` | 422 | `engine/api` | Format needs the desktop app (e.g. PDF) |
| `MODEL_PACKAGE_INVALID` | 422 | `engine/formats` | Bad or unsafe model file (`params.reason`, §6.4) |
| `PIPELINE_FILE_INVALID` | 422 | `engine/formats` | A pipeline file breaks §6.3 (`params.reason`, §6.1) *(proposed T2.03)* |
| `PROJECT_FILE_INVALID` | 422 | `engine/formats` | `project.json` breaks §6.2 (`params.reason`, §6.1) *(proposed T2.03)* |
| `MODEL_AXIS_MISMATCH` | 422 | `engine/formats` | New data's axis doesn't match the model |
| `VALIDATION_GROUPS_IGNORED` | warning | `core/blocks/validate` | Groups exist but CV ignores them (`params.n_groups`); raised by `validate.cv` when its `Folds` have `groups_respected = false` *(moved from `engine/graph`, T2.10a; hold-out splits still open, R25)* |
| `VALIDATION_FOLDS_INVALID` | node error | `core/blocks/validate` | CV `Folds` are not a partition: a row is predicted twice (`params.reason` = `duplicate_prediction`) or never (`missing_prediction`) in repeat `params.repeat` (METHODS.md N23) *(proposed T2.10a)* |
| `BLOCK_CONSTANT_SPECTRA` | node error | `core/blocks/preprocess` | A spectrum has zero variance (e.g. SNV cannot scale it): `params.rows` (row positions), or `params.reference` (`mean`/`input`) when the MSC reference is constant *(params proposed T1.07)* |
| `BLOCK_MSC_SLOPE_INVALID` | node error | `core/blocks/preprocess` | MSC: a spectrum's fitted slope on the reference is ≤ 0 (anti-correlated or constant spectrum); `params.rows` *(proposed T1.07)* |
| `BLOCK_AXIS_NOT_UNIFORM` | warning (node) | `core/blocks/preprocess` | Savitzky–Golay: the axis steps deviate by more than 1 % from the mean step, so derivatives are taken per point (`params.max_deviation`: largest relative deviation, e.g. `0.46`) *(proposed T1.08)* |
| `BLOCK_CONSTANT_COLUMNS` | warning (node) | `core/blocks/preprocess` | Autoscaling/Pareto: training columns with zero variance are centred and left unscaled (scale 1) (`params.columns`: column positions in X, or in y with `target = y`) *(proposed T1.09)* |
| `BLOCK_MISSING_VALUES` | node error | `core/blocks/split` | Guard error (METHODS.md N1, N14): a block received NaN in X or in a used y, which only direct Python API calls can cause (the engine removes such rows at entry); `params.port_id`. Raised by the split blocks and `model.pls` (T1.12a); other blocks do not check yet *(proposed T1.10)* |
| `BLOCK_CONSTANT_RESPONSE` | node error | `core/blocks/split` | SPXY: every response value is equal (with `group_aware`: every group-mean value, BUG #58), so the y term of the joint distance is undefined (METHODS.md N13; no fall-back to Kennard–Stone); `params.port_id` *(proposed T1.10)*. PLS (`model.pls`): every training y column is constant *(proposed T1.12a)* |
| `BLOCK_PLS_COMPONENTS_CAPPED` | warning (node) | `core/blocks/model` | PLS with `n_components_mode = search_max`: the searched maximum LV count is above n_min = min(n_train − 1, p) and was capped (`params.from`, `params.to`) (Quan 2026-11-26) *(proposed T1.12a)* |
| `BLOCK_PLS_EQUIVALENT_MLR` | warning (node) | `core/blocks/model` | PLS fitted with n_min = min(n_train − 1, p) components: equivalent to multiple linear regression (least squares, no latent-variable regularisation; with p ≥ n the training rows are fitted exactly) (`params.n_components`) (Quan 2026-11-26) *(proposed T1.12a)* |
| `BLOCK_SPLIT_STRATUM_TOO_SMALL` | warning (node) | `core/blocks/split` | Stratified random split: strata with fewer than 2 sampling units are put in training (`params.strata`: stratum labels — class names, or y-bin numbers from 0) *(proposed T1.10)* |
| `BLOCK_PLS_PRECISION_LOST` | warning (node) | `core/blocks/model` | PLS with `algorithm = simpls`: the scores of the first `params.n_components` components deviate from orthonormal by more than 1e-6 (`params.max_deviation`: largest deviation), so the components from that LV count on are dropped (set to 0; predictions for more LVs equal those for one LV fewer); NIPALS keeps them (METHODS.md#simpls) (decided, Quan 2026-11-26) |
| `METRIC_UNDEFINED` | warning | `core/metrics` | A metric cannot be computed for the set and is NaN (METHODS.md §8): `params.metric` (result name, e.g. `secv`, or `sensitivity`/`specificity`/`auc` with `params.class`), `params.reason` ∈ `n_lt_2`, `constant_y`, `constant_prediction` (slope/intercept), `zero_rmse` (RPD/RPIQ of a perfect fit), `class_absent`, `only_class` |
| `METRIC_FEW_SAMPLES` | warning | `core/metrics` | CV or test set smaller than ISO 12099:2010 asks for: `params.metric` (`secv`/`sep` with `params.minimum` 20, `bias_cv`/`bias_p` with 10), `params.n` |
| `METRIC_CLASSES_UNBALANCED` | warning | `core/metrics` | The true classes of a classification set are unbalanced: imbalance ratio largest/smallest class count `params.ratio` > `params.threshold` (parameter `imbalance_ratio`, default 1.5); the class-size-weighted means `sensitivity_w_*`, `specificity_w_*`, `auc_w_*` are added next to the macro means (METHODS.md N22, N27). `params.set` ∈ `c`, `cv`, `p` *(proposed T2.10a, for Quan; raised from T2.10b)* |
| `BLOCK_INPUT_REQUIREMENT_MISSING` | node error | `core/block` | Input lacks content the port `requires` (Y, classes, groups, spatial, predictions) (§4.3); scaling blocks with `target = y` raise it themselves when y is absent or its columns differ from the fitted ones (`params.port_id`, `params.requirement` = `y`, `params.expected`: fitted y column names) *(proposed T1.09)*; `model.pls` raises it on `y_transform` (`params.port_id` = `y_transform`) when the transform is not a `target = y` scaling of the same y columns fitted on the same training rows (its y is not centred) *(proposed T1.12a)*; grouped CV schemes (group k-fold, leave-one-group-out) also raise it, `requirement` = `groups`, when a group label is empty *(proposed T1.11)*; so do the split blocks with `group_aware` (BUG #58) |
| `BLOCK_INPUT_ROWS_MISMATCH` | node error | `core/block` | `rows_match` inputs share too few sample IDs (§4.5) |
| `BLOCK_INPUT_AXIS_MISMATCH` | node error | `core/block` | Input axis differs from the matched port or the fitted state's axis (§4.5) |
| `BLOCK_PARAM_INVALID` | 422 (validate issue) / node error | `core/block` | A parameter value breaks its schema: unknown key, type, bounds, odd, choices or constraint (`params.reason`, §5.3) *(proposed T1.03)* |

# VibeChem — Product Requirements (PRD)

> Status: v0.5 · Owner: Quan (personal project) · Last updated: 2026-11-17
> Feature IDs (F-xx) are stable references for Claude Code, issues and commits. Do not renumber; add new IDs.
> v0.5 merges product decisions (former DECISIONS.md) and the Quasar analysis (former COMPETITOR_QUASAR.md, Appendix A).
> What to build: this file + FUNCTION_CATALOG.md · How: ARCHITECTURE.md, TECH_STACK.md, DATA_MODEL.md, UI_GUIDE.md · Quality: QA.md · Steps: TASKS.md

## 1. Product statement
VibeChem is a free, open-source (GPL-3.0-or-later) **installable desktop application** for **chemometrics on vibrational and hyperspectral data**, with conventional statistics and publication plotting. Users build analyses as a **visual pipeline of symbol blocks** — grouped into classes, connected freely, each opening a detailed configuration — and get **rigorous, publication-grade validation** by default.

Name: *Vib*rational spectroscopy + *Chem*ometrics; also *vibecoded* (≈80–90 % AI-generated; architecture and infrastructure reviewed by K, algorithms by Quan).

## 2. Positioning — why VibeChem wins ("ăn tiền")
| | PLS_Toolbox / Unscrambler | Quasar (Orange + Spectroscopy) | **VibeChem** |
|---|---|---|---|
| Cost | Paid licence | Free, GPL-3 | Free, GPL-3 |
| Workflow | Menus/dialogs | Visual widget graph, general ML | Visual block pipeline, chemometrics-native |
| Main strength | Mature, broad chemometrics | Broad, polished exploratory analysis | **Spectra → validated, transferable, deployable model** |
| Validation | Expert configures | Per-fold preprocessing, grouped CV, permutation test; no nested CV | **Nested CV tuning LVs + preprocessing + selection jointly** |
| Preprocessing search | Manual | Manual | **Automated chain search with leaderboard** |
| Variable selection | Several methods | Generic feature ranking | **Chemometric suite with fold stability** |
| Calibration transfer | Paid add-ons | Not documented | **DS, PDS, SST, EPO, GLSW, di-PLS …** |
| Parallel computing | Limited | Limited | **Parallel pipeline + CV/search by default** |
| Deployment & citation | Proprietary files | Save model + Predictions | **Model package + applicability domain + code export + auto-bibliography** |

## 3. Target users
| Persona | Need | Implication |
|---|---|---|
| **P1 Graduate student / early researcher** (primary) | Correct model without a paid licence; learn why each step matters | Defaults, student tooltips, guard-rails |
| **P2 Experienced chemometrician** | Fast, reproducible nested-CV pipelines, transfer methods, full control | All parameters exposed; parallel compute; code export |
| **P3 Applied lab / QC analyst** | Apply and transfer validated models across instruments | Predict mode, applicability domain, calibration transfer |
First cohort: researchers and students in Japan and Vietnam (EN/JA/VI). Personas are validated by interviews (PROJECT.md §4).

## 4. Scope and features
**Functional scope = every function in FUNCTION_CATALOG.md, released by tier** (P0 → v1.0, P1 → v1.1–1.3, P2 → v1.4+, P3 → v2+). Below: product behaviour every function relies on.

### 4.1 Pipeline canvas (signature)
- **F-01 Block canvas.** Classes: Data, Explore, Preprocess, Split, Validate, Select, Model, Transfer, Statistics, Imaging, Deploy (names confirmed by card sort). One symbol per function; drag and connect.
- **F-02 Live data position.** States `idle · queued · running · done · stale · error`; "data here" marker on the furthest computed block of each branch.
- **F-03 Inspect any block.** Click → configuration + output preview (plot, shape, summary, input vs output).
- **F-04 Stale propagation & partial re-run.** Only changed and downstream blocks re-run (content-addressed cache).
- **F-05 Pipelines & templates.** Save/load; named templates separate from data; built-in templates.
- **F-06 Guided mode.** Same pipeline as a step-by-step wizard with context warnings ("replicates detected → use group CV").
- **F-07 Multi-port typed blocks.** Any number of named, typed inputs/outputs (e.g. PDS: `master`, `slave`, `transfer_samples` → `transform`, `corrected`); fan-out; DAG; incompatible connections refused with an explanation (types in DATA_MODEL.md §4).
- **F-08 Student tooltips.** Every block, parameter and metric: ≤ 2 sentences (what + when) and "Learn more" with figure and reference; expert mode hides them; EN/JA/VI.

### 4.2 Validation integrity (core differentiator)
- **F-42 Leakage-safe by construction.** Fitted steps fit on training folds only, enforced by the compiler (ARCHITECTURE.md §3.2); "Leakage-safe ✓" badge; leaky pipelines cannot run.
- **F-43 Nested CV.** Outer loop for performance; inner loop jointly tunes LVs, preprocessing and selection; any CV scheme per level.
- **F-44 Chemometric metrics.** RMSEC/CV/P, R²c/cv/p, bias, SEP, slope, RPD, RPIQ (original units); accuracy, per-class sensitivity/specificity, confusion matrix, ROC-AUC.
- **F-45 Diagnostics.** RMSECV-vs-LV curve, predicted vs measured, residuals, T²/Q, permutation test.

### 4.3 Deploy, reproducibility, citation
- **F-70 Model package** (versioned, no pickle) · **F-71 Predict mode** with applicability-domain flags · **F-72 Report** (HTML/PDF, methods paragraph) · **F-73 Python export** · **F-74 Run provenance** (pipeline, seeds, data hash, versions).
- **F-75 Method citations.** Each block carries its references; reports list exactly the methods used (BibTeX/RIS); Help → Cite VibeChem (CITATION.cff, Zenodo DOI).

### 4.4 Platform
- **F-80 Languages** EN, JA, VI; all strings externalised.
- **F-81 Installer** for Windows, macOS, Linux on GitHub Releases; offline; no Python install needed; built in CI from Phase 0; unsigned in v1.0 with first-launch guide.
- **F-82 Update check** (notification only).
- **F-83 Parallel computing.** Independent branches concurrently; folds, nested loops, searches, permutations, bootstrap, pixel predictions in parallel workers; "CPU cores to use" setting (default all but one); progress, ETA, cancel; memory guard; identical results for any core count; GPU later (P2).
- **F-84 Crash resilience.** Failing block or native kernel never closes the app or loses work; engine restarts and reopens the project.

## 5. Out of scope (all versions unless revisited)
User accounts, cloud sync, multi-user collaboration · instrument control / live acquisition · commercial licensing or paid tiers · telemetry in v1 (any future telemetry opt-in only).

## 6. Releases
| Release | Content |
|---|---|
| v1.0 | Catalog P0 + all F-features |
| v1.1–1.3 | Catalog P1 (calibration transfer first) |
| v1.4+ | Catalog P2 (hyperspectral imaging core, domain adaptation) |
| v2+ | Catalog P3, VibeChem Lite (hosted web), deep learning |

## 7. Success criteria for v1.0
1. A new grad student goes from CSV to a nested-CV PLS model with report in < 30 min using a template.
2. Every P0 function matches its reference within METHODS.md tolerances (automated).
3. A saved pipeline reproduces identical metrics on another machine and any core count.
4. Nested CV on 500 × 1,500 runs ≥ 4× faster on 8 cores than on 1.
5. 5–10 external users (JA and VI speakers) complete a real analysis and give feedback.
6. A Quasar user can do every "parity" task in Appendix A.
7. Usability: SUS ≥ 70; core tasks ≥ 80 % unaided success (PROJECT.md §4).

## 8. Non-functional requirements
Performance, scale, robustness, security: ARCHITECTURE.md §1.2 and §3. Quality rules: QA.md. Offline; user data stays local.

## 9. Product decisions (log)
| ID | Date | Decision |
|---|---|---|
| D-015 | 2026-11-17 | v1.0 ships unsigned (zero cost); later SignPath Foundation (Windows, free for OSS) and Apple Developer Program (USD 99/year) |
| D-013 | 2026-11-17 | Licence GPL-3.0-or-later |
| D-009 | 2026-11-16 | Scope = everything, prioritised in FUNCTION_CATALOG.md |
| D-008 | 2026-11-16 | Personal project, no institutional affiliation; citation-ready from first release |
| D-007 | 2026-11-16 | Compete with Quasar on depth of the predictive workflow first |
| D-006 | 2026-11-16 | EN/JA/VI in v1 |
| D-004 | 2026-11-16 | Minimalist monochrome UI, colour only for meaning |
| D-003 | 2026-11-16 | Block canvas is the signature interaction |
| D-002 | 2026-11-16 | Vibrational spectroscopy first; general chemistry data later |
| D-001 | 2026-11-16 | Free and open source, by and for researchers |
Technical decisions: ARCHITECTURE.md §7–8.

---

## Appendix A — Quasar comparison (from official docs, 2026-11-16; verify in the app)
Quasar = Orange 3 core (~110 general ML widgets) + Orange-Spectroscopy (15 widgets), GPL-3.0.

**Parity required for v1.0** (Quasar features our users rely on): Spectra viewer QoL (click/line selection, group mean ± SD, peak labels, invert X, zoom/fit shortcuts, curve resampling, image export) · full Preprocess Spectra set (cut, Gaussian/SG smoothing, baseline incl. ALS, normalisations, SNV, EMSC, spike removal, PCA denoising, T↔A, shift; atmospheric correction in v1.1) · Interpolate · Average · Multifile import · Integrate · SNR · PCA, HCA, k-Means · scatter/box/violin/distributions/heat map · per-fold preprocessing, grouped CV, permutation test · reports, saved workflows, save/load model, predictions.

**Quasar strengths we must not claim as differentiators:** per-fold preprocessing via Test & Score, grouped CV ("cross validation by feature"), permutation plot, one-parameter tuning (Parameter Fitter), Python Script widget.

**Gaps = VibeChem's opportunity (per docs):** no nested CV; tuning limited to one integer parameter · no preprocessing-chain search · no chemometric variable selection (VIP, SR, CARS, SPA, iPLS, Jackknife) · minimal PLS outputs · generic ML metrics instead of RMSECV/SEP/RPD/RPIQ · no Kennard–Stone/SPXY, venetian or contiguous CV · no applicability domain at prediction · no code export or methods text.

**Not planned:** CN2 rules, Pythagorean trees, nomogram, sieve/mosaic, FreeViz/Radviz, Louvain, SOM, text/network add-ons. Hyperspectral maps, peak fit, interferograms are in the catalog at P1–P3.

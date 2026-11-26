# VibeChem — Function Catalog & Priority List

> Status: v0.5 · Last updated: 2026-11-25
> v0.5: T1.00b pengoo port inventory — "Likely source" notes name the pengoo function to port (per-function decisions and defects to fix in TECH_STACK.md §11.2); rows marked *proposed (T1.00b)* await Quan's approval.
> v0.4: T1.00 Quasar port inventory — "Likely source" notes name the Quasar/Orange module to port or the library to wrap instead (osp = orange-spectroscopy, o3 = Orange3, commits and per-module decisions in TECH_STACK.md §11.1); rows marked *proposed (T1.00)* await Quan's approval.
> v0.3: pengoo wording ("ported from pengoo"); reuse sources per class; PDF via desktop app.
> Goal: include every function that serves chemometrics, vibrational & hyperspectral data, conventional statistics and plotting. Nothing is cut; everything is **ordered**.
> Each function becomes one block (or a mode of one block). Every block must have: an icon, a student tooltip, a method reference (auto-citation), a METHODS.md entry and a reference test (QA.md §3).
> **Reuse first (ARCHITECTURE.md ADR-009):** before building any block, check the "Likely source" notes below and TECH_STACK.md §11. These are candidates, not decisions — each step confirms them.

## Priority tiers
| Tier | Release | Rule |
|---|---|---|
| **P0** | v1.0 | Required to go from raw vibrational spectra to a validated, published, deployable model. Release-blocking. |
| **P1** | v1.1–v1.3 | High value; widens coverage (calibration transfer, more models/selection, Quasar breadth). |
| **P2** | v1.4–v1.x | Specialist methods, hyperspectral imaging core, domain adaptation. |
| **P3** | v2+ | Research-grade / niche, deep learning, advanced imaging. |

Within a tier, build in table order. Owner may promote any item. If v1.0 runs late, the cut list in PROJECT.md §3 decides which P0 items move to v1.1.

---

## 1. Data input/output
*Likely source: pandas/pyarrow (CSV, Excel), `jcamp` (JCAMP-DX); SPC → port osp `utils/spc` (Rohan Isaac's `spc`, GPL-3.0) or `spc-io` (T1.06 decides); OPUS → wrap `brukeropus` (Quasar's `opusFC` rejected); OMNIC SPA, PerkinElmer .sp → port osp `io/omnic.py`, `io/perkinelmer.py` + `utils/specio`; Renishaw WDF → wrap `renishawWiRE`; .mat → `scipy.io` (osp `io/matlab.py` role rules); ENVI → `spectral`; Agilent FPA → `agilent-format`; OMNIC map → port osp `utils/pymca5` (MIT); multi-file behaviour from osp `owmultifile`.*
| Function | Tier |
|---|---|
| CSV/TSV, Excel import with column-role assignment | P0 |
| JCAMP-DX, Thermo SPC | P0 |
| Multi-file import + concatenate | P0 |
| Merge metadata table by sample ID | P0 |
| Export data/results (CSV, Excel), save project | P0 |
| Bruker OPUS | P1 |
| Thermo OMNIC SPA, PerkinElmer .sp, Renishaw WDF *(proposed (T1.00); from "Other vendor formats")* | P1 |
| MATLAB .mat, HDF5, NumPy | P1 |
| Hyperspectral cubes: ENVI (.hdr/.raw), Specim, .mat cube | P2 |
| Other vendor formats (on user request) | P3 |

## 2. Data handling
*Likely source: interpolation → port osp `preprocess` `Interpolate`/`InterpolateToDomain` + NaN helpers in `preprocess/utils.py` (on SciPy `interp1d`); average by group → port osp `owaverage.average_table`; impute → scikit-learn `SimpleImputer` (o3 `impute.py` not ported).*
| Function | Tier |
|---|---|
| Select / exclude rows and columns (with logged reason) | P0 |
| Interpolate / resample to common axis | P0 |
| Average replicates by group | P0 |
| Missing values: detect, remove, impute | P0 |
| Derived columns (formula), group-by aggregate | P1 |
| Data augmentation (noise, shift, scatter simulation) | P3 |

## 3. Exploration & plotting
*Likely source: scikit-learn (PCA, clustering, t-SNE), SciPy (dendrogram; small tree helpers `prune`/`top_clusters` ported from o3 `clustering/hierarchical.py`), `umap-learn` (if approved); 2D-COS → port osp `owcos.calc_cos` (check against R `corr2D`); SNR → port osp `owsnr`; plots drawn in the UI (uPlot); spectra-viewer QoL list from osp `owspectra` (spec only).*
| Function | Tier |
|---|---|
| Spectra viewer (Quasar-level QoL: group mean ± SD, line select, peak labels, shortcuts, resampling) | P0 |
| PCA: scores, loadings, biplot, explained variance, T²/Q | P0 |
| Scatter, line, box/violin, histogram/KDE, bar | P0 |
| Heat map, correlation matrix, correlation spectrum (X vs Y per wavelength) | P0 |
| Publication figure presets (vector export, DPI, journal widths) | P0 |
| SNR per group / position *(proposed (T1.00); PRD Appendix A parity)* | P0 |
| Hierarchical clustering + dendrogram, k-Means | P0 (raised from P1 by Quan 2026-11-25, T1.00: v1.0 Quasar parity, PRD Appendix A) |
| 2D correlation spectroscopy (2D-COS: synchronous/asynchronous) | P1 |
| Band-assignment overlay (functional-group reference bands) | P1 |
| t-SNE, UMAP, MDS, 3D scatter, parallel coordinates | P1 |
| DBSCAN, self-organising map | P2 |

## 4. Preprocessing
*Likely source: SciPy (`savgol_filter`, `gaussian_filter1d` — Quasar wraps the same), scikit-learn scalers, `chemotools` (MSC, SNV, derivatives, detrend), `pybaselines` (ALS, arPLS, airPLS, polynomial, ModPoly/IModPoly, SNIP — preferred over Quasar's LGPL ALS copy). **Port from pengoo `preprocessing.py`** (TECH_STACK.md §11.2): `snv`, `msc` (with the ddof fix), axis-based detrend, Coca-Lopez spike removal (second despike method), `wavelet_denoise` (P1, needs PyWavelets). **Port from osp `preprocess/`** (TECH_STACK.md §11.1): `Cut`, `RubberbandBaseline`, `LinearBaseline`, `Normalize` (vector/area/attribute/min-max), `NormalizeReference`, `Absorbance`/`Transmittance`, `PCADenoising`, `ShiftAndScale`, `Despike`, `EMSC` (+ `npfunc`; MSC = order-0 case; interferents → extended EMSC), `ME_EMSC`, `AtmCorr` + `SpSubtract`, `Integrate`; interferogram → port osp `irfft.py`; peak fitting → wrap `lmfit` with osp `peakfit_compute` set-up.*
| Function | Tier |
|---|---|
| Range cut, Savitzky–Golay smoothing & derivatives, Gaussian/moving-average smoothing | P0 |
| SNV, MSC, EMSC (basic), detrend | P0 |
| Baseline: polynomial, ALS, airPLS, rubber-band | P0 |
| Normalisation: vector, min-max, area, by peak/attribute, by reference | P0 |
| Band integration: area, height, peak position *(proposed (T1.00); PRD Appendix A "Integrate" parity)* | P0 |
| Spike/cosmic-ray removal | P0 |
| Baseline: SNIP (pybaselines) *(proposed (T1.00b); used in pengoo's grid search)* | P0 |
| Median-filter smoothing *(proposed (T1.00b); pengoo `median_denoise`)* | P0 |
| Mean-centring, autoscaling, Pareto, range scaling | P0 |
| Transmittance↔absorbance, log(1/R), Kubelka–Munk | P0 |
| PCA denoising | P0 |
| Norris–Williams gap derivative, wavelet denoising, VSN | P1 |
| Extended EMSC (replicate/interferent models), Raman fluorescence removal (ModPoly, IModPoly) | P1 |
| Peak alignment (COW, icoshift), axis shift | P1 |
| Atmospheric H₂O/CO₂ correction | P1 |
| Peak fitting (Gaussian, Lorentzian, Voigt, … with constraints) | P1 |
| ME-EMSC (Mie scattering), FFT filtering | P2 |
| Interferogram → spectrum | P3 |

## 5. Sample selection & splitting
*Likely source: scikit-learn (random, stratified, group), `kennard-stone` (KS, cross-check); **port from pengoo `model_metrics.py`**: `_ks_order`, SPXY distance, `_duplex_order`, `split_cal_test` (stratified, sampling units kept whole).*
| Function | Tier |
|---|---|
| Random, Y-stratified, by group, user column | P0 |
| Kennard–Stone, SPXY, Duplex | P0 |
| Rank-rotate split with protected y-extremes *(proposed (T1.00b); pengoo `split_cal_test`)* | P1 |
| Puchwein, D-optimal | P2 |

## 6. Validation
*Likely source: scikit-learn splitters (o3 `evaluation/testing.py` wraps the same, not ported); nested CV orchestration is our own engine code (differentiator); permutation test → port the logic of o3 `widgets/evaluate/owpermutationplot.permutation()` (with a `Generator`, our folds); group k-fold with combined group columns, folds materialised once, group-leak check → port from pengoo `model_metrics.py`.*
| Function | Tier |
|---|---|
| k-fold, venetian blinds, contiguous blocks, LOO, repeated k-fold, Monte-Carlo CV | P0 |
| Group k-fold (replicate-safe) | P0 |
| Nested CV (multi-level, any scheme per level) | P0 |
| External test-set validation | P0 |
| Permutation / Y-randomisation test | P0 |
| Bootstrap, .632, repeated double CV (rdCV) | P1 |

## 7. Optimisation & search
*Likely source: scikit-learn `ParameterGrid`; LV rules (global min, 1-SE, paired t-test, Wold R) → port pengoo `select_n_components`; preprocessing-chain search → port pengoo `grid_search.py` (no pickle, no joblib); `optuna` for Bayesian (if approved).*
| Function | Tier |
|---|---|
| LV-number rules: min RMSECV, 1-SE rule, Wold's R, randomisation test | P0 |
| Preprocessing chain grid search (ported from pengoo) | P0 |
| Hyperparameter grid search | P0 |
| Random search, Bayesian optimisation | P1 |
| Multi-objective view (error vs complexity Pareto front) | P2 |

## 8. Variable selection
*Likely source: **port from pengoo `variable_selection.py`** + `model_metrics.py`: VIP, selectivity ratio, jackknife, SPA, CARS, SWSR, sPLS, ACO, siPLS, MW-PLS and the shared subset scorer (SPA and CARS to be aligned with their papers, TECH_STACK.md §11.2); iPLS forward/backward is not in pengoo (own code); CAKE from Quan's own code.*
| Function | Tier |
|---|---|
| VIP, selectivity ratio, regression coefficients + Jackknife (Martens' uncertainty test) | P0 |
| iPLS (forward/backward), CARS, SPA | P0 |
| Selection inside CV + stability map | P0 |
| GA-PLS, UVE / MC-UVE, siPLS, sPLS, ACO, SWSR | P1 |
| MW-PLS (moving-window PLS) *(proposed (T1.00b); pengoo `moving_window_pls`)* | P1 |
| CAKE (owner's method) | P1 |
| VCPA, IRIV, Boruta / RF importance | P2 |

## 9. Regression models
*Likely source: scikit-learn (PLSRegression, PCR via pipeline, linear models, SVR, RF, GB, kNN, GP, MLP); SIMPLS own code.*
| Function | Tier |
|---|---|
| PLS (NIPALS, SIMPLS), PLS2 multi-Y | P0 |
| PCR, MLR (on selected variables), Ridge/Lasso/Elastic Net | P0 |
| SVR, Random Forest, Gradient Boosting, kNN | P1 |
| Locally weighted PLS (LW-PLS), kernel PLS, Gaussian process | P1 |
| ANN/MLP, stacking/ensembles | P2 |
| 1D-CNN, other deep models | P3 |

## 10. Classification & authentication
*Likely source: scikit-learn (LDA/QDA, kNN, SVM, RF, logistic); PLS-DA, SIMCA, DD-SIMCA likely own code (check existing packages first).*
| Function | Tier |
|---|---|
| PLS-DA (binary, multi-class), PCA-LDA, LDA/QDA, kNN | P0 |
| SIMCA | P0 |
| DD-SIMCA, one-class classifiers (authentication / adulteration screening) | P1 |
| OPLS-DA, SVM, Random Forest, logistic regression | P1 |
| CNN classifiers | P3 |

## 11. Latent-variable & resolution methods
*Likely source: scikit-learn (PCA, ICA, NMF); `pyMCR` (MCR-ALS, if approved); `tensorly` (PARAFAC, P3).*
| Function | Tier |
|---|---|
| PCA | P0 |
| OPLS | P1 |
| MCR-ALS (with constraints) | P1 |
| ICA, NMF | P2 |
| PARAFAC, Tucker (multiway) | P3 |

## 12. Calibration transfer & domain adaptation
*Blocks take multiple inputs (e.g. master + slave instrument, source + target domain) — multi-port blocks (PRD F-07). Port types are designed in TASKS.md T0.14 even though these blocks ship in P1 (PROJECT.md §3, R-11). Likely source: mostly own code (DS/PDS/SST/EPO are short); check existing packages first.*
| Function | Tier |
|---|---|
| Transfer-sample selection (KS on master) | P1 |
| Slope/bias correction | P1 |
| Direct Standardisation (DS), Piecewise DS (PDS) | P1 |
| Spectral Space Transformation (SST) | P1 |
| Orthogonal methods: EPO, GLSW, OSC | P1 |
| Model updating / augmentation with target samples | P2 |
| Domain-invariant PLS (di-PLS), TCA, CCA-based transfer | P2 |
| Deep domain adaptation | P3 |

## 13. Statistical testing
*Likely source: SciPy `stats`; `statsmodels` (Tukey HSD, multiple-testing correction, if approved); model-comparison tests (van der Voet, Pitman–Morgan, F, Brown–Forsythe, Welch, bootstrap ΔRMSEP, Holm) → port pengoo `validate_models`.*
| Function | Tier |
|---|---|
| Descriptive statistics, confidence intervals | P0 |
| Normality (Shapiro–Wilk), variance homogeneity (Levene) | P0 |
| t-tests, one/two-way ANOVA + Tukey HSD | P0 |
| Mann–Whitney, Wilcoxon signed-rank, Kruskal–Wallis | P0 |
| Pearson / Spearman correlation | P0 |
| Model comparison: paired tests on CV errors, randomisation t-test (van der Voet) | P0 |
| Bias and slope significance tests on a test set (ISO 12099) *(proposed (T1.00b); pengoo `validate_models`)* | P0 |
| Multiple-testing correction (Bonferroni, Holm, BH-FDR) | P1 |
| Bland–Altman, equivalence tests, bootstrap CIs | P1 |
| MANOVA, ASCA (designed experiments) | P2 |

## 14. Interpretation & diagnostics
*Likely source: scikit-learn metrics (confusion matrix, ROC; o3 `scoring.py` wraps the same); residuals / DModX → port o3 `regression/pls.py` `dmodx`, `_residual_ssx`; `shap` (P1, if approved).*
| Function | Tier |
|---|---|
| Coefficient / VIP / loading plots over the spectrum | P0 |
| Predicted vs reference, residuals, leverage, T²/Q influence plot | P0 |
| Confusion matrix, ROC/AUC | P0 |
| Permutation importance, SHAP | P1 |
| Elliptical joint confidence region (EJCR) for slope/bias | P1 |

## 15. Hyperspectral imaging
*Likely source: port osp `utils/__init__.py` hypercube helpers, `utils/binning.py`, `owreshape`, `owstackalign` + `utils/skimage` (BSD-3); readers `spectral` (ENVI), `agilent-format`; viewer spec from osp `owhyper`.*
| Function | Tier |
|---|---|
| Cube viewer: band image, RGB/false colour, pixel spectrum | P2 |
| ROI masking, background removal, mean spectrum per ROI | P2 |
| Pixel-wise prediction maps, PCA score images, k-means segmentation | P2 |
| Spectral unmixing (VCA, N-FINDR + MCR) | P3 |
| Spatial-spectral models, mosaics | P3 |

## 16. Deployment, reporting & citation
| Function | Tier |
|---|---|
| Model package, predict mode with applicability domain | P0 |
| HTML report (PDF via the desktop app), auto methods paragraph | P0 |
| Auto-bibliography of methods used (BibTeX/RIS) | P0 |
| Python script export, run provenance | P0 |
| Batch prediction from command line | P1 |
| Model comparison dashboard / registry | P1 |
| ONNX export, local prediction API | P2 |

## 17. Platform
| Function | Tier |
|---|---|
| Multi-port typed blocks (DAG pipelines) | P0 |
| Parallel execution engine | P0 |
| Crash resilience (engine restart, native fallback) | P0 |
| EN / JA / VI interface, student tooltips | P0 |
| Installers (Windows, macOS, Linux) on GitHub Releases | P0 |
| Templates, save/load pipelines | P0 |
| Python script block / plugin SDK | P1 |
| GPU acceleration (optional) | P2 |
| Remote / HPC executor | P3 |
| VibeChem Lite (hosted web) | P3 |

---

## P0 size check
P0 ≈ 90 functions. Realistic only because the numerical core reuses mature libraries (NumPy, SciPy, scikit-learn, chemotools, pybaselines) and code ported from pengoo and Orange-Spectroscopy, and every block follows one template (CLAUDE.md §5). Any P0 item without an existing reference implementation to test against is flagged to Quan (algorithm review and test infrastructure) before work starts. Libraries marked "if approved" are not yet in TECH_STACK.md §1 and need Quan's approval before use.

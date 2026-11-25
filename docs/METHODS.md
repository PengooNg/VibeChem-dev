<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# VibeChem — Methods

> v0.1 · 2026-11-25 · **DRAFT (T1.04): Quan corrects and approves.** Part 1 covers the methods of T1.07–T1.14. Later phases add entries in the same format. Block headers cite entries by anchor (`docs/METHODS.md#snv`); the numbered `# Step N:` comments in a block follow the **Steps** of its entry. Citation keys refer to `docs/references.bib`.

## Contents
- [0. Choices for Quan to confirm](#0-choices-for-quan-to-confirm)
- [1. Conventions](#1-conventions)
- [2. Preprocessing](#2-preprocessing): [cut](#cut) · [SNV](#snv) · [MSC](#msc) · [detrend](#detrend) · [Savitzky–Golay](#savgol)
- [3. Scaling](#3-scaling): [mean-centre](#mean-centre) · [autoscale](#autoscale) · [Pareto](#pareto) · [Y scaling](#y-scaling)
- [4. Splits](#4-splits): [random](#random-split) · [Kennard–Stone](#kennard-stone) · [SPXY](#spxy) · [Duplex](#duplex) · [group-aware selection](#group-aware-split)
- [5. Cross-validation folds](#5-cross-validation-folds): [k-fold](#k-fold) · [venetian blinds](#venetian-blinds) · [contiguous blocks](#contiguous-blocks) · [LOO](#loo) · [repeated k-fold](#repeated-k-fold) · [group k-fold](#group-k-fold)
- [6. PLS regression](#6-pls-regression): [PLS (NIPALS)](#pls) · [LV sweep](#pls-lv-sweep) · [SIMPLS](#simpls) · [VIP](#vip)
- [7. PLS-DA](#plsda)
- [8. Metrics](#8-metrics): [regression](#regression-metrics) · [RMSECV aggregation](#rmsecv) · [classification](#classification-metrics)

---

## 0. Choices for Quan to confirm
Every item marked **(T1.04)** in TECH_STACK.md §11.2, plus the new choices found while drafting. "Suggested" is what the entries below use until Quan decides. pengoo defects D1 and D2 (TECH_STACK.md §11.2) are noted where an entry touches them.

**(T1.04) items from the pengoo inventory**
| # | Question | Suggested answer | Why |
|---|---|---|---|
| Q1 | SNV: ddof of the per-spectrum SD (pengoo 0, skeleton engine 1) | **ddof = 1**, parameter with choices 0/1 | Same as the block template and the skeleton engine. The factor √((p−1)/p) is the same for every spectrum, so PLS predictions do not change; only the printed SNV values differ. Barnes et al. 1989 divisor *to verify* in the paper. |
| Q2 | Savitzky–Golay edge mode (pengoo `nearest`, SciPy default `interp`) | **`interp`** default; `nearest`, `mirror`, `constant`, `wrap` as options | `interp` fits the same polynomial to the last window, which is the Savitzky–Golay idea carried to the edge. `nearest` repeats the edge value and bends derivatives near the edges. |
| Q3 | Savitzky–Golay derivative `delta` | **signed axis step** `delta = λ₂ − λ₁` (derivative per axis unit); non-uniform axis → error | pengoo used `delta = 1` (per point), so its derivatives depend on the point spacing. With the signed step a descending wavenumber axis still gives d/dν. |
| Q4 | PLS X scaling default (scikit-learn `scale=True`; every pengoo PLS result used it) | **mean-centring only** (`scale=False`); autoscaling is a visible scaling block | Spectra share one unit, and autoscaling raises noise-only variables to the same weight as bands. `scale=False` reproduces the published gasoline results of Mevik & Wehrens 2007 (testdata PROVENANCE sanity check). Old pengoo results are not comparable 1:1. |
| Q5 | Kennard–Stone / SPXY distance space (pengoo: PCA scores of unit means, 99 % variance) | **raw X, Euclidean** default; option "PCA scores" (number of components or variance fraction); group-aware mode averages each sampling unit first | Raw X is the method as published (Kennard & Stone 1969, Galvão et al. 2005) and what the `kennard-stone` cross-check uses. PCA scores stay available for wide, noisy spectra. |
| Q6 | RMSECV aggregation default (pengoo `fold_mean`) | **`pooled`** = √(PRESS/n); `fold_mean` as option; per-fold RMSE always stored | Pooled is the chemometrics definition (Martens & Næs 1989), is correct for unequal folds and is what the R `pls` package reports (our T1.15 reference). Per-fold values are kept, so the 1-SE and t-test LV rules still work. |
| Q7 | Bias sign | **bias = mean(ŷ − y)**, positive = over-prediction | ISO 12099:2010 Eq. (1)–(3): "a positive bias when the predictions are too high" (checked in the official preview). Same sign as pengoo, so no old results flip. |
| Q8 | "int ≥ n → LOO" rule in `make_cv_splitter` | **no silent switch**: 2 ≤ k ≤ n_units (samples, or groups when grouped); k > n_units → `BLOCK_PARAM_INVALID` (reason `constraint`); k = n_units allowed (equals LOO / leave-one-group-out); LOO is its own scheme | A silent change of scheme hides a typo (k = 100 on 60 samples). The result is the same as asking for LOO, so nothing is lost. |
| Q9 | PLS2 VIP | **offer it**: SS of component a summed over all Y columns (Eq. in [VIP](#vip)); documented as depending on Y scaling; per-response VIP not in T1.12b | pengoo's formula already sums over Y columns, so it is PLS2-ready. Multi-response VIP is the form used in the original VIP chapter (Wold et al. 1993, *to verify*). |
| Q10 | Model-comparison defaults `n_perm = 9999`, `n_boot = 2000` (marked T1.04 / P6) | **defer to the P6 validation step** (not a Phase 1 method) | No Phase 1 block uses them. |

**New choices found while drafting**
| # | Question | Suggested answer | Why |
|---|---|---|---|
| N1 | Missing values (NaN is allowed in `SpectralDataset.X`) in Phase 1 blocks | every Phase 1 block **rejects NaN in X** (and in y where y is used) with a node error; needs a new code, proposed `BLOCK_MISSING_VALUES` (added to DATA_MODEL.md §7 by T1.07) | Silent NaN propagation would give NaN metrics late in the graph. Imputation is a P6 block. |
| N2 | Autoscale/Pareto SD ddof | **ddof = 1** | Same as SNV, SEP, RPD and scikit-learn's own PLS `scale=True`. A common factor, so PLS predictions do not change. `StandardScaler` uses ddof 0, so T1.09 corrects its `scale_` or uses two lines of NumPy. |
| N3 | Autoscale/Pareto on a zero-variance column | centre it, leave it unscaled (scale 1) and **warn** in the node log | Flat columns occur after cuts or detector saturation; an error would block common pipelines. Same as `StandardScaler`, but not silent. |
| N4 | Savitzky–Golay on a non-uniform axis | node error, proposed code `BLOCK_AXIS_NOT_UNIFORM` (relative spacing tolerance 1e-6, added to DATA_MODEL.md §7 by T1.08); the fix is an interpolation block | SG assumes equal spacing. |
| N5 | Kennard–Stone start | **the two most distant samples** (as in pengoo and Daszykowski et al. 2002); ties → lowest row index | The variant that starts at the sample nearest the mean also exists. Which one Kennard & Stone 1969 use, and which one the `kennard-stone` package uses, is *to verify*; the T1.10 cross-check must use the same start. |
| N6 | RMSEC divisor | **n** (not n − A − 1) | Same as RMSECV/RMSEP and pengoo; degrees-of-freedom versions are not comparable across LV counts in the UI. |
| N7 | Slope | **b in y = a + b·ŷ** (reference regressed on prediction) | ISO 12099:2010 §5.4.1 (checked in the preview). The predicted-vs-measured plot shows ŷ against y, so the plot's visual slope is the reverse regression; the UI labels it. |
| N8 | RPD and RPIQ denominator (pengoo: RPD = SD/RMSE) | **SEP** for both, i.e. RPD = SD(y)/SEP, RPIQ = (Q3 − Q1)/SEP | Fearn 2002 and Bellon-Maurel et al. 2010 define the ratios with SEP (*to verify in both papers*). If Quan prefers RMSE (pengoo, many soil papers), change both together. |
| N9 | Repeated k-fold RMSECV | pooled RMSECV **per repeat**, then mean and SD over repeats | One prediction per sample per repeat; pooling across repeats would count samples several times. |
| N10 | Split / CV when the dataset has groups but the scheme ignores them | warning `VALIDATION_GROUPS_IGNORED` (already in DATA_MODEL.md §7) | Replicates in both training and validation inflate results (Esbensen & Geladi 2010). |
| N11 | MSC with slope bᵢ ≤ 0 | node error, proposed code `BLOCK_MSC_SLOPE_INVALID` | Dividing by a negative or zero slope flips or explodes the spectrum; it means the reference does not fit that spectrum. |
| N12 | Defaults with no source: SG window 11 / polyorder 2; random split test fraction 0.25, 5 y-bins; k-fold k = 10; repeats 5; PLS `n_components` 10 (capped at min(n − 1, p)) | as listed (marked *to confirm* in the entries) | Common starting values; no paper prescribes them. |
| N13 | SPXY with all y equal | node error, proposed code `BLOCK_CONSTANT_RESPONSE` | max d_y = 0 makes the y term undefined; a silent fall-back to Kennard–Stone would hide it. |
| N14 | New error codes | `BLOCK_MISSING_VALUES`, `BLOCK_AXIS_NOT_UNIFORM`, `BLOCK_MSC_SLOPE_INVALID`, `BLOCK_CONSTANT_RESPONSE` are **proposals only**; each implementing step adds its code to DATA_MODEL.md §7 in its own PR | CLAUDE.md §4: codes are added to DATA_MODEL.md first, not invented in code. This PR does not change DATA_MODEL.md. |
| N15 | Metric names in `Results.metrics` | `rmsec/rmsecv/rmsep`, `r2c/r2cv/r2p`; `bias`, `sep`, `slope`, `intercept`, `rpd`, `rpiq`, `press` refer to the Results' own set; `n_lv` | Matches the DATA_MODEL.md §2.8 example (`rmsecv`, `r2cv`, `bias`, `rpd`, `rpiq`, `n_lv`). |
| N16 | PLS component sign | fix after fitting: largest-\|w\| element of each weight vector positive (scores and loadings flipped with it) | Signs from SVD/NIPALS can differ between BLAS builds; predictions do not change, plots and saved states do (ARCHITECTURE.md: same results across OS). |

---

## 1. Conventions
- **Data.** X is n × p (rows = spectra, columns = axis points λ₁ … λ_p); y is n × k (k = 1: PLS1, k > 1: PLS2). x̄ⱼ is a column mean, x̄ᵢ· a row (spectrum) mean. "Training rows" are the rows a fitted block's `fit` sees; `apply` uses only statistics learned in `fit` (CLAUDE.md §4; this is why pengoo defect D2 cannot happen).
- **Residual.** e = ŷ − y (Q7). All metrics are in original Y units: any Y scaling is inverted before metrics.
- **Standard deviation.** ddof = 1 unless an entry says otherwise.
- **Missing values.** Phase 1 blocks reject NaN (N1).
- **Randomness.** Every random choice takes a `numpy.random.Generator`; scikit-learn functions that need an integer seed get one drawn from that Generator (`int(rng.integers(2**32))`).
- **Ties** (distances, class scores) go to the lowest row or class index, so results are deterministic.
- **Tolerance classes** used in the entries (QA.md §3: tolerances always explicit):
  | Class | Use | `assert_close` |
  |---|---|---|
  | `T-exact` | closed-form hand calculation, algebraic identity | `rtol=1e-10, atol=1e-12` |
  | `T-lib` | our block vs the library it wraps, same algorithm | `rtol=1e-10, atol=1e-12` |
  | `T-iter` | iterative algorithm vs another implementation (NIPALS PLS2, SIMPLS vs NIPALS) | `rtol=1e-6, atol=1e-9` |
  | `T-pub` | published values | the tolerance recorded in the `testdata/expected/` file (gasoline: `rtol=1e-3`, proposed in T0.07); otherwise half a unit of the last printed digit (`atol`), `rtol=0` |
- **Entry fields.** Definition · Formula · Steps (what `# Step N:` comments follow) · Parameters (defaults) · Edge cases · Reference values (independent, never pengoo or Quasar: TECH_STACK.md §11.1 rule 3, §11.2 rule 5) · Tolerance · Implementation · Library differences.

---

## 2. Preprocessing

<a id="cut"></a>
### Range cut (`preprocess.cut`) · T1.07
- **Definition.** Keep the axis points that lie inside one or more ranges.
- **Formula.** keep j ⇔ ∃ r: lo_r ≤ λⱼ ≤ hi_r (bounds inclusive).
- **Steps.** 1 for each range, mark λⱼ with lo ≤ λⱼ ≤ hi (lo/hi may be given in either order) · 2 union of the marks · 3 reject an empty selection · 4 keep the marked columns in their original axis order.
- **Parameters.** `ranges`: list of (lo, hi) in axis units, at least one.
- **Edge cases.** Descending axis (wavenumbers): order kept. Overlapping ranges: union, no duplicate columns. No point selected → `BLOCK_PARAM_INVALID` (reason `constraint`). A range outside the axis selects nothing from that range (allowed if another range selects points).
- **Reference values.** Hand-made axis with points exactly on the bounds.
- **Tolerance.** Exact (index sets equal).
- **Implementation.** Own NumPy; behaviour as Quasar `Cut` (inclusive bounds, several ranges, unsorted axis), ported per TASKS.md T1.07.

<a id="snv"></a>
### Standard Normal Variate (`preprocess.snv`) · T1.07
- **Definition.** Centre and scale each spectrum by its own mean and SD. Row-wise, not fitted.
- **Formula.** zᵢⱼ = (xᵢⱼ − x̄ᵢ·) / sᵢ, with x̄ᵢ· = (1/p) Σⱼ xᵢⱼ and sᵢ = √( Σⱼ (xᵢⱼ − x̄ᵢ·)² / (p − ddof) ).
- **Steps.** 1 row means · 2 row SDs (ddof) · 3 reject rows with sᵢ = 0 · 4 (X − mean)/SD.
- **Parameters.** `ddof` ∈ {0, 1}, default 1 (Q1).
- **Edge cases.** Constant spectrum (sᵢ = 0) → `BLOCK_CONSTANT_SPECTRA` with the row list; no `+1e-10` guard (pengoo's silently returns 0). p = 1 with ddof = 1 → division by zero: rejected as `BLOCK_CONSTANT_SPECTRA` too (p − ddof = 0).
- **Reference values.** Hand calculation on a 2 × 4 matrix; properties: each output row has mean 0 and SD 1 (same ddof); SNV(aX + b) = SNV(X) for a > 0.
- **Tolerance.** `T-exact`.
- **Implementation.** Own NumPy (4 lines; the `block-template` example).
- **Library differences.** chemotools `StandardNormalVariate` and pengoo use ddof 0.
- **Reference.** `barnes1989snv`; review `rinnan2009review`.

<a id="msc"></a>
### Multiplicative Scatter Correction (`preprocess.msc`) · T1.07
- **Definition.** Regress each spectrum on a reference spectrum m and remove the offset and the multiplicative effect. Fitted: m is learned in `fit`.
- **Formula.** xᵢ = aᵢ + bᵢ·m + eᵢ, (aᵢ, bᵢ) by ordinary least squares over the p points; corrected x̃ᵢ = (xᵢ − aᵢ)/bᵢ. Default m = mean spectrum of the training rows.
- **Steps.** `fit`: 1 m = column mean of training X (or the user reference). `apply`: 2 for each spectrum, least-squares fit of aᵢ + bᵢ·m · 3 reject bᵢ ≤ 0 or bᵢ = 0 · 4 x̃ᵢ = (xᵢ − aᵢ)/bᵢ.
- **Parameters.** `reference`: `mean` (default) or a second input port with one spectrum on the same axis (`axis_match`).
- **Edge cases.** **D1:** aᵢ, bᵢ come from one least-squares solve (`np.linalg.lstsq` on [1, m]), never from `cov(x, m)` (ddof 1) / `var(m)` (ddof 0). Constant reference (var(m) = 0) → `BLOCK_CONSTANT_SPECTRA`. bᵢ ≤ 0 (spectrum anti-correlated with the reference) → node error with its own code, proposed `BLOCK_MSC_SLOPE_INVALID` (N11; T1.07 adds it to DATA_MODEL.md §7). Applied to new data: m from training only (D2).
- **Reference values.** Exact case xᵢ = a + b·m (a, b known, 50 points) → x̃ᵢ = m (`T-exact`; this is the D1 regression test). Hand calculation on 3 × 5. Cross-check: chemotools `MultiplicativeScatterCorrection` (`T-lib`, extra check only).
- **Tolerance.** `T-exact`.
- **Implementation.** Port of pengoo `msc` with the D1 fix, as a fitted block.
- **Reference.** `geladi1985msc`; review `rinnan2009review`.

<a id="detrend"></a>
### Detrend (`preprocess.detrend`) · T1.07
- **Definition.** Fit a polynomial in the axis value to each spectrum and subtract it. Row-wise, not fitted.
- **Formula.** For spectrum i: cᵢ = argmin Σⱼ (xᵢⱼ − Σ_{d=0..D} c_{id} uⱼ^d)², x̃ᵢⱼ = xᵢⱼ − Σ_d c_{id} uⱼ^d, where uⱼ is λⱼ mapped linearly to [−1, 1] (this only improves conditioning; the fitted curve is the same as for λⱼ).
- **Steps.** 1 u = axis mapped to [−1, 1] · 2 Vandermonde matrix of degree D · 3 least-squares fit for all spectra at once · 4 subtract the fitted curves.
- **Parameters.** `degree` D ∈ {1, 2, 3, …}, default 2 (Barnes et al. 1989 use a second-degree polynomial after SNV). Constraint D < p.
- **Edge cases.** Uses the real axis, never the index (pengoo falls back to the index). D ≥ p → `BLOCK_PARAM_INVALID`.
- **Reference values.** A spectrum that is exactly a degree-D polynomial in λ → output 0 (`T-exact`); a polynomial plus a known orthogonal component → that component back; result independent of the axis direction.
- **Tolerance.** `T-exact` (on well-conditioned u).
- **Implementation.** Own NumPy (`np.linalg.lstsq`), or chemotools/pybaselines `poly` if T1.07's reuse check prefers it; either must pass the same tests.
- **Reference.** `barnes1989snv`.

<a id="savgol"></a>
### Savitzky–Golay smoothing and derivatives (`preprocess.savgol`) · T1.08
- **Definition.** Fit a polynomial of order P by least squares in a moving window of w points; the output is the fitted value (smoothing) or its d-th derivative at the window centre.
- **Formula.** Output = convolution of each spectrum with the Savitzky–Golay coefficients for (w, P, d), times d!/Δλ^d for derivatives, where Δλ is the signed axis step (Q3). Edges by `mode` (Q2).
- **Steps.** 1 check the axis is uniform (N4) and take Δλ = λ₂ − λ₁ · 2 validate w, P, d · 3 one `savgol_filter` call on the whole matrix (`axis=1`) with `delta = Δλ`.
- **Parameters.** `window` w: odd, 3 ≤ w ≤ p, default 11 (*to confirm*, N12); `polyorder` P: 0 ≤ P < w, default 2; `deriv` d: 0 ≤ d ≤ P, default 0; `mode` ∈ {`interp`, `nearest`, `mirror`, `constant`, `wrap`}, default `interp`.
- **Edge cases.** w > p → `BLOCK_PARAM_INVALID` (`interp` needs w ≤ p). Even w → `BLOCK_PARAM_INVALID` (reason `odd`). Non-uniform axis → proposed `BLOCK_AXIS_NOT_UNIFORM` (N4). Derivative units: signal unit per axis unit to the power d.
- **Reference values.** Coefficients published by Savitzky & Golay 1964 with the corrections of Steinier et al. 1972: 5-point quadratic smoothing (−3, 12, 17, 12, −3)/35 and 5-point first derivative (−2, −1, 0, 1, 2)/10 (interior points, `T-exact`). A polynomial of order ≤ P is reproduced exactly, and its d-th derivative equals the analytic one in physical units (`T-exact`, any mode on interior points, `interp` everywhere).
- **Tolerance.** `T-exact` against the published coefficients; `T-lib` against `savgol_filter`.
- **Implementation.** Wrap `scipy.signal.savgol_filter` (SciPy 1.18.1: `mode` default `interp` — "a degree polyorder polynomial is fit to the last window_length values of the edges"; `delta` "the spacing of the samples", used only if deriv > 0).
- **Library differences.** pengoo: `mode='nearest'`, `delta=1`, one call per spectrum. Quasar: same SciPy call (its NaN and unsorted-axis handling is the behaviour reference, T1.08).
- **Reference.** `savitzky1964`, `steinier1972`.

---

## 3. Scaling
All column scalings are **fitted**: x̄ⱼ and sⱼ come from the training rows and are reused unchanged by `apply` (D2: pengoo recomputed them on whatever it was given). Done-when test of T1.09: applying to new rows uses the training statistics only.

<a id="mean-centre"></a>
### Mean-centring (`preprocess.mean_centre`) · T1.09
- **Formula.** x̃ᵢⱼ = xᵢⱼ − x̄ⱼ (training means).
- **Steps.** `fit`: 1 column means. `apply`: 2 subtract.
- **Reference values.** Hand calculation; property: training output has column means 0; test rows are shifted by the training means, not their own.
- **Tolerance.** `T-exact`.
- **Implementation.** Own NumPy or `StandardScaler(with_std=False)` (`T-lib`).
- **Reference.** `vandenberg2006scaling`.

<a id="autoscale"></a>
### Autoscaling (`preprocess.autoscale`) · T1.09
- **Formula.** x̃ᵢⱼ = (xᵢⱼ − x̄ⱼ) / sⱼ, sⱼ = training column SD with ddof 1 (N2).
- **Steps.** `fit`: 1 column means · 2 column SDs (ddof 1) · 3 sⱼ = 0 → scale 1 + warning (N3). `apply`: 4 (X − mean)/SD.
- **Reference values.** Hand calculation; training output has column mean 0 and SD 1.
- **Library differences.** `StandardScaler` uses ddof 0 (its `scale_` differs by √(n/(n−1))); scikit-learn `PLSRegression(scale=True)` uses ddof 1.
- **Tolerance.** `T-exact`.
- **Reference.** `vandenberg2006scaling`.

<a id="pareto"></a>
### Pareto scaling (`preprocess.pareto`) · T1.09
- **Formula.** x̃ᵢⱼ = (xᵢⱼ − x̄ⱼ) / √sⱼ (training statistics, ddof 1).
- **Edge cases.** As autoscaling (N3).
- **Reference values.** Hand calculation; property: Pareto(X) column SDs = √sⱼ.
- **Tolerance.** `T-exact`.
- **Implementation.** Own NumPy (two lines), or chemotools if T1.09 shows it is a better fit.
- **Reference.** `vandenberg2006scaling`.

<a id="y-scaling"></a>
### Y centring and autoscaling · T1.09
- **Definition.** The same fitted scalings applied to y; the block also offers the inverse transform, which the model applies to predictions before any metric, so metrics are in original Y units (replaces pengoo's hand-passed `y_sdev`).
- **Reference values.** Round trip y → scaled → inverse = y (`T-exact`); metrics of a model trained on scaled y equal those of the same model with the scaling folded in.
- **Note.** For PLS1, Y scaling does not change predictions (PLS is scale-equivariant in y). For PLS2 it changes the model and VIP (Q9).

---

## 4. Splits
Hold-out split blocks output `folds: Folds` (one train/test hold-out) plus `train` and `test` spectra (DATA_MODEL.md §4.6). They select rows only; nothing is fitted on test rows. The test fraction (or count) is a parameter; selection methods below return an **order**, and the first n_train rows of the order form the training set.

<a id="random-split"></a>
### Random and stratified split (`split.random`) · T1.10
- **Definition.** Draw the test rows at random; optionally stratified by class or by y quantile bins, so both sets cover the same range.
- **Steps.** 1 strata = classes, or y binned into `n_bins` quantile bins (default 5, *to confirm*), or none · 2 within each stratum draw the test share with the Generator · 3 union.
- **Parameters.** `test_fraction` (0 < f < 1, default 0.25 *to confirm*) or `n_test`; `stratify` ∈ {none, classes, y}; `rng`.
- **Edge cases.** Fewer than 2 rows in a stratum → that stratum goes to training and a warning is logged. Groups present → group-aware selection (see below) or `VALIDATION_GROUPS_IGNORED` warning (N10).
- **Reference values.** Properties: train ∪ test = all rows, disjoint, sizes as requested (± 1 per stratum), stratum shares kept; same seed → same split.
- **Tolerance.** Exact.
- **Implementation.** Wrap scikit-learn `train_test_split` (seed drawn from the Generator).

<a id="kennard-stone"></a>
### Kennard–Stone (`split.kennard_stone`) · T1.10
- **Definition.** Select training samples that cover the X space uniformly: start with the two most distant samples, then repeatedly add the sample whose distance to its nearest selected sample is largest.
- **Formula.** d(i, j) = ‖zᵢ − zⱼ‖₂, z = raw X rows (default) or PCA scores (Q5). Next k = argmax_{k ∉ S} min_{s ∈ S} d(k, s).
- **Steps.** 1 distance space z (raw X, or PCA scores fitted on all rows of the split input — the split is a design step, not a model fit) · 2 distance matrix · 3 start pair = argmax d (N5) · 4 max–min loop until all rows are ordered · 5 first n_train rows of the order → training.
- **Parameters.** `test_fraction`/`n_test`; `space` ∈ {`x`, `pca`}, default `x`; `n_components` or `variance` (for `pca`, default 0.99 as in pengoo).
- **Edge cases.** Ties → lowest index. Duplicate spectra (d = 0) are fine. n ≤ 2 → order is the row order. Memory: the n × n matrix (n = 5 000 → 200 MB in float64) — above a size threshold compute the min-distance vector incrementally (O(n) memory).
- **Reference values.** Hand-worked example of 6 points in 2-D with a unique order; cross-check with the `kennard-stone` package (same start rule, N5) on the gasoline data. Kennard & Stone 1969 printed example *to verify* as an extra reference.
- **Tolerance.** Exact (orders equal).
- **Implementation.** Port pengoo `_ks_order` (vectorised update of the min-distance vector instead of the Python `max(rest, key=…)` loop).
- **Reference.** `kennard1969`, `daszykowski2002`.

<a id="spxy"></a>
### SPXY (`split.spxy`) · T1.10
- **Definition.** Kennard–Stone on a joint distance in X and y.
- **Formula.** d_xy(i, j) = d_x(i, j) / max d_x + d_y(i, j) / max d_y, with d_x as in Kennard–Stone and d_y(i, j) = ‖yᵢ − yⱼ‖₂ (|yᵢ − yⱼ| for one response).
- **Steps.** 1 d_x · 2 d_y · 3 normalise each by its maximum · 4 sum · 5 Kennard–Stone order on d_xy.
- **Parameters.** As Kennard–Stone; requires y (`requires: ["y"]`).
- **Edge cases.** All y equal (max d_y = 0) → node error, proposed code `BLOCK_CONSTANT_RESPONSE` (N13); no silent fall-back to Kennard–Stone. NaN in y → N1.
- **Reference values.** Hand-worked example (5 samples, 1 response) where SPXY and KS give different orders.
- **Tolerance.** Exact (orders equal); distances `T-exact`.
- **Implementation.** Port pengoo SPXY distance (`Dx/max + Dy/max`).
- **Reference.** `galvao2005spxy`.

<a id="duplex"></a>
### Duplex (`split.duplex`) · T1.10 *(proposed (T1.00b) addition)*
- **Definition.** Build training and test sets that both cover the X space: the two most distant samples go to training, the next two most distant (of the rest) to test, then the sets alternately take the remaining sample farthest from their own members.
- **Steps.** 1 distance matrix (as KS) · 2 farthest pair → training · 3 farthest remaining pair → test · 4 alternate: each set takes the remaining sample with the largest min-distance to that set · 5 when the test set reaches n_test, the rest go to training.
- **Edge cases.** As Kennard–Stone. Unequal set sizes: alternation stops for the full set.
- **Reference values.** Hand-worked example (8 points in 2-D).
- **Tolerance.** Exact.
- **Implementation.** Port pengoo `_duplex_order`.
- **Reference.** `snee1977duplex`, `daszykowski2002`.

<a id="group-aware-split"></a>
### Group-aware selection (option of all split blocks) · T1.10
- **Definition.** Keep sampling units (replicate spectra of one sample, `group_ids`) whole: a unit is entirely in training or entirely in test.
- **Steps.** 1 unit means of X (and y) · 2 run the selected method on the unit means · 3 expand selected units back to their rows.
- **Edge cases.** Stratified random split with groups: strata are assigned per unit (majority class or unit-mean y).
- **Reference values.** Property: no `group_id` appears in both sets; with one row per group, results equal the plain method.
- **Implementation.** Port of the unit-preserving selection in pengoo `split_cal_test` (`rank_rotate` and `protect_extremes` are a proposed P1 row, not here).
- **Reference.** `esbensen2010validation`.

---

## 5. Cross-validation folds
Fold blocks output `folds: Folds` (DATA_MODEL.md §4): for each fold, the validation row indices; training = the other rows. Folds are made **once** and reused by every model and every LV count that is compared on them (pengoo `PredefinedFolds`). Common rules:
- **Number of folds** k: 2 ≤ k ≤ n_units, where n_units = number of rows, or number of groups when grouped. k > n_units → `BLOCK_PARAM_INVALID` (reason `constraint`); no silent switch to LOO (Q8).
- **Groups.** When the input has `group_ids`, a scheme that ignores them logs `VALIDATION_GROUPS_IGNORED` (N10). Grouped schemes never split a group (group-leak assertion ported from pengoo).
- **Order-based schemes** (venetian blinds, contiguous blocks) use the row order of the input, which is the import order unless an upstream block sorted it.
- **Reference values** for all schemes: property tests (Done when of T1.11) — validation sets partition the rows (each row validated exactly once per repeat), groups never split, sizes differ by at most one unit, same Generator seed → same folds; plus a hand-listed small case per scheme.

<a id="k-fold"></a>
### k-fold (`validate.kfold`) · T1.11
- **Definition.** Rows (optionally shuffled with the Generator) are cut into k folds of near-equal size.
- **Parameters.** `k` (default 10 *to confirm*), `shuffle` (default true), `rng`.
- **Implementation.** Wrap scikit-learn `KFold`.
- **Reference.** `stone1974cv`.

<a id="venetian-blinds"></a>
### Venetian blinds (`validate.venetian_blinds`) · T1.11
- **Definition.** Row i (0-based, input order) goes to fold i mod k.
- **Implementation.** Own code (one line of NumPy).
- **Reference.** `eigenvector_cv` (*to verify*).

<a id="contiguous-blocks"></a>
### Contiguous blocks (`validate.contiguous_blocks`) · T1.11
- **Definition.** Rows in input order are cut into k consecutive blocks of near-equal size (the first n mod k blocks one row larger).
- **Implementation.** Own code, or scikit-learn `KFold(shuffle=False)`, which gives exactly these blocks (`T-lib` test).
- **Reference.** `eigenvector_cv` (*to verify*).

<a id="loo"></a>
### Leave-one-out (`validate.loo`) · T1.11
- **Definition.** n folds, one row each; with groups: leave-one-group-out.
- **Implementation.** Wrap scikit-learn `LeaveOneOut` / `LeaveOneGroupOut`.
- **Reference.** `stone1974cv`.

<a id="repeated-k-fold"></a>
### Repeated k-fold (`validate.repeated_kfold`) · T1.11
- **Definition.** k-fold repeated r times with different shuffles; each repeat is a full partition.
- **Parameters.** `k`, `repeats` (default 5 *to confirm*), `rng`.
- **Metrics.** RMSECV per repeat, then mean and SD over repeats (N9).
- **Implementation.** Wrap scikit-learn `RepeatedKFold`.

<a id="group-k-fold"></a>
### Group k-fold (`validate.group_kfold`) · T1.11
- **Definition.** k-fold over groups: every group is in exactly one validation fold. Several group columns are combined into one label (`A|B`, as pengoo `validate_cv_groups`); a missing group label → node error (N1).
- **Parameters.** `k`, `shuffle`, `rng`.
- **Implementation.** Wrap scikit-learn `GroupKFold(shuffle=True, random_state=…)` (needs scikit-learn ≥ 1.6; we pin 1.9.x).
- **Reference.** `esbensen2010validation`.

---

## 6. PLS regression

<a id="pls"></a>
### PLS regression, NIPALS (`model.pls`) · T1.12a
- **Definition.** Find A latent variables (scores T = X₀R) that maximise covariance with Y, and regress Y on them. PLS1: one y column; PLS2: several.
- **Formula.** X₀ = X − x̄ (training means), Y₀ = Y − ȳ; X is **not** scaled by default (Q4). For a = 1 … A on the deflated matrices Xₐ, Yₐ:
  wₐ = first left singular vector of XₐᵀYₐ (‖wₐ‖ = 1; PLS1: wₐ = Xₐᵀy / ‖Xₐᵀy‖) · tₐ = Xₐwₐ · pₐ = Xₐᵀtₐ / (tₐᵀtₐ) · qₐ = Yₐᵀtₐ / (tₐᵀtₐ) · Xₐ₊₁ = Xₐ − tₐpₐᵀ · Yₐ₊₁ = Yₐ − tₐqₐᵀ.
  Rotations R = W(PᵀW)⁻¹, coefficients B = RQᵀ (p × k), prediction ŷ = ȳ + (x − x̄)B.
- **Steps.** `fit`: 1 centre X and Y with training means · 2 NIPALS loop (scikit-learn) · 3 store x̄, ȳ, W, P, Q, R, T, B. `apply`: 4 ŷ = ȳ + (x − x̄)B.
- **Outputs.** scores T, loadings P, weights W, y-loadings Q, rotations R, coefficients B per LV count, intercept, explained X and Y variance per component.
- **Parameters.** `n_components` A: 1 ≤ A ≤ min(n_train − 1, p), default 10 *to confirm* (capped at the bound); `scale` ∈ {false, true}, default false (Q4; true is kept only to reproduce old pengoo results).
- **Edge cases.** A above the bound → `BLOCK_PARAM_INVALID` (reason `bounds`). Constant y → `BLOCK_CONSTANT_RESPONSE` (N13). NaN → N1. PLS2 NIPALS inner loop is iterative (scikit-learn `max_iter=500`, `tol=1e-06`); non-convergence warning from scikit-learn is passed to the node log.
- **Reference values.** Mevik & Wehrens 2007 on `gasoline_nir` (`testdata/expected/gasoline_nir_pls.json`: LOO RMSEP for 0–10 components, test RMSEP, explained variance, 2-component test predictions; R `pls` kernel PLS, same predictions as NIPALS for PLS1). Hand calculation for PLS1 with A = 1 (w ∝ X₀ᵀy). PLS2: R `pls` (other software) values *to obtain* in T1.12a, or a published PLS2 example.
- **Tolerance.** `T-pub` against the paper; `T-lib` against scikit-learn `PLSRegression(scale=False)` predictions (PLS1); `T-iter` for PLS2.
- **Implementation.** Wrap scikit-learn `PLSRegression` (1.9.1 signature `n_components=2, scale=True, max_iter=500, tol=1e-06`: we always pass `scale` explicitly). Sign of each component is fixed after the fit (largest-|w| element positive, N16) so outputs are reproducible across BLAS builds.
- **Library differences.** scikit-learn default `scale=True` autoscales X and Y with ddof 1 (all pengoo PLS results). R `pls` default: centring only.
- **Reference.** `wold1984collinearity`, `geladi1986pls`, `hoskuldsson1988`, `wold2001pls`, `mevik2007pls`.

<a id="pls-lv-sweep"></a>
### LV sweep from one fit · T1.12a
- **Definition.** Predictions for every LV count a = 1 … A from one fit with A components.
- **Formula.** Bₐ = R₍:,1..a₎ Q₍:,1..a₎ᵀ, ŷₐ = ȳ + (x − x̄)Bₐ. Valid because the first a NIPALS (and SIMPLS) components do not depend on later ones. a = 0: ŷ₀ = ȳ (training mean).
- **Reference values.** Property: sweep at a equals a separate fit with `n_components = a` (`T-lib` for PLS1, `T-iter` for PLS2), for every a.
- **Note.** The intercept-only (a = 0) prediction is the **training** mean; R `pls` prints the test-set mean for its 0-component test RMSEP (see the notes in the expected file).
- **Implementation.** Port pengoo `_predict_pls_at_lv` (one function replacing its two copies).

<a id="simpls"></a>
### SIMPLS (algorithm option of `model.pls`) · T1.12b
- **Definition.** de Jong's algorithm: weights are computed from the cross-product S = X₀ᵀY₀, deflated by projection, so scores are linear combinations of the **original** centred X.
- **Steps** (de Jong 1993, Appendix; each line checked against the paper in T1.12b): 1 S = X₀ᵀY₀ · for a = 1 … A: 2 rₐ = first left singular vector of S · 3 tₐ = X₀rₐ, centre, normalise ‖tₐ‖ = 1 and divide rₐ by the same norm · 4 pₐ = X₀ᵀtₐ, qₐ = Y₀ᵀtₐ · 5 vₐ = pₐ orthogonalised against v₁ … vₐ₋₁, normalised · 6 S ← S − vₐ(vₐᵀS) · 7 B = RQᵀ.
- **Reference values.** PLS1: identical predictions to NIPALS (de Jong 1993) — gasoline values of Mevik & Wehrens 2007 (`T-pub`) and NIPALS (`T-iter`). PLS2: R `pls` `method = "simpls"` (other software) values *to obtain* in T1.12b.
- **Implementation.** Own code (≈ 30 lines of NumPy; no maintained SIMPLS in our stack — T1.12b repeats the §12 search).
- **Reference.** `dejong1993simpls`.

<a id="vip"></a>
### Variable Importance in Projection (VIP) · T1.12b
- **Definition.** Weighted sum of squared weights per variable, each component weighted by the Y variance it explains.
- **Formula.** SSₐ = (tₐᵀtₐ) Σ_m q_{ma}² (sum over the k Y columns; PLS1: k = 1). VIPⱼ = √( p Σₐ SSₐ (wⱼₐ / ‖wₐ‖)² / Σₐ SSₐ ).
- **Steps.** 1 SSₐ from T and Q · 2 normalised weights · 3 weighted sum · 4 scale by p and take the square root.
- **Edge cases.** PLS2 (Q9): VIP depends on the relative scaling of the Y columns (documented in the block tooltip). The "VIP > 1" rule of thumb is a display threshold, not part of the method.
- **Reference values.** Properties: Σⱼ VIPⱼ² = p (`T-exact`); A = 1 → VIPⱼ = √p·|w̃ⱼ| (hand calculation). Independent value from other software (R `plsVarSel`, or `mixOmics` for PLS2) *to obtain* in T1.12b; pengoo values only as `test_vip_pengoo_regression`.
- **Tolerance.** `T-exact` for properties; `T-iter` against other software.
- **Implementation.** Port pengoo `calculate_vip` (already sums over Y columns; uses scikit-learn's unit-norm `x_weights_`).
- **Reference.** `wold1993vip` (*to verify*), `chong2005vip`, `mehmood2012review`.

---

<a id="plsda"></a>
## 7. PLS-DA (`model.plsda`) · T1.13
- **Definition.** PLS2 on a dummy-coded class matrix; a sample is assigned to the class with the largest predicted value.
- **Formula.** Classes sorted by label c₁ … c_G; Y = n × G indicator matrix (yᵢg = 1 if sample i is in class g, else 0); fit PLS (mean-centred X and Y, no Y scaling); ĉᵢ = argmax_g ŷᵢg.
- **Steps.** `fit`: 1 sorted class list · 2 indicator matrix · 3 PLS2 fit. `apply`: 4 predicted indicator values · 5 argmax (ties → lowest class index).
- **Decision rule.** Max rule only in T1.13. Binary case: two indicator columns; because rows of Ŷ sum to 1 (centred PLS with an intercept preserves the constant row sum), the max rule equals "ŷ of class 2 > 0.5". Threshold, LDA-on-scores and probabilistic rules are later options.
- **Outputs.** Predicted class, the G predicted values (used for ROC), PLS outputs.
- **Edge cases.** Only one class in the training rows → node error `BLOCK_CONSTANT_RESPONSE` (a constant response, N13). A class missing from a training fold: its column is constant in that fold → that class cannot be predicted; logged as a warning per fold. Unknown class at apply time is impossible (labels come from the training set).
- **Reference values.** Hand-worked binary example (4 samples, 2 variables, A = 1); property: row sums of Ŷ = 1 (`T-exact`); multi-class property tests; loose published check on `olive_oil_ftir` (CV accuracy ≥ 0.90, `testdata/expected/olive_oil_ftir_classification.json`, protocol unverified).
- **Implementation.** Our PLS block + scikit-learn label handling (`LabelBinarizer` gives one column for two classes — we always build G columns).
- **Reference.** `barker2003plsda`, `ballabio2013plsda`.

---

## 8. Metrics (`vibechem_core/metrics.py`) · T1.14
All metrics are computed in **original Y units** (inverse Y scaling first) and per Y column for PLS2. e = ŷ − y (Q7). n = number of predictions in the set. "Set" is calibration (predictions of the model fitted on all training rows, on those rows), cross-validation (out-of-fold predictions) or prediction (external test set).

<a id="regression-metrics"></a>
### Regression metrics
| Name | Formula | Notes |
|---|---|---|
| RMSEC / RMSECV / RMSEP | √( Σ eᵢ² / n ) | divisor n (N6); RMSECV aggregation see below |
| Bias | ē = (1/n) Σ eᵢ = mean(ŷ) − mean(y) | ISO 12099:2010 Eq. (1)–(3); positive = over-prediction (Q7) |
| SEP | √( Σ (eᵢ − ē)² / (n − 1) ) | bias-corrected SD of residuals; ISO 12099 §6.5 (*to verify*), `fearn2002sep` |
| R² (R²c, R²cv, R²p) | 1 − Σ eᵢ² / Σ (yᵢ − ȳ)² , ȳ = mean of y **in the same set** | not the squared correlation; can be negative on test data |
| Slope, intercept | least squares y = a + b·ŷ | reference on prediction, ISO 12099:2010 §5.4.1 (N7) |
| RPD | SD(y) / SEP, SD with ddof 1 over the same set | N8 (*to verify* in `fearn2002sep`) |
| RPIQ | (Q3 − Q1) / SEP, quartiles of y in the same set (linear interpolation, NumPy default) | N8 (*to verify* in `bellonmaurel2010rpiq`) |
| PRESS | Σ eᵢ² over the out-of-fold predictions | |
- **Reference values.** Every metric: hand calculation on a 5-sample example (Done when of T1.14), written out in the test file. Identity (property): RMSE² = ē² + SEP²·(n − 1)/n (`T-exact`).
- **Edge cases.** n < 2 → SEP, slope, R², RPD, RPIQ are undefined: returned as NaN with a warning (metrics are reported, not block inputs). SD(y) = 0 → R², RPD, RPIQ NaN with a warning. ISO 12099 asks for ≥ 20 validation samples for SEP and ≥ 10 for bias: below that, a warning (not an error).
- **Names in `Results.metrics`** (DATA_MODEL.md §4.2 takes them from here, N15): `rmsec`, `rmsecv`, `rmsep`, `r2c`, `r2cv`, `r2p`; the set-free names `bias`, `sep`, `slope`, `intercept`, `rpd`, `rpiq`, `press` refer to the set of that Results; `n_lv` is the LV count. Matches the DATA_MODEL.md §2.8 example.
- **Implementation.** Own NumPy (each metric is one line), scikit-learn `r2_score` as a `T-lib` cross-check. Port of pengoo `regression_metrics` definitions plus RPIQ and slope.
- **Reference.** `iso12099_2010`, `fearn2002sep`, `bellonmaurel2010rpiq`, `martens1989`.

<a id="rmsecv"></a>
### RMSECV aggregation
- **`pooled`** (default, Q6): RMSECV = √( PRESS / n ), PRESS over all out-of-fold predictions (each row predicted once per repeat). Same as R `pls` `RMSEP(…, estimate = "CV")` (gasoline reference).
- **`fold_mean`** (option): RMSECV = (1/k) Σ_f RMSE_f, RMSE_f over the rows of fold f. Unequal fold sizes make it differ from pooled.
- **Always stored:** RMSE_f per fold, their SD (ddof 1) and SE = SD/√k, so the 1-SE and paired t-test LV rules (T2.10a) work with either default.
- **Repeated CV:** per repeat, then mean and SD over repeats (N9).
- **Bias, R², SEP, RPD in CV** use the pooled out-of-fold predictions in both modes (as pengoo).
- **D2.** Out-of-fold predictions come from a pipeline re-fitted on each fold's training rows only (DATA_MODEL.md §4.6), never from preprocessing re-fitted on the validation fold.
- **Reference values.** Hand calculation with unequal folds (3 + 2 rows) where pooled ≠ fold mean; gasoline LOO values (`T-pub`, pooled). With LOO, `fold_mean` becomes the mean absolute error (each fold RMSE is |eᵢ|), which is another reason not to make it the default.
- **Reference.** `martens1989`, `mevik2007pls`.

<a id="classification-metrics"></a>
### Classification metrics
| Name | Definition |
|---|---|
| Confusion matrix C | C[t, p] = number of samples of true class t predicted as p (rows true, columns predicted; class order = sorted labels) |
| Accuracy | Σ_g C[g, g] / n |
| Sensitivity of class g | C[g, g] / Σ_p C[g, p] |
| Specificity of class g | Σ_{t≠g} Σ_{p≠g} C[t, p] / Σ_{t≠g} Σ_p C[t, p] |
| ROC-AUC | binary: AUC of the class-2 predicted value; multi-class: one-vs-rest AUC of each class's predicted value, then the unweighted (macro) mean |
- **Edge cases.** A class absent from the set → its sensitivity is NaN with a warning; AUC needs both labels present per class, otherwise NaN with a warning.
- **Reference values.** Hand-computed 3-class confusion matrix; AUC by hand as the fraction of (positive, negative) pairs ranked correctly, ties counting ½ (Fawcett 2006).
- **Tolerance.** `T-exact`.
- **Implementation.** scikit-learn `confusion_matrix`, `accuracy_score`, `roc_auc_score` (binary, called per class for one-vs-rest so PLS-DA values outside [0, 1] are accepted).
- **Reference.** `fawcett2006roc`, `ballabio2013plsda`.

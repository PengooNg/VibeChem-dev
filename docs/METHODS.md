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
| N11 | MSC with slope bᵢ ≤ 0 | node error, proposed code `BLOCK_MSC_SLOPE_INVALID` | Dividing by a negative or zero slope flips or explodes the spectrum; it means the reference does not fit that spectrum. |
| N12 | Savitzky–Golay default window | **11 points**, polyorder 2 | Common starting value; no paper prescribes one. Quan may prefer a different default. |
| N10 | Group-aware split / CV when the dataset has groups but the scheme ignores them | warning `VALIDATION_GROUPS_IGNORED` (already in DATA_MODEL.md §7) | Replicates in both training and validation inflate results (Esbensen & Geladi 2010). |

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
  | `T-pub` | published values | half a unit of the last printed digit (`atol`), `rtol=0` |
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
- **Parameters.** `window` w: odd, 3 ≤ w ≤ p, default 11 *(to confirm)*; `polyorder` P: 0 ≤ P < w, default 2; `deriv` d: 0 ≤ d ≤ P, default 0; `mode` ∈ {`interp`, `nearest`, `mirror`, `constant`, `wrap`}, default `interp`.
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

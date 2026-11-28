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
- [9. Validation](#9-validation): [cross-validation](#cv) · [LV-number rules](#lv-rules) · [preprocessing grid search](#grid-search) · [nested CV](#nested-cv)

---

## 0. Choices for Quan to confirm
Every item marked **(T1.04)** in TECH_STACK.md §11.2, plus the new choices found while drafting. "Suggested" is what the entries below use until Quan decides.

**Decided by Quan, 2026-11-25:** Q1–Q10 as suggested. N2, N3, N6, N7, N9, N10, N11, N13, N16 as suggested (N3: warn, centre, do not block later steps; N10: warn, do not block; N11, N13: warn and block = node error). N1, N4, N5, N8, N12, N14, N15 changed as written in their rows below; the entries follow these decisions. pengoo defects D1 and D2 (TECH_STACK.md §11.2) are noted where an entry touches them.

**(T1.04) items from the pengoo inventory**
| # | Question | Suggested answer | Why |
|---|---|---|---|
| Q1 | SNV: ddof of the per-spectrum SD (pengoo 0, skeleton engine 1) | **ddof = 1**, parameter with choices 0/1 | Same as the block template and the skeleton engine. The factor √((p−1)/p) is the same for every spectrum, so PLS predictions do not change; only the printed SNV values differ. Barnes et al. 1989 divisor checked by Quan 2026-11-25. |
| Q2 | Savitzky–Golay edge mode (pengoo `nearest`, SciPy default `interp`) | **`interp`** default; `nearest`, `mirror`, `constant`, `wrap` as options | `interp` fits the same polynomial to the last window, which is the Savitzky–Golay idea carried to the edge. `nearest` repeats the edge value and bends derivatives near the edges. |
| Q3 | Savitzky–Golay derivative `delta` | **signed axis step** `delta = λ₂ − λ₁` (derivative per axis unit); non-uniform axis → error | pengoo used `delta = 1` (per point), so its derivatives depend on the point spacing. With the signed step a descending wavenumber axis still gives d/dν. |
| Q4 | PLS X scaling default (scikit-learn `scale=True`; every pengoo PLS result used it) | **mean-centring only** (`scale=False`); autoscaling is a visible scaling block | Spectra share one unit, and autoscaling raises noise-only variables to the same weight as bands. `scale=False` reproduces the published gasoline results of Mevik & Wehrens 2007 (testdata PROVENANCE sanity check). Old pengoo results are not comparable 1:1. |
| Q5 | Kennard–Stone / SPXY distance space (pengoo: PCA scores of unit means, 99 % variance) | **raw X, Euclidean** default; option "PCA scores" (number of components or variance fraction); group-aware mode averages each sampling unit first | Raw X is the method as published (Kennard & Stone 1969, Galvão et al. 2005) and what the `kennard-stone` cross-check uses. PCA scores stay available for wide, noisy spectra. |
| Q6 | RMSECV aggregation default (pengoo `fold_mean`) | **`pooled`** = √(PRESS/n); `fold_mean` as option; per-fold RMSE always stored | Pooled is the chemometrics definition (Martens & Næs 1989), is correct for unequal folds and is what the R `pls` package reports (our T1.15 reference). Per-fold values are kept, so the 1-SE and t-test LV rules still work. |
| Q7 | Bias sign | **bias = mean(ŷ − y)**, positive = over-prediction | ISO 12099:2010 Eq. (1)–(3): "a positive bias when the predictions are too high" (checked in the official preview). Same sign as pengoo, so no old results flip. |
| Q8 | "int ≥ n → LOO" rule in `make_cv_splitter` | **no silent switch**: 2 ≤ k ≤ n_units (samples, or groups when grouped); k > n_units → `BLOCK_PARAM_INVALID` (reason `constraint`); k = n_units allowed (equals LOO / leave-one-group-out); LOO is its own scheme | A silent change of scheme hides a typo (k = 100 on 60 samples). The result is the same as asking for LOO, so nothing is lost. |
| Q9 | PLS2 VIP | **offer it**: SS of component a summed over all Y columns (Eq. in [VIP](#vip)); documented as depending on Y scaling; per-response VIP not in T1.12b | pengoo's formula already sums over Y columns, so it is PLS2-ready. Multi-response VIP is the form used in the original VIP chapter (Wold et al. 1993). |
| Q10 | Model-comparison defaults `n_perm = 9999`, `n_boot = 2000` (marked T1.04 / P6) | **defer to the P6 validation step** (not a Phase 1 method) | No Phase 1 block uses them. |

**New choices found while drafting**
| # | Question | Suggested answer | Why |
|---|---|---|---|
| N1 | Missing values (NaN is allowed in `SpectralDataset.X`) in Phase 1 blocks | **Decided:** when no imputation block is upstream, rows with NaN in X (or in y where y is used) are **removed once, where the data enters the pipeline** (the engine inserts the removal before the first block, T2.04), with warning `DATA_MISSING_VALUES_REMOVED` (params `count`, `sample_ids`) and a dataset-history entry. Columns are never dropped. Blocks themselves never drop rows; a block that still receives NaN (only possible through direct Python API calls) raises the guard error `BLOCK_MISSING_VALUES` | Removing rows in one visible place keeps y, groups and sample IDs aligned and keeps n the same in every fold and in the test set. Imputation is a P6 block. |
| N2 | Autoscale/Pareto SD ddof | **ddof = 1** | Same as SNV, SEP, RPD and scikit-learn's own PLS `scale=True`. A common factor, so PLS predictions do not change. `StandardScaler` uses ddof 0, so T1.09 corrects its `scale_` or uses two lines of NumPy. |
| N3 | Autoscale/Pareto on a zero-variance column | centre it, leave it unscaled (scale 1) and **warn** in the node log | Flat columns occur after cuts or detector saturation; an error would block common pipelines. Same as `StandardScaler`, but not silent. |
| N4 | Savitzky–Golay on a non-uniform axis | **Decided:** relative spacing deviation max\|Δλᵢ − Δλ̄\| / \|Δλ̄\| ≤ 1 % → `delta` = mean signed step Δλ̄, no warning; > 1 % → `delta` = 1 (per point), warning `BLOCK_AXIS_NOT_UNIFORM` (params `max_deviation`) and the derivative unit recorded as "per point" in the output | SG assumes equal spacing. Real axes (Raman CCD in cm⁻¹, rounded wavenumbers) are often slightly uneven; the mean step is exact enough there. Large deviations fall back to per-point derivatives, visibly. An interpolation block is the clean fix. |
| N5 | Kennard–Stone start | **Decided:** both variants as a block parameter `start` ∈ {`most_distant` (default: the two most distant samples, as in pengoo and Daszykowski et al. 2002), `nearest_mean` (first the sample nearest the mean of z, then the max–min loop)}; same parameter in SPXY; ties → lowest row index | The user picks the variant in the block's parameter panel like any other hyperparameter. References checked by Quan 2026-11-25; the T1.10 cross-check runs the `kennard-stone` package with the `start` it implements. |
| N6 | RMSEC divisor | **n** (not n − A − 1) | Same as RMSECV/RMSEP and pengoo; degrees-of-freedom versions are not comparable across LV counts in the UI. |
| N7 | Slope | **b in y = a + b·ŷ** (reference regressed on prediction) | ISO 12099:2010 §5.4.1 (checked in the preview). The predicted-vs-measured plot shows ŷ against y, so the plot's visual slope is the reverse regression; the UI labels it. |
| N8 | RPD and RPIQ denominator (pengoo: RPD = SD/RMSE) | **Decided (current practice):** **RMSE of the same set** for both, i.e. RPD = SD(y)/RMSE, RPIQ = (Q3 − Q1)/RMSE (RMSEC, RMSECV or RMSEP) | Current applied practice (soil, food and recent NIR papers) and pengoo; the ratio includes bias, so a biased model scores lower. Same as SEP-based ratios when bias ≈ 0. Fearn 2002 (RPD) and Bellon-Maurel et al. 2010 (RPIQ) are still cited as the original papers (Quan, 2026-11-25). |
| N9 | Repeated k-fold RMSECV | pooled RMSECV **per repeat**, then mean and SD over repeats | One prediction per sample per repeat; pooling across repeats would count samples several times. |
| N10 | Split / CV when the dataset has groups but the scheme ignores them | warning `VALIDATION_GROUPS_IGNORED` (already in DATA_MODEL.md §7) | Replicates in both training and validation inflate results (Esbensen & Geladi 2010). |
| N11 | MSC with slope bᵢ ≤ 0 | node error, proposed code `BLOCK_MSC_SLOPE_INVALID` | Dividing by a negative or zero slope flips or explodes the spectrum; it means the reference does not fit that spectrum. |
| N12 | Default parameter values (the values a block starts with on the canvas; users change them) | **Decided:** SG window 11 / polyorder 2; random split test fraction 0.25, 5 y-bins; k-fold **k = 5**; repeats 5; PLS maximum LVs **20** (capped at min(n_train − 1, p)) | Common starting values; no paper prescribes them. k = 5 and 20 LVs follow pengoo. |
| N13 | SPXY with all y equal | node error, proposed code `BLOCK_CONSTANT_RESPONSE` | max d_y = 0 makes the y term undefined; a silent fall-back to Kennard–Stone would hide it. |
| N14 | New codes | **Decided:** errors `BLOCK_MSC_SLOPE_INVALID` (N11), `BLOCK_CONSTANT_RESPONSE` (N13) and the guard error `BLOCK_MISSING_VALUES` (N1); warnings `DATA_MISSING_VALUES_REMOVED` (N1) and `BLOCK_AXIS_NOT_UNIFORM` (N4). All are **proposals**; each implementing step adds its code to DATA_MODEL.md §7 in its own PR | CLAUDE.md#hard-rules: codes are added to DATA_MODEL.md first, not invented in code. This PR changes DATA_MODEL.md only for the metric names (N15). |
| N15 | Metric names in `Results.metrics` | **Decided:** every metric is computed and stored **for every set** (calibration `c`, cross-validation `cv`, prediction `p`): `rmsec/rmsecv/rmsep`, `r2c/r2cv/r2p`, `sec/secv/sep`, `bias_c/bias_cv/bias_p`, `slope_c/slope_cv/slope_p`, `intercept_c/intercept_cv/intercept_p`, `rpd_c/rpd_cv/rpd_p`, `rpiq_c/rpiq_cv/rpiq_p`, `rss_c/press/rss_p`; `n_lv` | Chemometric names per set (SEC/SECV/SEP). PRESS is the CV sum by definition; for calibration and test the same sum is a residual sum of squares. DATA_MODEL.md §2.8 example updated. |
| N17 | LV counts an LV rule may choose (T2.10a) | **a = 1 … A**; a = 0 (training mean) is in the CV curve but never chosen | A PLS model needs at least one component (`n_components ≥ 1`); same as pengoo. A curve whose minimum is at a = 0 shows that the model does not beat the mean |
| N18 | Default LV rule of `validate.cv` | **`global_min`** | pengoo default; the other rules are options in the parameter panel |
| N19 | 1-SE rule with repeated CV | SE over **all r · k folds** of all repeats: SE = SD(RMSE_f, ddof 1) / √(r·k) | Every LV count is scored on the same folds, so the r·k fold errors are the sample the rule needs; with one repeat this is the §8 SE. The fold errors are not independent (training sets overlap, repeats reuse rows), so this SE is too small and 1-SE leans to fewer LVs less than it should; the corrected variance of Nadeau & Bengio is a later option (RISKS.md R61) |
| N20 | Paired t-test rule | pengoo's **forward stepping**: from a = 1, add an LV while the two-sided paired t-test of the fold RMSEs of a and a + 1 gives p < α **and** RMSECV falls; α a parameter, default 0.05 (pengoo fixed 0.05); an option, not the default (N18) | **pengoo rule (Quan)**: Quan's own rule, carried over for pengoo users; no paper. The published alternatives are the options `haaland_thomas` (N25) and `van_der_voet` (N26). Dependent fold errors make the test reject too often, i.e. choose more LVs (RISKS.md R61) |
| N21 | Wold R threshold | **0.95**, parameter; R(a) = PRESS(a)/PRESS(a−1) from a = 2 | The value 0.95 is pengoo's default (Quan accepts it). Wold 1978 is cited for the PRESS-ratio criterion only; the 0.95 value is not taken from that paper |
| N22 | Classification metric names in `Results.metrics` (R36) | Always both averages over the classes g, for every set c/cv/p: **macro** (unweighted mean) `sensitivity_c/cv/p`, `specificity_c/cv/p`, `auc_c/cv/p`; **weighted** (weight n_g / n, n_g = true count of class g in the set) `sensitivity_w_c/cv/p`, `specificity_w_c/cv/p`, `auc_w_c/cv/p`; plus `accuracy_c/cv/p` and the class ratio `class_ratio_c/cv/p` (N27). Per-class values in `details.per_class` (`{class: {sensitivity, specificity}}`). Optional, parameter `micro_metrics` (bool, default **false**): micro averages `sensitivity_micro_*`, `specificity_micro_*`, `auc_micro_*` (counts or one-vs-rest scores pooled over the classes before the ratio), computed only when on | Quan's design (2026-11-28). Class labels are user text, so they stay out of metric names. Macro does not let a large class hide a poor small one; weighted shows what a class-blind reader expects; showing both with the class ratio lets the reader judge, with no hidden gate. Identities: weighted sensitivity = accuracy (Σ_g (n_g/n)·C[g,g]/n_g = Σ_g C[g,g]/n), and for single-label multi-class data micro sensitivity = accuracy too (pooled TP = Σ_g C[g,g], pooled TP + FN = n); both are still stored so each family is complete. Computed in T2.10b (CV of PLS-DA), names fixed now |
| N23 | Fold sets that are not a partition, in CV | node error `VALIDATION_FOLDS_INVALID` (new, `params.reason` ∈ `duplicate_prediction`, `missing_prediction`; `params.repeat`) | One out-of-fold prediction per row per repeat (R41); a `custom` or hold-out `Folds` can break it, and RMSECV would silently count rows twice or skip them |
| N24 | LV range of a CV curve when folds were capped differently | A = **smallest** fitted component count over the folds | A fold with fewer training rows can be capped lower (n_min = n_train − 1); every LV count of the curve then has a prediction for every row |
| N25 | Haaland–Thomas F-test rule (`haaland_thomas`) | a_min = argmin over a ≥ 1 of PRESS(a); F(a) = PRESS(a)/PRESS(a_min); p(a) = P(F_{n,n} ≥ F(a)), n = rows of the `Folds`; the smallest a ≤ a_min with p(a) > α. α a parameter, **default 0.25** | Haaland & Thomas 1988: the fewest factors whose PRESS is not significantly larger than the minimum PRESS, with an F-ratio probability of 0.75 (α = 0.25) chosen empirically by the authors. α = 0.25 and the (n, n) degrees of freedom are taken from secondary restatements (e.g. Bunseki Kagaku 45 (1996) 85, which tests against F(10,10; α) with α = 0.25 "as Haaland et al."); the 1988 paper itself was not read here. With repeats PRESS is the mean over repeats (§9 step 4) and n stays the number of rows |
| N26 | van der Voet randomisation rule (`van_der_voet`) | a_min as in N25; for a = 1 … a_min − 1: d_i = ē_i(a)² − ē_i(a_min)², ē_i² = squared out-of-fold residual of row i averaged over repeats; T = mean(d); T*_b = mean(s_b · d) with independent random signs s_b ∈ {−1, +1}, b = 1 … B; p(a) = (#{T*_b ≥ T} + ½)/(B + 1); the smallest a with p(a) > α, else a_min. α **default 0.05**, B **default 1000**, signs from the run's `numpy.random.Generator` | van der Voet 1994 sign-swap (randomisation) test of squared prediction errors; the p formula and the a < a_min search follow R `pls` `selectNcomp(method = "randomization")` (Mevik & Wehrens 2007), which defaults to α = 0.01, B = 999 and also allows a = 0; here α = 0.05 and B = 1000 (Quan) and a ≥ 1 (N17). Averaging the squared residuals over repeats keeps one paired value per row |
| N27 | Class ratio and the severe-imbalance warning (N22) | `class_ratio` = largest / smallest true class count in the set (∞ when a class of the model is absent from the set: §8 edge cases already warn), always reported. Warning `METRIC_CLASSES_SEVERELY_UNBALANCED` only when ratio **> threshold** (strictly), parameter `severe_imbalance_ratio`, **default 20** ("20:1") | The ratio is the imbalance ratio IR of Fernández, García, del Jesus & Herrera 2008 (§2.1: majority / minority instances; for several classes we take the largest over the smallest class). **20 is Quan's chosen heuristic default; no source was found that defines 20:1 as "severe"** (published cut-offs differ, e.g. Fernández et al. 2008 §5 call IR > 9 "high imbalance" in their benchmark grouping) |
| N28 | CV curve of PLS2 (k > 1 Y columns) (T2.10b) | **PRESS summed over the k columns in the space the model was fitted in**: each fold's residuals are divided per column by the fold model's Y scale (built-in `scale` SD, times the `y_transform` scale when connected; 1 when neither), so RMSECV(a) = √(PRESS(a)/(n·k)); RMSE_f and the row residuals ē_i² are summed the same way, so all six LV rules work unchanged. `metrics` = `rmsecv`, `press` of that curve at n_lv and `n_lv`; the §8 CV metrics of every column, in original units, in `details.per_column` (`{column: {rmsecv, r2cv, …}}`). PLS1 (k = 1) keeps the curve in original Y units, as T2.10a. Unscaled PLS2 (fitted Y scale 1 for every column: `scale` = false and no `y_transform`, or one that only centres) whose largest / smallest Y column variance (ddof 1, all rows of the `Folds`) is > `y_variance_ratio` (parameter, **default 10**) → warning `VALIDATION_Y_SCALES_DIFFER` (`params.ratio`, `params.threshold`) | Decision by Quan (2026-11-28, option 1): one model has one LV count, so the rules need one curve; the fitted space is the one PLS2 itself optimises in (MATLAB `plsregress` also sums the MSE over responses). Column names are user text, so per-column values stay out of metric names (as class labels, N22). Unscaled, a column with 10× the variance weighs 10× in PRESS and can decide the LV count alone; the warning says so and the user can scale Y. **The default 10 (one order of magnitude of variance) is a heuristic; no source was checked for it** |
| N29 | LV criterion of PLS-DA in CV (T2.10b) | **PRESS of the indicator matrix** (PLS-DA = PLS2 on the G indicator columns, fitted unscaled, so the raw indicator space; N28 curve), so all six LV rules work. The CV error rate 1 − accuracy for every a = 0 … A (mean over repeats) is stored as `details.error_rate` for display. `metrics` = the N22/N27 CV names at n_lv (mean over repeats) and `n_lv`; `details.per_class` = per-class sensitivity and specificity (mean over repeats). A class absent from a fold's training rows → its predicted value is 0 in that fold (its indicator was 0 on every training row) and warning `VALIDATION_CLASS_MISSING_IN_FOLD` (`params.class`, `params.fold`, `params.repeat`) | Decision by Quan (2026-11-28): the PRESS criterion keeps every rule usable; an error-rate criterion (minimum CV classification error) only suits `global_min`/`one_se` and is a later option, not built |
| N30 | Preprocessing grid search (T2.10c): candidate order, duplicates, the best candidate, no `model` output | **Order**: the product of the `search_space` slots in the order written, the last slot changing fastest; a `null` option skips its slot. **Duplicates**: chains with the same blocks and the same parameters (defaults filled in) in the same order are one candidate, the first one kept. **Best**: the smallest RMSECV at the candidate's own chosen LV count on its own CV curve (the curve its LV rule worked on: Y units for PLS1, the fitted space for PLS2 and PLS-DA, N28, N29); ties → the first candidate. `Results.metrics` = the best candidate's CV metrics. **No `model` output** in v1, why: the search re-fits each candidate's preprocessing per fold and on all training rows only inside its generated branch; the fitted states of the best chain's steps (MSC reference, autoscaling means and SDs, …) are not collected into a `Model`. A PLS (or PLS-DA) state alone holds only the regression on *preprocessed* X, so applied to raw spectra it predicts wrong values without an error. **What the user does instead:** read `details.best_chain` (the full chain with every parameter), wire those blocks between the data and the model block on the canvas and run `validate.cv`; that pipeline's `model` output is the one to save and apply. **Options** (DATA_MODEL.md §4.7 point 4): (a) no `model` output in v1 (current): nothing new to store and the deployed chain stays visible on the canvas, at the cost of one manual rewiring step; (b) a `Model` that bundles the fitted chain states with the PLS state: one-click deploy, but a new state layout for `.vcm` packages, prediction and the leakage audit (`fitted_rows` per step); (c) the UI turns `best_chain` into canvas nodes: the graph stays the only truth and no format changes, but it is canvas work (Phase 4). **Revisited with the UI**, when (b) and (c) can be weighed on a real flow | Product order is the order the user wrote, so the table reads like the search space; pengoo sorts by step identity only to share prefixes between neighbours, which our cache will do by content hash. Duplicates come from the same block in two slots or from writing a default out; running them twice changes nothing. The RMSECV at n_lv is what every LV rule already chose on, and it exists for all three model kinds. **The best candidate's metrics are optimistic** (the same folds chose the chain and the LV count); an unbiased estimate is nested CV (T2.10d) |
| N31 | Grid-search size caps and workers (T2.10c) | **Decided by Quan (2026-11-28).** N = candidates after deduplication, M = LV counts swept = the model block's `n_components` (default 20). **Hard caps**, checked before any candidate is built or run: N ≤ 1000, M ≤ 1000 and N·M ≤ 50000; above any → `BLOCK_PARAM_INVALID` on the search node, `reason` `too_many_candidates` / `too_many_lv` / `search_too_large` (checked in that order), params `n_candidates`, `n_lv`, `n_iterations` (= N·M), `limit`. **Serial limit:** one worker runs at most 1000 iterations (N·M); above that the search runs only in parallel (the engine uses several cores and the search node gets a caution warning), and with one worker N·M > 1000 is refused. **`n_jobs`** (int, default −10): positive = that many workers, negative = all cores minus \|n_jobs\| (−10 = all cores minus 10), clamped to ≥ 1; 0 is invalid. **Workers (decision by Quan: option A, 2026-11-28):** w = min(effective `n_jobs`, the executor's workers) is the core budget of every scheduler stage that holds the search's branch tasks (the other tasks of those stages share it; several searches in one stage → the smallest w). N·M > 1000 with w = 1 → `BLOCK_PARAM_INVALID` on the search node, `param_id` `n_jobs`, `reason` `serial_too_large`, params `n_iterations`, `workers`, `limit`, before any candidate is built (after the hard caps); N·M > 1000 with w > 1 → warning `VALIDATION_SEARCH_PARALLEL_ONLY` (params `n_iterations`, `workers`) on the search node. | Quan's limits. The default search (252 candidates × 20 LV = 5040 iterations) already needs parallel workers; the caps stop a typo (e.g. 40 options in four slots = 2.5 million chains) from building millions of nodes. The values are Quan's choice, not from a source |
| N32 | Nested CV (T2.10d): what the inner loop tunes, how the outer folds predict, no `model` output | **Inner loop:** on each outer fold's training rows, the `inner_folds` block (`{block_id, params}` of a fold block, a scheme parameter, decided by Quan 2026-11-28) makes the inner folds, and a [grid search](#grid-search) with the node's `search_space` and `validate.cv` parameters picks the chain and the LV count (best = lowest inner RMSECV at the candidate's n_lv, N30). Default `search_space` = `[[null]]`: one empty chain, so only the LV count is tuned (the LV rule on the inner curve). Selection parameters are tuned the same way once selection blocks exist (they are Spectra steps; none in v1). **Outer prediction:** the chosen chain and the model re-fitted on the outer training rows, at the chosen n_lv (the fold model's first n_lv components = a refit, [LV sweep](#pls-lv-sweep)). **Outer metrics:** the `validate.cv` CV metrics (§8 names, same `aggregation`, mean over repeats, N9) of the out-of-fold predictions, each fold at its own n_lv; no LV count is chosen on the outer folds. **Seeds:** each outer fold's inner run has its own seed from the run's Generator (a shuffled inner fold block gives different inner folds per outer fold). **No `model` output** in v1 (DATA_MODEL.md §4.7 point 5): nested CV estimates the performance of the *tuning procedure*; every outer fold may pick another chain and n_lv, so there is no single model to return. The model to deploy is the procedure run once on all rows: a `validate.cv` (LVs only) or a grid search and then `validate.cv` on its best chain (N30); the nested result is that model's honest performance estimate. | The inner search sees only the outer training rows (the compiler's leakage rules check each inner run), so the outer metrics carry no selection bias (Varma & Simon 2006; Filzmoser et al. 2009, repeated double CV). Reusing the grid search keeps one tuning rule for both. The outer folds use the node's own `folds` input, so any fold scheme works on either level (PRD F-43). A bundled final model has the same open questions as N30 (b) |
| N16 | PLS component sign | fix after fitting: largest-\|w\| element of each weight vector positive (scores and loadings flipped with it) | Signs from SVD/NIPALS can differ between BLAS builds; predictions do not change, plots and saved states do (ARCHITECTURE.md: same results across OS). |

---

## 1. Conventions
- **Data.** X is n × p (rows = spectra, columns = axis points λ₁ … λ_p); y is n × k (k = 1: PLS1, k > 1: PLS2). x̄ⱼ is a column mean, x̄ᵢ· a row (spectrum) mean. "Training rows" are the rows a fitted block's `fit` sees; `apply` uses only statistics learned in `fit` (CLAUDE.md#hard-rules; this is why pengoo defect D2 cannot happen).
- **Residual.** e = ŷ − y (Q7). All metrics are in original Y units: any Y scaling is inverted before metrics.
- **Standard deviation.** ddof = 1 unless an entry says otherwise.
- **Missing values.** Rows with NaN are removed once where the data enters the pipeline, with a warning (N1); blocks never see NaN.
- **Randomness.** Every random choice takes a `numpy.random.Generator`; scikit-learn functions that need an integer seed get one drawn from that Generator (`int(rng.integers(2**32))`).
- **Ties** (distances, class scores) go to the lowest row or class index, so results are deterministic.
- **Tolerance classes** used in the entries (QA.md §3: tolerances always explicit):
  | Class | Use | `assert_close` |
  |---|---|---|
  | `T-exact` | closed-form hand calculation, algebraic identity | `rtol=1e-10, atol=1e-12` |
  | `T-lib` | our block vs the library it wraps, same algorithm | `rtol=1e-10, atol=1e-12` |
  | `T-iter` | iterative algorithm vs another implementation (NIPALS PLS2, SIMPLS vs NIPALS) | `rtol=1e-6, atol=1e-9` |
  | `T-pub` | published values | the tolerance recorded in the `testdata/expected/` file (gasoline: `rtol=1e-3`, proposed in T0.08); otherwise half a unit of the last printed digit (`atol`), `rtol=0` |
- **Software and data cited by the entries:** scikit-learn `pedregosa2011sklearn`, SciPy `virtanen2020scipy`, gasoline data `kalivas1997`.
- **Entry fields.** Definition · Formula · Steps (what `# Step N:` comments follow) · Parameters (defaults) · Edge cases · Reference values (independent, never pengoo or Quasar: TECH_STACK.md §11.1 rule 3, §11.2 rule 5) · Tolerance · Implementation · Library differences.

---

## 2. Preprocessing

<a id="cut"></a>
### Range cut (`preprocess.cut`) · T1.07
- **Definition.** Keep the axis points that lie inside one or more ranges.
- **Formula.** keep j ⇔ ∃ r: lo_r ≤ λⱼ ≤ hi_r (bounds inclusive).
- **Steps.** 1 for each range, mark λⱼ with lo ≤ λⱼ ≤ hi (lo/hi may be given in either order) · 2 union of the marks · 3 reject an empty selection · 4 keep the marked columns in their original axis order.
- **Parameters.** `ranges`: list of (lo, hi) in axis units, at least one (parameter type `wavelength_ranges`, DATA_MODEL.md §5.2). Default `[[-1e9, 1e9]]`: keeps every point of any real spectral axis (no-op until the user sets ranges) *(proposed T1.07)*.
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
- **Steps.** `fit`: 1 m = column mean of training X (or the user reference). `apply`: 2 for each spectrum, least-squares fit of aᵢ + bᵢ·m · 3 reject bᵢ ≤ 0 or bᵢ = 0 (a constant spectrum has bᵢ = 0, detected as "all values equal" because rounding can leave a tiny positive bᵢ) · 4 x̃ᵢ = (xᵢ − aᵢ)/bᵢ. `apply` on an axis other than the fitted one → `BLOCK_INPUT_AXIS_MISMATCH` *(T1.07)*.
- **Parameters.** `reference`: `mean` (default) or a second input port with one spectrum on the same axis (`axis_match`). A reference input with more than one row is replaced by the mean of its rows (one row = that spectrum); the history entry records which option and how many rows were used.
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
- **Steps.** 1 spacing check (N4): deviation ≤ 1 % → Δ = mean signed step Δλ̄; otherwise Δ = 1 (per point) and warning `BLOCK_AXIS_NOT_UNIFORM` · 2 validate w, P, d · 3 one `savgol_filter` call on the whole matrix (`axis=1`) with `delta = Δ`.
- **Parameters.** `window` w: odd, 3 ≤ w ≤ p, default 11 (N12); `polyorder` P: 0 ≤ P < w, default 2; `deriv` d: 0 ≤ d ≤ P, default 0; `mode` ∈ {`interp`, `nearest`, `mirror`, `constant`, `wrap`}, default `interp`.
- **Edge cases.** w > p → `BLOCK_PARAM_INVALID` (`interp` needs w ≤ p). Even w → `BLOCK_PARAM_INVALID` (reason `not_odd`, DATA_MODEL.md §5.3). Non-uniform axis → N4 (mean step, or per point with warning `BLOCK_AXIS_NOT_UNIFORM`). Derivative units: signal unit per axis unit to the power d, or per point to the power d after the N4 fall-back (recorded in the output).
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
- **Steps.** 1 strata = classes, or y binned into `n_bins` quantile bins (default 5, N12), or none · 2 within each stratum draw the test share with the Generator · 3 union.
- **Parameters.** `test_fraction` (0 < f < 1, default 0.25, N12) or `n_test`; `stratify` ∈ {none, classes, y}; `rng`.
- **Edge cases.** Fewer than 2 rows in a stratum → that stratum goes to training and a warning is logged. Groups present → group-aware selection (see below) or `VALIDATION_GROUPS_IGNORED` warning (N10).
- **Reference values.** Properties: train ∪ test = all rows, disjoint, sizes as requested (± 1 per stratum), stratum shares kept; same seed → same split.
- **Tolerance.** Exact.
- **Implementation.** Wrap scikit-learn `train_test_split` (seed drawn from the Generator).

<a id="kennard-stone"></a>
### Kennard–Stone (`split.kennard_stone`) · T1.10
- **Definition.** Select training samples that cover the X space uniformly: start with the two most distant samples (or, with `start = nearest_mean`, the sample nearest the mean), then repeatedly add the sample whose distance to its nearest selected sample is largest.
- **Formula.** d(i, j) = ‖zᵢ − zⱼ‖₂, z = raw X rows (default) or PCA scores (Q5). Next k = argmax_{k ∉ S} min_{s ∈ S} d(k, s).
- **Steps.** 1 distance space z (raw X, or PCA scores fitted on all rows of the split input — the split is a design step, not a model fit) · 2 distance matrix · 3 start (N5): `most_distant` → pair argmax d; `nearest_mean` → the row with the smallest ‖zᵢ − z̄‖₂ · 4 max–min loop until all rows are ordered · 5 first n_train rows of the order → training.
- **Parameters.** `test_fraction`/`n_test`; `start` ∈ {`most_distant`, `nearest_mean`}, default `most_distant` (N5); `space` ∈ {`x`, `pca`}, default `x`; `n_components` or `variance` (for `pca`, default 0.99 as in pengoo).
- **Edge cases.** Ties → lowest index. Duplicate spectra (d = 0) are fine. n ≤ 2 → order is the row order. Memory: the n × n matrix (n = 5 000 → 200 MB in float64) — above a size threshold compute the min-distance vector incrementally (O(n) memory).
- **Reference values.** Hand-worked example of 6 points in 2-D with a unique order; hand-worked example for `nearest_mean` too; cross-check with the `kennard-stone` package (run with the `start` it implements, N5) on the gasoline data. Kennard & Stone 1969 printed example as an extra reference.
- **Tolerance.** Exact (orders equal).
- **Implementation.** Port pengoo `_ks_order` (vectorised update of the min-distance vector instead of the Python `max(rest, key=…)` loop).
- **Reference.** `kennard1969`, `daszykowski2002`.

<a id="spxy"></a>
### SPXY (`split.spxy`) · T1.10
- **Definition.** Kennard–Stone on a joint distance in X and y.
- **Formula.** d_xy(i, j) = d_x(i, j) / max d_x + d_y(i, j) / max d_y, with d_x as in Kennard–Stone and d_y(i, j) = ‖yᵢ − yⱼ‖₂ (|yᵢ − yⱼ| for one response).
- **Steps.** 1 d_x · 2 d_y · 3 normalise each by its maximum · 4 sum · 5 Kennard–Stone order on d_xy.
- **Parameters.** As Kennard–Stone (incl. `start`, N5); requires y (`requires: ["y"]`).
- **Edge cases.** All y equal, or with groups all unit-mean y equal (max d_y = 0, up to rounding: max d_y ≤ 10⁻¹⁰ · max |y|) → node error, proposed code `BLOCK_CONSTANT_RESPONSE` (N13); no silent fall-back to Kennard–Stone. NaN in y → removed at entry (N1).
- **Reference values.** Hand-worked example (5 samples, 1 response) where SPXY and KS give different orders.
- **Tolerance.** Exact (orders equal); distances `T-exact`.
- **Implementation.** Port pengoo SPXY distance (`Dx/max + Dy/max`).
- **Reference.** `galvao2005spxy`.

<a id="duplex"></a>
### Duplex (`split.duplex`) · T1.10 *(T1.00b addition, approved at the Phase 1 gate)*
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
- **Edge cases.** Stratified random split with groups: strata are assigned per unit (majority class or unit-mean y). An empty group label → node error `BLOCK_INPUT_REQUIREMENT_MISSING` (`requirement` = `groups`), as in the grouped CV schemes.
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
- **Parameters.** `k` (default 5, N12), `shuffle` (default true), `rng`.
- **Implementation.** Wrap scikit-learn `KFold`.
- **Reference.** `stone1974cv`.

<a id="venetian-blinds"></a>
### Venetian blinds (`validate.venetian_blinds`) · T1.11
- **Definition.** Row i (0-based, input order) goes to fold i mod k.
- **Implementation.** Own code (one line of NumPy).
- **Reference.** `eigenvector_cv`.

<a id="contiguous-blocks"></a>
### Contiguous blocks (`validate.contiguous_blocks`) · T1.11
- **Definition.** Rows in input order are cut into k consecutive blocks of near-equal size (the first n mod k blocks one row larger).
- **Implementation.** Own code, or scikit-learn `KFold(shuffle=False)`, which gives exactly these blocks (`T-lib` test).
- **Reference.** `eigenvector_cv`.

<a id="loo"></a>
### Leave-one-out (`validate.loo`) · T1.11
- **Definition.** n folds, one row each; with groups: leave-one-group-out.
- **Implementation.** Wrap scikit-learn `LeaveOneOut` / `LeaveOneGroupOut`.
- **Reference.** `stone1974cv`.

<a id="repeated-k-fold"></a>
### Repeated k-fold (`validate.repeated_kfold`) · T1.11
- **Definition.** k-fold repeated r times with different shuffles; each repeat is a full partition.
- **Parameters.** `k`, `repeats` (default 5, N12), `rng`.
- **Metrics.** RMSECV per repeat, then mean and SD over repeats (N9).
- **Implementation.** Wrap scikit-learn `RepeatedKFold`.

<a id="group-k-fold"></a>
### Group k-fold (`validate.group_kfold`) · T1.11
- **Definition.** k-fold over groups: every group is in exactly one validation fold. Several group columns are combined into one label (`A|B`, as pengoo `validate_cv_groups`); a missing group label → node error (group labels are metadata; N1 covers X and y only).
- **Parameters.** `k`, `shuffle`, `rng`.
- **Implementation.** Wrap scikit-learn `GroupKFold(shuffle=True, random_state=…)` (needs scikit-learn ≥ 1.6; we pin 1.9.x): shuffled groups are cut into k sets whose group counts differ by at most one. With `shuffle` false scikit-learn instead gives the largest remaining group to the fold with the fewest rows (balanced rows, not balanced group counts). The dataset has one `group_ids` column, so combining several group columns into `A|B` happens where the group column is built (import), not in this block.
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
- **Parameters.** `n_components` A (maximum LVs of the fit and the LV sweep): A ≥ 1, default 20 (N12); bound n_min = min(n_train − 1, p) per the edge cases; `n_components_mode` ∈ {`search_max`, `fixed`}, default `search_max` (see edge cases); `scale` ∈ {false, true}, default false (Q4; true is kept only to reproduce old pengoo results); `algorithm` ∈ {`nipals`, `simpls`}, default `nipals` (Quan, 2026-11-26): `simpls` follows [SIMPLS](#simpls) with the same `n_components`, `n_components_mode`, `scale`, edge cases and sign rule.
- **Edge cases.** Bound n_min = min(n_train − 1, p) (Quan, 2026-11-26): `n_components_mode = fixed` (A is the chosen model size) and A > n_min → `BLOCK_PARAM_INVALID` (reason `constraint`, `constraint` = `1 <= n_components <= <n_min>`; DATA_MODEL.md §5.3 has no reason `bounds`), the block does not run. `n_components_mode = search_max` (default; A is the upper end of the LV sweep) and A > n_min → A is capped at n_min with warning `BLOCK_PLS_COMPONENTS_CAPPED` (`from`, `to`). A fit with exactly n_min components warns `BLOCK_PLS_EQUIVALENT_MLR` (equivalent to MLR). One training row (n_min = 0) → `BLOCK_PARAM_INVALID` (`constraint` = `n_train >= 2`). Errors are raised before any warning. Constant y (PLS2: every Y column constant) → `BLOCK_CONSTANT_RESPONSE` (N13). NaN → removed at entry (N1). PLS2 NIPALS inner loop is iterative: we pass `max_iter=10000`, `tol=1e-20` (scikit-learn compares `tol` with the squared change of w, so this stops at ‖Δw‖ < 1e-10; the default `tol=1e-06` stopped PLS2 early, VIP off by 1.8e-5 relative, #60); non-convergence warning from scikit-learn is passed to the node log.
- **Reference values.** Mevik & Wehrens 2007 on `gasoline_nir` (`testdata/expected/gasoline_nir_pls.json`: LOO RMSEP for 0–10 components, test RMSEP, explained variance, 2-component test predictions; R `pls` kernel PLS, same predictions as NIPALS for PLS1). Hand calculation for PLS1 with A = 1 (w ∝ X₀ᵀy). PLS2: R values in `testdata/expected/r_pls_reference.json` (R 4.6.2, run by Quan 2026-11-27): `mixOmics` NIPALS PLS2 on R `oliveoil` (autoscaled Y), checked through VIP (`T-iter`, see [VIP](#vip)).
- **Tolerance.** `T-pub` against the paper; `T-lib` against scikit-learn `PLSRegression(scale=False)` predictions (PLS1); `T-iter` for PLS2.
- **Implementation.** Wrap scikit-learn `PLSRegression` (1.9.1 signature `n_components=2, scale=True, max_iter=500, tol=1e-06`: we always pass `scale` explicitly, and `max_iter=10000`, `tol=1e-20`, see edge cases). Sign of each component is fixed after the fit (largest-|w| element positive, N16) so outputs are reproducible across BLAS builds.
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
- **Steps** (de Jong 1993, Appendix; in T1.12b checked line by line against R `pls` `simpls.fit`, the adapted de Jong algorithm of Mevik & Wehrens 2007 — the paper itself was not at hand): 1 S = X₀ᵀY₀ · for a = 1 … A: 2 rₐ = first left singular vector of S · 3 tₐ = X₀rₐ, centre, normalise ‖tₐ‖ = 1 and divide rₐ by the same norm · 4 pₐ = X₀ᵀtₐ, qₐ = Y₀ᵀtₐ · 5 vₐ = pₐ orthogonalised against v₁ … vₐ₋₁, normalised · 6 S ← S − vₐ(vₐᵀS) · 7 B = RQᵀ.
- **State arrays** (decided, Quan 2026-11-26): same names as NIPALS — `rotations` R (t = X₀R), `scores` T (unit length, orthogonal), `loadings` P = X₀ᵀT, `y_loadings` Q = Y₀ᵀT, `coefficients` B; `weights` = R with unit-length columns (SIMPLS has no separate W; R `pls` returns R as `projection` and no `loading.weights`). With T unit length, the NIPALS formulas for explained variance, the LV sweep and VIP apply unchanged (pₐ = X₀ᵀtₐ/(tₐᵀtₐ)).
- **Edge cases.** As [PLS](#pls). If S has no covariance left (largest singular value ≤ ε·max(n, p)·‖S₀‖₂, e.g. rank(X₀) < A) the loop stops and later components stay 0 with warning "y residual is constant at iteration a" (the text scikit-learn's NIPALS uses), passed to the node log. SIMPLS works on the cross-product S, which keeps fewer digits than the deflated X of NIPALS: when the scores of the first a components deviate from orthonormal by more than 1e-6 (`T-iter`), the fit warns `BLOCK_PLS_PRECISION_LOST` (`n_components` = first such a, `max_deviation`) and drops the components from a on (set to 0, as the rank stop, so predictions for more LVs equal those for a − 1) (decided, Quan 2026-11-26). Gasoline (50 × 401): fine at 20 LV (deviation 1e-10), lost before n_min = 49; NIPALS stays orthonormal there.
- **Reference values.** PLS1: identical predictions to NIPALS (de Jong 1993) — gasoline values of Mevik & Wehrens 2007 (`T-pub`) and NIPALS (`T-iter`). PLS2: de Jong's criterion solved directly (rₐ maximises ‖Y₀ᵀX₀r‖ with ‖r‖ = 1 and X₀r orthogonal to t₁ … tₐ₋₁: top eigenvector on the null space of the constraints), predictions for a = 1 … 6 (`T-iter`); full rank = least squares. R `pls` 2.9.0 `method = "simpls"` predictions for a = 1 … 5 on R `oliveoil` (raw Y, centring only; `testdata/expected/r_pls_reference.json`, `T-iter`).
- **Implementation.** Own code (≈ 40 lines of NumPy; T1.12b repeated the §12 search: scikit-learn has NIPALS only; `mbpls` and `pyls` carry SIMPLS inside multiblock / neuroimaging packages, `pyls` not on PyPI).
- **Reference.** `dejong1993simpls`.

<a id="vip"></a>
### Variable Importance in Projection (VIP) · T1.12b
- **Definition.** Weighted sum of squared weights per variable, each component weighted by the Y variance it explains.
- **Formula.** SSₐ = (tₐᵀtₐ) Σ_m q_{ma}² (sum over the k Y columns; PLS1: k = 1). VIPⱼ = √( p Σₐ SSₐ (wⱼₐ / ‖wₐ‖)² / Σₐ SSₐ ).
- **Steps.** 1 SSₐ from T and Q · 2 normalised weights · 3 weighted sum · 4 scale by p and take the square root.
- **Edge cases.** PLS2 (Q9): VIP depends on the relative scaling of the Y columns (documented in the block tooltip). The "VIP > 1" rule of thumb is a display threshold, not part of the method.
- **Reference values.** Properties: Σⱼ VIPⱼ² = p (`T-exact`, PLS1 and PLS2, both algorithms); A = 1 → VIPⱼ = √p·|w̃ⱼ| (hand calculation); A = 2 from NIPALS by hand (`T-exact`); PLS2 with two identical Y columns = PLS1 (`T-iter`). Other software (`testdata/expected/r_pls_reference.json`, `T-iter`): R `plsVarSel` 0.10.0 `VIP` on NIPALS PLS1, gasoline rows 1–50, A = 1 … 5; `mixOmics` 6.38.0 `vip` on NIPALS PLS2, R `oliveoil` autoscaled Y, A = 1 … 5. VIP of SIMPLS models stays provisional: it follows MATLAB `plsregress`, which has no R equivalent (RISKS.md). No pengoo regression test: `pengoo/` is not in the repository, so CI cannot run one.
- **Tolerance.** `T-exact` for properties; `T-iter` against other software.
- **Implementation.** Port of pengoo `calculate_vip` (already sums over Y columns) as `vibechem_core.blocks.model.pls.vip(state, n_lv=None)`: VIP from the first `n_lv` components of the fitted state (default all, so a `search_max` fit gives VIP at the chosen LV count); uses the state's `weights` — NIPALS W, SIMPLS R with unit columns (decided, Quan 2026-11-26; the convention of MATLAB `plsregress`, which computes VIP from its normalised SIMPLS weights). So for PLS1 the VIP of a SIMPLS model differs from the VIP of a NIPALS model, although the predictions are the same. Computed on demand, not stored.
- **Reference.** `wold1993vip`, `chong2005vip`, `mehmood2012review`.

---

<a id="plsda"></a>
## 7. PLS-DA (`model.plsda`) · T1.13
- **Definition.** PLS2 on a dummy-coded class matrix; a sample is assigned to the class with the largest predicted value.
- **Formula.** Classes sorted by label c₁ … c_G; Y = n × G indicator matrix (yᵢg = 1 if sample i is in class g, else 0); fit PLS (mean-centred X and Y, no Y scaling); ĉᵢ = argmax_g ŷᵢg.
- **Steps.** `fit`: 1 sorted class list · 2 indicator matrix · 3 PLS2 fit. `apply`: 4 predicted indicator values · 5 argmax (ties → lowest class index).
- **Decision rule.** Max rule only in T1.13. Binary case: two indicator columns; because rows of Ŷ sum to 1 (centred PLS with an intercept preserves the constant row sum), the max rule equals "ŷ of class 2 > 0.5". Threshold, LDA-on-scores and probabilistic rules are later options.
- **Outputs.** Predicted class, the G predicted values (used for ROC), PLS outputs.
- **Edge cases.** Only one class in the training rows → node error `BLOCK_CONSTANT_RESPONSE` (a constant response, N13). A class missing from a training fold: its column is constant in that fold → that class cannot be predicted; logged as a warning per fold. Unknown class at apply time is impossible (labels come from the training set).
- **Reference values.** Hand-worked binary example (4 samples, 2 variables, A = 1); property: row sums of Ŷ = 1 (`T-exact`); multi-class property tests; loose published check on `olive_oil_ftir` (leave-one-oil-out CV accuracy ≥ 0.90 at the LV count `validate.cv` chooses on the indicator PRESS, N29, from 20 searched; `testdata/expected/olive_oil_ftir_classification.json`, protocol unverified; choosing the LV count on the same CV is optimistic, nested CV in T2.10d).
- **Implementation.** Our PLS block (NIPALS, `scale = false`) on a G-column indicator matrix built with NumPy (`np.unique` + `np.eye`; scikit-learn `LabelBinarizer` gives one column for two classes, so it is not used). Parameters `n_components`, `n_components_mode` as [PLS](#pls). Predictions table: `row_index`, `sample_id`, `class_pred`, `score_<class>` (DATA_MODEL.md §4.2 `Results`). The block only sees the training rows, so its class list never has an empty class; the per-fold "class missing from a training fold" warning needs the full class list and belongs to the CV loop (engine, Phase 2).
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
| SEP | √( Σ (eᵢ − ē)² / (n − 1) ) | bias-corrected SD of residuals; ISO 12099 §6.5, `fearn2002sep` |
| R² (R²c, R²cv, R²p) | 1 − Σ eᵢ² / Σ (yᵢ − ȳ)² , ȳ = mean of y **in the same set** | not the squared correlation; can be negative on test data |
| Slope, intercept | least squares y = a + b·ŷ | reference on prediction, ISO 12099:2010 §5.4.1 (N7) |
| RPD | SD(y) / RMSE of the same set (RPDc = SD/RMSEC, RPDcv = SD/RMSECV, RPDp = SD/RMSEP), SD with ddof 1 over the same set | N8 (RMSE denominator); original paper `fearn2002sep` |
| RPIQ | (Q3 − Q1) / RMSE of the same set, quartiles of y in the same set (linear interpolation, NumPy default) | N8 (RMSE denominator); original paper `bellonmaurel2010rpiq` |
| PRESS / RSS | Σ eᵢ² — `press` over the out-of-fold predictions; `rss_c`, `rss_p` over calibration and test predictions | N15 |
- **Reference values.** Every metric: hand calculation on a 5-sample example (Done when of T1.14), written out in the test file. Identity (property): RMSE² = ē² + SEP²·(n − 1)/n (`T-exact`).
- **Edge cases.** n < 2 → SEP, slope, R², RPD, RPIQ are undefined: returned as NaN with a warning (metrics are reported, not block inputs). SD(y) = 0 → R², RPD, RPIQ NaN with a warning; RMSE = 0 (perfect fit) → RPD, RPIQ NaN with a warning (T1.14; "constant" means all values equal, not a zero sum of squares, which rounding can miss). ISO 12099 asks for ≥ 20 validation samples for SEP and ≥ 10 for bias: below that, a warning (not an error).
- **Names in `Results.metrics`** (DATA_MODEL.md §4.2 takes them from here, N15): every metric for every available set — `rmsec/rmsecv/rmsep`, `r2c/r2cv/r2p`, `sec/secv/sep`, `bias_c/bias_cv/bias_p`, `slope_c/slope_cv/slope_p`, `intercept_c/intercept_cv/intercept_p`, `rpd_c/rpd_cv/rpd_p`, `rpiq_c/rpiq_cv/rpiq_p`, `rss_c/press/rss_p`; `n_lv` is the LV count. A set that was not computed is absent (not NaN). The SE column of the table above is SEC, SECV or SEP by set.
- **Expected calibration values.** A PLS model with an intercept has bias_c ≈ 0 and slope_c ≈ 1 by construction; the help text says so (they are stored anyway).
- **Implementation.** Own NumPy (each metric is one line), scikit-learn `r2_score` as a `T-lib` cross-check. Port of pengoo `regression_metrics` definitions plus RPIQ and slope.
- **Reference.** `iso12099_2010`, `fearn2002sep`, `bellonmaurel2010rpiq`, `martens1989`.

<a id="rmsecv"></a>
### RMSECV aggregation
- **`pooled`** (default, Q6): RMSECV = √( PRESS / n ), PRESS over all out-of-fold predictions (each row predicted once per repeat). Same as R `pls` `RMSEP(…, estimate = "CV")` (gasoline reference).
- **`fold_mean`** (option): RMSECV = (1/k) Σ_f RMSE_f, RMSE_f over the rows of fold f. Unequal fold sizes make it differ from pooled.
- **Always stored:** RMSE_f per fold, their SD (ddof 1) and SE = SD/√k, so the 1-SE and paired t-test LV rules (T2.10a) work with either default.
- **Repeated CV:** per repeat, then mean and SD over repeats (N9).
- **Bias, R², SECV, slope, intercept, RPD, RPIQ in CV** use the pooled out-of-fold predictions in both modes (as pengoo); RPDcv and RPIQcv divide by the reported RMSECV.
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
- **Names in `Results.metrics`** *(proposed T2.10a, N22, N27)*: per set c/cv/p always `accuracy_*`, macro means `sensitivity_*`, `specificity_*`, `auc_*`, class-size-weighted means `sensitivity_w_*`, `specificity_w_*`, `auc_w_*` (weight n_g/n; a class absent from the set has weight 0 and drops out of the weighted sums, its macro terms are NaN), and `class_ratio_*` (largest / smallest true class count); per-class sensitivity and specificity in `details.per_class`. With `micro_metrics` = true (default false) also `sensitivity_micro_*`, `specificity_micro_*`, `auc_micro_*` (pooled one-vs-rest counts or scores; single-label micro sensitivity = accuracy). `class_ratio` > `severe_imbalance_ratio` (default 20) → warning `METRIC_CLASSES_SEVERELY_UNBALANCED` (`params.ratio`, `params.threshold`, `params.set`). Computed from T2.10b (`vibechem_core.metrics.classification_metrics`; binary: the class-2 AUC is the AUC of both classes, because class 1 against class 2 on −score₂ is the same ROC; reference values: hand-worked 3-class example with one-hot scores, `T-exact`).
- **Reference.** `fawcett2006roc`, `ballabio2013plsda`, `fernandez2008imbalanced` (imbalance ratio, N27).

---

## 9. Validation
*DRAFT (T2.10a): new entries, Quan corrects and approves; choices N17–N27 in §0. T2.10b adds PLS2 and PLS-DA (N28, N29, for Quan). T2.10c adds the preprocessing grid search (N30, for Quan; N31 decided by Quan). T2.10d adds nested CV (N32, for Quan).*

<a id="cv"></a>
### Cross-validation (`validate.cv`) · T2.10a, T2.10b
- **Definition.** For each fold f of each repeat r of the input `Folds`, the subgraph feeding the `model` input is re-fitted on the fold's training rows (compiler fold plan, DATA_MODEL.md §4.6) and the fold's PLS or PLS-DA model predicts the fold's validation rows for every LV count a = 0 … A ([LV sweep](#pls-lv-sweep)); PLS-DA predicts the indicator values. The out-of-fold predictions of one repeat are one CV set.
- **Steps.** 1 per fold: LV sweep of the fold model on its validation rows (rows taken by `row_index`) · 2 per repeat: one out-of-fold prediction for every row of the `Folds` (N23) · 3 per repeat and LV count: PRESS_r(a), RMSECV_r(a) with the chosen [aggregation](#rmsecv), RMSE_f(a) per fold (PLS2 and PLS-DA: over all k columns in the fitted space, N28, N29) · 4 curve: RMSECV(a) and PRESS(a) = mean over repeats; SD (ddof 1) and SE = SD/√(r·k) of the r·k fold RMSEs (N19); squared residual ē_i(a)² of each row = mean over repeats (N26; every repeat must predict the same rows, else `VALIDATION_FOLDS_INVALID` `missing_prediction`) · 5 choose n_lv with the [LV rule](#lv-rules) · 6 §8 CV metrics at n_lv per repeat, then the mean over repeats (N9): PLS1 the regression names, PLS2 per column (N28), PLS-DA the classification names (N22, N27, N29) · 7 `model` output: the input model (fitted on all training rows) cut to its first n_lv components, B = R Q′ rebuilt from them; components are fitted one after another, so this equals a refit at n_lv ([LV sweep](#pls-lv-sweep)) *(T2.10b)*.
- **Parameters.** `aggregation` ∈ {`pooled`, `fold_mean`}, default `pooled` (Q6) · `lv_rule` ∈ {`global_min`, `one_se`, `ttest`, `wold`, `haaland_thomas`, `van_der_voet`}, default `global_min` (N18) · `alpha` 0.05 (`ttest`, N20) · `wold_threshold` 0.95 (`wold`, N21) · `f_alpha` 0.25 (`haaland_thomas`, N25) · `randomisation_alpha` 0.05 and `n_randomisations` 1000 (`van_der_voet`, N26; the signs come from a seed drawn from the run's Generator, recorded as `details.randomisation_seed`, `null` for other rules) · `micro_metrics` false and `severe_imbalance_ratio` 20 (PLS-DA, N22, N27) · `y_variance_ratio` 10 (unscaled PLS2, N28).
- **Outputs.** `results: Results`, `kind = cv`: `metrics` = the §8 CV names at n_lv plus `n_lv`; `predictions` = `row_index`, `sample_id`, `fold`, `repeat`, `y_true_<col>`, `y_pred_<col>` at n_lv (PLS-DA: `class_true`, `class_pred`, `score_<class>`); `details` = `lv` (0 … A), `rmsecv`, `press`, `rmsecv_fold_sd`, `rmsecv_fold_se` (one value per a), `rmsecv_repeat_sd` (SD over repeats at n_lv, NaN for one repeat), `n_lv_global_min`, `lv_rule`, `randomisation_seed`, `aggregation`; PLS2 `per_column`, PLS-DA `per_class` and `error_rate` (N28, N29). `y_unit` = the Y unit when all columns share one, else null (PLS-DA null). `model: Model` = the step-7 model at n_lv (`n_components` = n_lv) *(T2.10b)*. Reference value: its predictions equal scikit-learn `PLSRegression(n_components = n_lv)` fitted on all rows (`T-lib`).
- **Edge cases.** A = smallest fitted component count over the folds (N24). A row predicted twice or never in a repeat → `VALIDATION_FOLDS_INVALID` (N23; also a hold-out `Folds`, whose validation rows are only the test rows: use the test-set block). `Folds` with `groups_respected = false` → warning `VALIDATION_GROUPS_IGNORED` (N10, `params.n_groups`; R25, R41). PLS-DA validation rows without classes → `BLOCK_INPUT_REQUIREMENT_MISSING` (`requirement` = `classes`). A class absent from a fold's training rows → `VALIDATION_CLASS_MISSING_IN_FOLD` (N29). Unscaled PLS2 with very different Y variances → `VALIDATION_Y_SCALES_DIFFER` (N28). The metrics at n_lv come from the same folds that chose n_lv, so they are optimistic (selection bias); an unbiased estimate needs nested CV (T2.10d). PLS2 with `scale` or `y_transform`: `rmsecv`/`press` are in fitted units, so `y_unit` is null; per-column values in `details.per_column` stay in Y units. PLS-DA max rule with a class absent from a fold's training rows: its predicted value 0 can be the largest, so that fold can predict the class it never saw (the same value a model whose indicator column was all 0 gives).
- **Reference values.** `gasoline_nir` rows 1–50 with leave-one-out: RMSECV for 1–10 LV = Mevik & Wehrens 2007 (`rmsep_cv` in `testdata/expected/gasoline_nir_pls.json`, `T-pub`). 5-fold contiguous blocks: RMSECV curve = a hand-written scikit-learn `KFold` + `PLSRegression(scale=False)` loop (`T-lib`). Hand case for repeats and per-fold SD/SE (`T-exact`). Runner on a dataset whose `row_index` is offset from its positions and unsorted. PLS2 (scaled and unscaled) curve = a hand-written scikit-learn loop with the residuals divided by each fold's training Y SD (`T-iter`). PLS-DA: indicator PRESS, error rate and the N22 metrics = a hand-written scikit-learn loop with `accuracy_score`, `recall_score`, `roc_auc_score` (`T-iter`).
- **Implementation.** Block `validate.cv` (core) computes steps 1–7 from the per-fold states and validation spectra the engine runner hands it (`vibechem_engine.runners`); the fold loop is our compiler and scheduler (TECH_STACK.md §11.2: pengoo `calculate_cv_rmse` aggregation ported, loop ours).
- **Reference.** `stone1974cv`, `martens1989`, `mevik2007pls`.

<a id="lv-rules"></a>
### LV-number rules (`vibechem_core.lv_rules`) · T2.10a
Inputs: the CV curve RMSECV(a) and PRESS(a) for a = 0 … A, the fold RMSEs RMSE_f(a) of all K = r·k folds (every LV count scored on the same folds) and, for `haaland_thomas` and `van_der_voet`, the squared out-of-fold residual ē_i(a)² of each of the n rows (mean over repeats). Candidates a = 1 … A (N17).
| Rule | Choice |
|---|---|
| `global_min` | a* = argmin over a ≥ 1 of RMSECV(a); ties → smallest a |
| `one_se` | threshold = RMSECV(a*) + SE(a*), SE(a) = SD(RMSE_f(a), ddof 1)/√K; the smallest a ≥ 1 with RMSECV(a) ≤ threshold |
| `ttest` | a = 1; while a < A: two-sided paired t-test of RMSE_f(a) against RMSE_f(a + 1) over the K folds; p < α and RMSECV(a + 1) < RMSECV(a) → a + 1, else stop. K < 2 or all differences 0: not significant; all differences equal and non-zero: t is infinite, p = 0 |
| `wold` | R(a) = PRESS(a)/PRESS(a − 1) for a = 2 … A; the first a with R(a) ≥ threshold gives a − 1; none → A; PRESS(a − 1) = 0 → a − 1 |
| `haaland_thomas` | a_min = argmin_{a ≥ 1} PRESS(a) (ties → smallest a); the smallest a ≤ a_min with P(F_{n,n} ≥ PRESS(a)/PRESS(a_min)) > α (N25); PRESS(a_min) = 0 → a_min |
| `van_der_voet` | a_min as above; the smallest a < a_min whose randomisation p (N26) > α, else a_min |
- **Edge cases.** No candidate (A = 0) or a non-finite curve value → `ValueError` (the CV block never passes either). `one_se` and `ttest` need K ≥ 2. `haaland_thomas` and `van_der_voet` without row residuals, or `van_der_voet` without a Generator → `ValueError`. `van_der_voet` with all d_i = 0: every T*_b = T, p ≈ 1, not significant. Both rules take a_min from PRESS, so with `aggregation` = `fold_mean` a_min can differ from `n_lv_global_min` (the RMSECV argmin).
- **Reference values.** Hand-built curves per rule, each decision worked out in the test; for `ttest` the t statistic d̄/(s_d/√K) by hand (`T-exact`), p from SciPy (`T-lib`). `haaland_thomas`: for F(n, n) with n = 2 the tail has the closed form P(F ≥ x) = 1/(1 + x) (`T-exact`). `van_der_voet`: exact sign-flip p over all 2^n sign vectors for n = 10 (enumerated in the test), Monte Carlo p within 4·√(p(1 − p)/B) of it (Monte Carlo error, tolerance stated in the test, no class of §1); fixed Generator seed gives the same choice twice.
- **Library differences.** pengoo rejects `1se`/`ttest` with pooled RMSECV; here the fold RMSEs are always kept, so every rule works with both aggregations (#rmsecv). pengoo's α is fixed at 0.05; its Wold ratio adds 1e-12 to the denominator (here: the explicit zero rule).
- **Implementation.** Port of pengoo `select_n_components` and `_wold_r_criterion` (TECH_STACK.md §11.2); SciPy `ttest_rel` and `scipy.stats.f.sf`; the randomisation test is own NumPy code after R `pls` `randomiz.test` (Mevik & Wehrens 2007).
- **Reference.** `wold1978cv` (Wold R), `hastie2009esl` §7.10 (one-standard-error rule), `haaland1988pls` (F-test), `vandervoet1994` and `mevik2007pls` (randomisation test); `ttest`: pengoo rule (Quan), no paper (N20).

<a id="grid-search"></a>
### Preprocessing grid search (`validate.grid_search`) · T2.10c
*DRAFT (T2.10c): new entry, Quan corrects and approves; choices N30, N31 in §0.*
- **Definition.** Every candidate preprocessing chain of the `search_space` parameter is cross-validated exactly as `validate.cv` would cross-validate a pipeline with that chain wired between the node feeding the model block's first input and the model block: the same model block and parameters, the same `Folds` for every candidate (shared folds), the same CV parameters and LV rule ([cross-validation](#cv)). The search reports one row per candidate and the best candidate.
- **`search_space`.** Ordered slots; each slot is a list of options; an option is `null` (skip the slot) or `{"block_id", "params"}` of a registered block whose first input is `Spectra`, whose other inputs are optional, and which has a `Spectra` output (preprocessing, scaling; fitted blocks are re-fitted per fold like any block in the refit subgraph). Example: `[[null, {"block_id": "preprocess.snv"}], [null, {"block_id": "preprocess.savgol", "params": {"window": 15, "deriv": 1}}]]` gives four candidates. Default: the file `vibechem_core/blocks/validate/default_search_space.json` (scatter: none, SNV, MSC · baseline: none, detrend degree 1–3 · Savitzky–Golay: none, window 5/15/25 × derivative 1/2, polyorder 2 · scaling: none, autoscale, Pareto; 252 candidates; pengoo's fixed step order with the options our blocks have).
- **Steps.** 1 every option checked against the block registry, its parameters filled with defaults and validated · 2 candidates = the product of the slots in the order written, last slot fastest, `null` steps dropped, duplicates removed (N30); size caps N ≤ 1000, M ≤ 1000, N·M ≤ 50000 checked (N31) · 3 per candidate: the [CV](#cv) steps 1–6 on the shared `Folds` (the engine runs each candidate as a `validate.cv` branch of the pipeline) · 4 candidates table: one row per candidate in candidate order · 5 best candidate: smallest RMSECV at its n_lv (N30).
- **Parameters.** `search_space` (above); `n_jobs` (default −10 = all cores minus 10, at least 1; N31); the [`validate.cv` parameters](#cv), applied to every candidate.
- **Outputs.** `results: Results`, `kind = search`: `candidates` = `candidate` (0 …), `chain` (canonical JSON `[{"block_id", "params"}, …]`, sorted keys, all parameters), every CV metric name of the candidates (`validate.cv` names) including `n_lv`, and `rmsecv_at_n_lv` (the N30 criterion); `metrics`, `y_unit` and `predictions` = those of the best candidate; `details` = `best` (row), `best_chain`, `n_candidates`, `criterion` (`rmsecv_at_n_lv`), `lv_rule`, `aggregation`. Warnings of the candidates' CV nodes are reported once each on the search node. No `model` output: the best chain's fitted preprocessing states are not kept as a `Model`, and a PLS state alone cannot predict raw spectra; the user wires the blocks of `details.best_chain` on the canvas and runs `validate.cv` on them. Options: (a) none in v1, (b) a bundled chain + PLS `Model`, (c) the UI builds the chain as nodes; revisited with the UI (N30).
- **Edge cases.** Unknown `block_id`, a block that is not a Spectra step, or invalid option parameters → `BLOCK_PARAM_INVALID` on the search node (`param_id` = `search_space`, `reason` `unknown_block` / `not_a_spectra_step` / the option's own reason, `slot`, `option`, `value` = the block id or the option's parameter id). A candidate that fails (e.g. a step's run-time error) fails the run; the error is reported on its branch and on the search node. A search above the N31 caps → `BLOCK_PARAM_INVALID` (`too_many_candidates`, `too_many_lv`, `search_too_large`) before anything runs; above the serial limit (N·M > 1000) with one worker → `serial_too_large`, with several → warning `VALIDATION_SEARCH_PARALLEL_ONLY`. A structurally invalid `search_space` (not a non-empty list of non-empty slots of `null` or `{"block_id", "params"}`) → `BLOCK_PARAM_INVALID` reason `type`. The chain with every slot `null` is a candidate (the model on the unprocessed stream). The best candidate's metrics are optimistic (selection bias, N30); use nested CV (T2.10d) for an unbiased estimate.
- **Reference values.** Gasoline rows 1–50, 5-fold contiguous blocks, PLS (8 LV), `one_se`: every candidate's `details` and metrics equal a separate `validate.cv` run of a pipeline with that chain (`T-exact`: the same computation). Candidate order and deduplication by hand (SNV in two slots, Savitzky–Golay with defaults written out and left out). Best and the candidates table on hand-made `Results` (`T-exact`). Caps at and one above each limit; `n_jobs` clamp by hand (`T-exact`).
- **Implementation.** Core block `validate.grid_search` (`candidate_chains`, steps 1–2; `apply`, steps 4–5); engine `vibechem_engine.runners.search.expand_search` adds one branch per candidate to the pipeline document, which is compiled again (fold plans, leakage rules), and the runner hands the branches' `Results` to the search node (step 3). Ordering and deduplication follow pengoo `grid_search.py` (`generate_all_method_combinations_optimized`, `_step_identity`; logic only, TECH_STACK.md §11.2); the product is stdlib `itertools.product` (scikit-learn `ParameterGrid` sorts its keys as text and would reorder slots ≥ 10).
- **Library differences.** pengoo fits PLS once per pipeline and fold on X preprocessed by stateless functions; fitted steps (MSC, scaling) are re-fitted per fold here (D2). pengoo's Excel pipeline list and random subsample are not in v1 (TECH_STACK.md §11.2).
- **Reference.** `engel2013preprocessing`, `stone1974cv`.

<a id="nested-cv"></a>
### Nested cross-validation (`validate.nested_cv`) · T2.10d
*DRAFT (T2.10d): new entry, Quan corrects and approves; choices in N32 (§0).*
- **Definition.** An outer CV on the node's `folds` input; on each outer fold's training rows an inner [grid search](#grid-search) tunes the preprocessing chain (`search_space`) and the LV count (the LV rule) on inner folds made by the `inner_folds` block on those rows only. The chain and model chosen by the inner search are re-fitted on the outer training rows and predict the outer validation rows at the chosen LV count. The outer metrics estimate the error of the whole tuning procedure without selection bias (N32).
- **Steps.** 1 per outer fold f: the `inner_folds` block on the outer training rows of the fold source stream (DATA_MODEL.md §4.6) · 2 per outer fold: the grid search's steps 1-5 on those inner folds ([grid search](#grid-search); with the default `search_space` one empty chain, i.e. the [CV](#cv) LV choice); its best candidate c_f and LV count a_f · 3 per outer fold: chain c_f and the model re-fitted on the outer training rows predict the outer validation rows at a_f · 4 the [CV](#cv) steps 2-3 and 6 on these out-of-fold predictions (one per row and repeat, N23; per repeat, then the mean over repeats, N9); per outer fold its inner choice.
- **Parameters.** `inner_folds` (`block_ref`: `{block_id, params}` of a fold block, default `{"block_id": "validate.kfold"}` = shuffled 5-fold) · `search_space` (as the grid search; default `[[null]]` = LVs only) · `n_jobs` (as the grid search, N31; for the inner searches) · the [`validate.cv` parameters](#cv), used by the inner searches (LV rule, `aggregation`) and by the outer metrics (`aggregation`, PLS-DA and PLS2 options).
- **Outputs.** `results: Results`, `kind = nested_cv`: `metrics` = the `validate.cv` CV metric names (no `n_lv`: it differs per fold); `predictions` = the `validate.cv` columns at each fold's a_f plus `n_lv`; `details` = `outer` (one entry per outer fold: `fold`, `repeat`, `candidate`, `chain` (canonical JSON), `n_lv`, `inner_rmsecv` = the inner RMSECV at a_f), `inner_folds`, `lv_rule`, `aggregation`, PLS2 `per_column`, PLS-DA `per_class`. Warnings of the inner searches are reported once each on the nested node. No `model` output (N32, DATA_MODEL.md §4.7 point 5).
- **Edge cases.** `inner_folds` with an unknown block, a block that is not a fold block (exactly one `Spectra` input and a `Folds` output) or invalid params → `BLOCK_PARAM_INVALID` on the nested node (`param_id` = `inner_folds`, `reason` `unknown_block` / `not_a_fold_block` / the block's own reason, `value`) before anything runs. Search-space errors and the N31 caps as in the grid search (checked on the node, and again by each inner search). An inner run that fails (e.g. too few outer training rows for the inner folds) fails the nested node with that error. A hold-out outer `Folds` → `VALIDATION_FOLDS_INVALID` as in [CV](#cv). The outer folds' chains may differ, so the outer `predictions` mix chains (`details.outer` says which). Cost: (outer folds) × (inner folds + 1) × (candidates) model fits per LV sweep.
- **Reference values.** Gasoline rows 1-50, outer 5 contiguous blocks, inner 4 contiguous blocks, PLS 1-10 LV, `global_min`: the per-fold choices (chain, LV count), the out-of-fold predictions and the outer RMSECV equal a hand-written scikit-learn nested CV (`GridSearchCV` over `Pipeline(passthrough | SNV, PLSRegression(scale=False))` with `neg_mean_squared_error` on the inner splits, refit on the outer training rows; equal inner folds, so the mean fold MSE ranks like the pooled RMSECV), with and without SNV in the search space (`T-lib`). Each fold's predictions at its own LV count = scikit-learn `PLSRegression(n_components = a_f)` fitted on the fold's training rows (`T-lib`).
- **Implementation.** Core block `validate.nested_cv` (step 4, on `validate.cv` `cross_validate` with per-fold LV counts); engine `vibechem_engine.runners`: the node is expanded like a grid search (one `validate.cv` branch per candidate on the outer folds); after the top-level stage a sub-run of `runners.nested.inner_pipeline` per outer fold (the nodes upstream of the model, the `inner_folds` node on the fold source stream, a `validate.grid_search` node; sources = the outer training rows, so the compiler's fold plans and leakage rules apply to every inner run) gives the choice (steps 1-2); then only the chosen branch's fold tasks run for that outer fold (step 3). scikit-learn's nested CV is used only as the test reference.
- **Reference.** `varma2006bias`, `filzmoser2009repeated`, `stone1974cv`.

# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/blocks/validate/cv.py
"""
Block:          Cross-validation of a PLS or PLS-DA model, with LV-number choice
Class:          validate
Ports:          in  -> model : Model (refit_per_fold)
                in  -> folds : Folds
                out -> results : Results
                out -> model   : Model (the input model at the chosen LV count)
Reference:      Stone (1974), J. R. Stat. Soc. B 36, 111-147; Martens & Naes (1989),
                Multivariate Calibration; Mevik & Wehrens (2007), J. Stat. Softw. 18(2)
METHODS:        docs/METHODS.md#cv, #lv-rules, #rmsecv, #classification-metrics
Implementation: own NumPy code on core ``predict_sweep``, ``cv_metrics``,
                ``classification_metrics`` and ``lv_rules`` (pengoo ``calculate_cv_rmse``
                aggregation, TECH_STACK.md §11.2)
Fitted:         No (the engine re-fits the model's subgraph per fold)
Reviewer:       Quan

The engine runner re-fits the subgraph feeding ``model`` on every fold's training rows
and calls ``apply`` with ``fold_runs``: per fold, the fold's model state and the model's
input on the fold's validation rows (taken by ``row_index``). ``model`` itself is the
model fitted on all training rows; the ``model`` output is it cut to the chosen LV count
(:func:`~vibechem_core.blocks.model.pls.truncate`). PLS2 and PLS-DA (a PLS2 on the class
indicator matrix) choose the LV count on the PRESS summed over the Y columns in the space
the model was fitted in (METHODS.md N28, N29).
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray

from vibechem_core.block import BLOCK_INPUT_REQUIREMENT_MISSING, Block, Param, State, port
from vibechem_core.blocks.model.pls import predict_sweep, truncate
from vibechem_core.data import Fold, FoldSet, Results, SpectralDataset
from vibechem_core.errors import BlockInputError, VibeChemWarning
from vibechem_core.lv_rules import LV_RULES, fold_sd_se, select_lv
from vibechem_core.metrics import classification_metrics, cv_metrics

# Node error: a row is predicted twice or never in one repeat (``reason``, ``repeat``).
VALIDATION_FOLDS_INVALID = "VALIDATION_FOLDS_INVALID"
# Warning: the folds split groups (replicates) across training and validation (``n_groups``).
VALIDATION_GROUPS_IGNORED = "VALIDATION_GROUPS_IGNORED"
# Warning: a class of the model is absent from a fold's training rows (``class``, ``fold``, ``repeat``).
VALIDATION_CLASS_MISSING_IN_FOLD = "VALIDATION_CLASS_MISSING_IN_FOLD"
# Warning: unscaled PLS2 whose Y column variances differ more than ``threshold`` (``ratio``).
VALIDATION_Y_SCALES_DIFFER = "VALIDATION_Y_SCALES_DIFFER"


@dataclass(frozen=True)
class FoldRun:
    """One fold's model (fitted on ``fold.train``) and its input on ``fold.validation``."""

    fold: Fold
    state: State
    validation: SpectralDataset


@dataclass(frozen=True)
class CVParams:
    aggregation: str = Param("pooled", choices=("pooled", "fold_mean"))
    lv_rule: str = Param("global_min", choices=LV_RULES)
    alpha: float = Param(0.05, min=1e-6, max=0.5, visible_if=("lv_rule", ("ttest",)))
    wold_threshold: float = Param(0.95, min=0.5, max=1.0, visible_if=("lv_rule", ("wold",)))
    f_alpha: float = Param(0.25, min=1e-6, max=0.5, visible_if=("lv_rule", ("haaland_thomas",)))
    randomisation_alpha: float = Param(
        0.05, min=1e-6, max=0.5, visible_if=("lv_rule", ("van_der_voet",))
    )
    n_randomisations: int = Param(
        1000, min=99, max=100000, visible_if=("lv_rule", ("van_der_voet",))
    )
    micro_metrics: bool = Param(False, advanced=True)
    severe_imbalance_ratio: float = Param(20.0, min=1.0, advanced=True)
    y_variance_ratio: float = Param(10.0, min=1.0, advanced=True)


class CrossValidation(Block):
    block_id = "validate.cv"
    version = "1.1.0"
    icon = "glyph-cv"
    references = (
        "stone1974cv",
        "martens1989",
        "mevik2007pls",
        "wold1978cv",
        "hastie2009esl",
        "haaland1988pls",
        "vandervoet1994",
        "fawcett2006roc",
        "ballabio2013plsda",
        "fernandez2008imbalanced",
    )
    fitted = False
    inputs = (port("model", "Model", refit_per_fold=True), port("folds", "Folds"))
    outputs = (port("results", "Results"), port("model", "Model"))
    params_type = CVParams

    def apply(
        self,
        model: State,
        folds: FoldSet,
        params: CVParams,
        fold_runs: Sequence[FoldRun],
        rng: np.random.Generator | None = None,
    ) -> dict[str, Results | State]:
        results = cross_validate(model, folds, params, fold_runs, rng)
        # Step 7: the model fitted on all training rows, cut to n_lv components (= a refit)
        return {"results": results, "model": truncate(model, int(results.metrics["n_lv"]))}


def cross_validate(
    model: State,
    folds: FoldSet,
    params: CVParams,
    fold_runs: Sequence[FoldRun],
    rng: np.random.Generator | None = None,
    n_lv_per_fold: Sequence[int] | None = None,
) -> Results:
    """Steps 1-6 of METHODS.md#cv (the ``validate.cv`` results).

    With ``n_lv_per_fold`` (nested CV, METHODS.md#nested-cv) every fold predicts at its
    own given LV count and no LV count is chosen: the curve has the one entry ``lv`` 0
    (the given counts), ``metrics.n_lv`` is 0 and ``n_lv_global_min`` is ``None``.
    """
    classes = cast(list[str] | None, model.values.get("classes"))
    columns = cast(list[str], model.values["y_columns"])
    k = len(columns)
    if [(r.fold.fold, r.fold.repeat) for r in fold_runs] != [
        (f.fold, f.repeat) for f in folds.folds
    ]:
        raise ValueError("fold_runs must follow folds.folds")
    if not folds.groups_respected:
        groups = {g for r in fold_runs for g in (r.validation.group_ids or ())}
        warnings.warn(
            VibeChemWarning(VALIDATION_GROUPS_IGNORED, {"n_groups": len(groups)}), stacklevel=2
        )

    # Step 1: LV sweep of every fold model on its validation rows; A = the smallest
    # fitted LV count over the folds (N24); PLS-DA: a class absent from a fold's
    # training rows has indicator 0 there, so its predicted value is 0 (N29)
    sweeps = [_sweep(r, classes) for r in fold_runs]
    if n_lv_per_fold is not None:
        if any(not 1 <= n < len(s) for s, n in zip(sweeps, n_lv_per_fold, strict=True)):
            raise ValueError("n_lv_per_fold must be between 1 and each fold's LV count")
        sweeps = [s[n : n + 1] for s, n in zip(sweeps, n_lv_per_fold, strict=True)]
    n_lv_max = min(len(s) for s in sweeps) - 1
    y_true = [_truth(r.validation, classes) for r in fold_runs]
    # Residuals in the space the fold model was fitted in (N28); PLS1 keeps Y units and
    # PLS-DA fits the raw indicator matrix
    space = [_fit_scale(r.state) if k > 1 and classes is None else np.ones(k) for r in fold_runs]
    errors = [
        (s[: n_lv_max + 1] - y) / c for s, y, c in zip(sweeps, y_true, space, strict=True)
    ]  # (A+1, n_f, k)

    # Step 2: one out-of-fold prediction for every row of the folds, per repeat (N23)
    repeats = sorted({r.fold.repeat for r in fold_runs})
    members = {rep: [i for i, r in enumerate(fold_runs) if r.fold.repeat == rep] for rep in repeats}
    first_rows: NDArray[np.int64] | None = None
    for rep, idx in members.items():
        rows = np.concatenate([fold_runs[i].validation.row_index for i in idx])
        if np.unique(rows).size != rows.size:
            raise BlockInputError(
                VALIDATION_FOLDS_INVALID, {"reason": "duplicate_prediction", "repeat": rep}
            )
        rows = np.sort(rows)
        if rows.size != folds.n_samples or (
            first_rows is not None and not np.array_equal(rows, first_rows)
        ):
            raise BlockInputError(
                VALIDATION_FOLDS_INVALID, {"reason": "missing_prediction", "repeat": rep}
            )
        first_rows = rows

    # Step 3: per repeat and LV count: PRESS, RMSECV (pooled or fold mean), fold RMSEs;
    # sums and means run over the rows and the k Y columns (N28)
    fold_rmse = np.stack([np.sqrt((e**2).mean(axis=(1, 2))) for e in errors], axis=1)
    press_r: list[NDArray[np.float64]] = []
    rmsecv_r: list[NDArray[np.float64]] = []
    row_sq_r: list[NDArray[np.float64]] = []  # (A+1, n) in row_index order
    for idx in members.values():
        e = np.concatenate([errors[i] for i in idx], axis=1)
        order = np.argsort(np.concatenate([fold_runs[i].validation.row_index for i in idx]))
        row_sq_r.append((e[:, order] ** 2).sum(axis=2))
        press_r.append((e**2).sum(axis=(1, 2)))
        if params.aggregation == "pooled":
            rmsecv_r.append(np.sqrt((e**2).mean(axis=(1, 2))))
        else:
            rmsecv_r.append(fold_rmse[:, idx].mean(axis=1))

    # Step 4: curve = mean over repeats; SD and SE of the r*k fold RMSEs (N19); squared
    # residual of each row, mean over repeats (N26)
    rmsecv = np.mean(rmsecv_r, axis=0)
    press = np.mean(press_r, axis=0)
    row_sq_err = np.mean(row_sq_r, axis=0)
    fold_sd, fold_se = fold_sd_se(fold_rmse)

    # Step 5: LV count chosen by the rule; the randomisation seed is drawn from the run's
    # Generator and recorded
    seed = (
        int(rng.integers(2**32))
        if rng is not None and params.lv_rule == "van_der_voet" and n_lv_per_fold is None
        else None
    )
    n_lv = (
        0
        if n_lv_per_fold is not None
        else select_lv(
            params.lv_rule,
            rmsecv,
            press,
            fold_rmse,
            alpha=params.alpha,
            wold_threshold=params.wold_threshold,
            row_sq_err=row_sq_err,
            f_alpha=params.f_alpha,
            randomisation_alpha=params.randomisation_alpha,
            n_randomisations=params.n_randomisations,
            rng=None if seed is None else np.random.default_rng(seed),
        )
    )

    # Step 6: METHODS §8 CV metrics at n_lv per repeat, then the mean over repeats (N9):
    # PLS1 the regression names; PLS2 the curve's rmsecv/press, per column in
    # details; PLS-DA the classification names (N22, N27)
    validation = [r.validation for r in fold_runs]
    # Fitted units = Y units (no scale, or a y_transform that only centres), N28
    unscaled = k == 1 or classes is not None or bool((_fit_scale(model) == 1).all())
    fold_ids = [np.full(r.validation.n_samples, r.fold.fold) for r in fold_runs]
    details: dict[str, Any] = {}
    if classes is not None:
        metrics, details = _classification(
            fold_runs, sweeps, members, classes, n_lv, n_lv_max, params
        )
    else:
        per_column = {
            col: _mean(
                [
                    cv_metrics(
                        np.concatenate([y_true[i][:, j] for i in idx]),
                        np.concatenate([sweeps[i][n_lv][:, j] for i in idx]),
                        np.concatenate([fold_ids[i] for i in idx]),
                        cast(Any, params.aggregation),
                    )
                    for idx in members.values()
                ]
            )
            for j, col in enumerate(columns)
        }
        if k == 1:
            metrics = per_column[columns[0]]
        else:
            metrics = {"rmsecv": float(rmsecv[n_lv]), "press": float(press[n_lv])}
            details["per_column"] = per_column
            if unscaled:
                _check_y_scales(y_true, members, params.y_variance_ratio)
    at_n_lv = [float(r[n_lv]) for r in rmsecv_r]
    predictions: dict[str, NDArray[Any]] = {
        "row_index": np.concatenate([v.row_index for v in validation]),
        "sample_id": np.concatenate([np.array(v.sample_ids, dtype=np.str_) for v in validation]),
        "fold": np.concatenate(fold_ids),
        "repeat": np.concatenate([np.full(r.validation.n_samples, r.fold.repeat) for r in fold_runs]),
    }  # fmt: skip
    scores = np.concatenate([s[n_lv] for s in sweeps])
    if classes is not None:
        labels = np.asarray(classes, dtype=np.str_)
        predictions["class_true"] = np.concatenate([np.asarray(v.classes, dtype=np.str_) for v in validation])  # fmt: skip
        predictions["class_pred"] = labels[scores.argmax(axis=1)]
        predictions.update({f"score_{c}": scores[:, g] for g, c in enumerate(classes)})
    else:
        truth = np.concatenate(y_true)
        for j, col in enumerate(columns):
            predictions[f"y_true_{col}"] = truth[:, j]
            predictions[f"y_pred_{col}"] = scores[:, j]
    units: set[str] = set(validation[0].y_units or ())
    if not unscaled:
        units = set[str]()  # the PLS2 curve is in fitted (scaled) units, not in Y units (N28)
    return Results(
        kind="cv",
        metrics={**metrics, "n_lv": float(n_lv)},
        y_unit=units.pop() if classes is None and len(units) == 1 else None,
        predictions=predictions,
        details={
            "lv": list(range(n_lv_max + 1)),
            "rmsecv": rmsecv.tolist(),
            "press": press.tolist(),
            "rmsecv_fold_sd": fold_sd.tolist(),
            "rmsecv_fold_se": fold_se.tolist(),
            "rmsecv_repeat_sd": float(np.std(at_n_lv, ddof=1))
            if len(at_n_lv) > 1
            else float("nan"),
            "n_lv_global_min": None
            if n_lv_per_fold is not None
            else select_lv("global_min", rmsecv, press, fold_rmse),
            "lv_rule": params.lv_rule,
            "randomisation_seed": seed,
            "aggregation": params.aggregation,
            **details,
        },
    )


def _sweep(run: FoldRun, classes: list[str] | None) -> NDArray[np.float64]:
    sweep = predict_sweep(run.state, run.validation)
    if classes is None:
        return sweep
    fitted = cast(list[str], run.state.values["classes"])
    full = np.zeros((*sweep.shape[:2], len(classes)))
    for g, c in enumerate(classes):
        if c in fitted:
            full[:, :, g] = sweep[:, :, fitted.index(c)]
        else:
            params = {"class": c, "fold": run.fold.fold, "repeat": run.fold.repeat}
            warnings.warn(VibeChemWarning(VALIDATION_CLASS_MISSING_IN_FOLD, params), stacklevel=3)
    return full


def _truth(data: SpectralDataset, classes: list[str] | None) -> NDArray[np.float64]:
    if classes is None:
        return cast(NDArray[np.float64], data.y)
    if data.classes is None:
        raise BlockInputError(
            BLOCK_INPUT_REQUIREMENT_MISSING, {"port_id": "model", "requirement": "classes"}
        )
    return (np.asarray(data.classes)[:, None] == np.asarray(classes)[None, :]).astype(np.float64)


def _fit_scale(state: State) -> NDArray[np.float64]:
    """Per Y column: original units / fitted units (built-in ``scale``, then ``y_transform``)."""
    scale = state.arrays["y_std"]
    if state.values["y_transform"]:
        scale = scale * state.arrays["y_inverse_scale"]
    return scale


def _mean(per_repeat: list[dict[str, float]]) -> dict[str, float]:
    return {k: float(np.mean([m[k] for m in per_repeat])) for k in per_repeat[0]}


def _classification(
    fold_runs: Sequence[FoldRun],
    sweeps: list[NDArray[np.float64]],
    members: dict[int, list[int]],
    classes: list[str],
    n_lv: int,
    n_lv_max: int,
    params: CVParams,
) -> tuple[dict[str, float], dict[str, Any]]:
    labels = np.asarray(classes, dtype=np.str_)
    per_repeat: list[dict[str, float]] = []
    per_class: list[dict[str, dict[str, float]]] = []
    error_rate: list[list[float]] = []
    for r, idx in enumerate(members.values()):
        truth = np.concatenate([np.asarray(fold_runs[i].validation.classes, dtype=np.str_) for i in idx])  # fmt: skip
        sweep = np.concatenate([sweeps[i][: n_lv_max + 1] for i in idx], axis=1)  # (A+1, n, G)
        error_rate.append([float((labels[s.argmax(axis=1)] != truth).mean()) for s in sweep])
        m, pc = classification_metrics(
            truth,
            labels[sweep[n_lv].argmax(axis=1)],
            sweep[n_lv],
            labels,
            "cv",
            micro=params.micro_metrics,
            # every repeat predicts the same rows, so the class ratio is checked once
            severe_imbalance_ratio=params.severe_imbalance_ratio if r == 0 else None,
        )
        per_repeat.append(m)
        per_class.append(pc)
    return _mean(per_repeat), {
        "per_class": {
            c: {s: float(np.mean([pc[c][s] for pc in per_class])) for s in per_class[0][c]}
            for c in classes
        },
        "error_rate": np.mean(error_rate, axis=0).tolist(),
    }


def _check_y_scales(
    y_true: list[NDArray[np.float64]], members: dict[int, list[int]], threshold: float
) -> None:
    first = next(iter(members.values()))
    var = np.var(np.concatenate([y_true[i] for i in first]), axis=0, ddof=1)
    ratio = float(var.max() / var.min()) if var.min() > 0 else math.inf
    if ratio > threshold:
        warnings.warn(
            VibeChemWarning(VALIDATION_Y_SCALES_DIFFER, {"ratio": ratio, "threshold": threshold}),
            stacklevel=3,
        )

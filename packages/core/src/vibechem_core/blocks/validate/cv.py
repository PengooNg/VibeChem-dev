# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/blocks/validate/cv.py
"""
Block:          Cross-validation of a PLS regression model, with LV-number choice
Class:          validate
Ports:          in  -> model : Model (refit_per_fold)
                in  -> folds : Folds
                out -> results : Results
Reference:      Stone (1974), J. R. Stat. Soc. B 36, 111-147; Martens & Naes (1989),
                Multivariate Calibration; Mevik & Wehrens (2007), J. Stat. Softw. 18(2)
METHODS:        docs/METHODS.md#cv, #lv-rules, #rmsecv
Implementation: own NumPy code on core ``predict_sweep``, ``cv_metrics`` and
                ``lv_rules`` (pengoo ``calculate_cv_rmse`` aggregation, TECH_STACK.md §11.2)
Fitted:         No (the engine re-fits the model's subgraph per fold)
Reviewer:       Quan

The engine runner re-fits the subgraph feeding ``model`` on every fold's training rows
and calls ``apply`` with ``fold_runs``: per fold, the fold's model state and the model's
input on the fold's validation rows (taken by ``row_index``). ``model`` itself is the
model fitted on all training rows. PLS1 only (METHODS.md#cv edge cases).
"""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray

from vibechem_core.block import BLOCK_INPUT_REQUIREMENT_MISSING, Block, Param, State, port
from vibechem_core.blocks.model.pls import predict_sweep
from vibechem_core.data import Fold, FoldSet, Results, SpectralDataset
from vibechem_core.errors import BlockInputError, VibeChemWarning
from vibechem_core.lv_rules import LV_RULES, fold_sd_se, select_lv
from vibechem_core.metrics import cv_metrics

# Node error: a row is predicted twice or never in one repeat (``reason``, ``repeat``).
VALIDATION_FOLDS_INVALID = "VALIDATION_FOLDS_INVALID"
# Warning: the folds split groups (replicates) across training and validation (``n_groups``).
VALIDATION_GROUPS_IGNORED = "VALIDATION_GROUPS_IGNORED"


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


class CrossValidation(Block):
    block_id = "validate.cv"
    version = "1.0.0"
    icon = "glyph-cv"
    references = ("stone1974cv", "martens1989", "mevik2007pls", "wold1978cv", "hastie2009esl")
    fitted = False
    inputs = (port("model", "Model", refit_per_fold=True), port("folds", "Folds"))
    outputs = (port("results", "Results"),)
    params_type = CVParams

    def apply(
        self, model: State, folds: FoldSet, params: CVParams, fold_runs: Sequence[FoldRun]
    ) -> Results:
        if (
            "classes" in model.values
            or len(cast(list[str], model.values.get("y_columns", []))) != 1
        ):
            raise BlockInputError(
                BLOCK_INPUT_REQUIREMENT_MISSING,
                {"port_id": "model", "requirement": "y", "expected": "one regression column"},
            )
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
        # fitted LV count over the folds (N24)
        sweeps = [predict_sweep(r.state, r.validation)[:, :, 0] for r in fold_runs]
        n_lv_max = min(len(s) for s in sweeps) - 1
        y_true = [cast(NDArray[np.float64], r.validation.y)[:, 0] for r in fold_runs]
        errors = [s[: n_lv_max + 1] - y for s, y in zip(sweeps, y_true, strict=True)]

        # Step 2: one out-of-fold prediction for every row of the folds, per repeat (N23)
        repeats = sorted({r.fold.repeat for r in fold_runs})
        members = {
            rep: [i for i, r in enumerate(fold_runs) if r.fold.repeat == rep] for rep in repeats
        }
        for rep, idx in members.items():
            rows = np.concatenate([fold_runs[i].validation.row_index for i in idx])
            if np.unique(rows).size != rows.size:
                raise BlockInputError(
                    VALIDATION_FOLDS_INVALID, {"reason": "duplicate_prediction", "repeat": rep}
                )
            if rows.size != folds.n_samples:
                raise BlockInputError(
                    VALIDATION_FOLDS_INVALID, {"reason": "missing_prediction", "repeat": rep}
                )

        # Step 3: per repeat and LV count: PRESS, RMSECV (pooled or fold mean), fold RMSEs
        fold_rmse = np.stack([np.sqrt((e**2).mean(axis=1)) for e in errors], axis=1)  # (A+1, K)
        press_r: list[NDArray[np.float64]] = []
        rmsecv_r: list[NDArray[np.float64]] = []
        for idx in members.values():
            e = np.concatenate([errors[i] for i in idx], axis=1)
            press_r.append((e**2).sum(axis=1))
            if params.aggregation == "pooled":
                rmsecv_r.append(np.sqrt((e**2).mean(axis=1)))
            else:
                rmsecv_r.append(fold_rmse[:, idx].mean(axis=1))

        # Step 4: curve = mean over repeats; SD and SE of the r*k fold RMSEs (N19)
        rmsecv = np.mean(rmsecv_r, axis=0)
        press = np.mean(press_r, axis=0)
        fold_sd, fold_se = fold_sd_se(fold_rmse)

        # Step 5: LV count chosen by the rule
        n_lv = select_lv(
            params.lv_rule,
            rmsecv,
            press,
            fold_rmse,
            alpha=params.alpha,
            wold_threshold=params.wold_threshold,
        )

        # Step 6: METHODS §8 CV metrics at n_lv per repeat, then the mean over repeats (N9)
        per_repeat: list[dict[str, float]] = []
        for idx in members.values():
            per_repeat.append(
                cv_metrics(
                    np.concatenate([y_true[i] for i in idx]),
                    np.concatenate([sweeps[i][n_lv] for i in idx]),
                    np.concatenate([np.full(y_true[i].size, fold_runs[i].fold.fold) for i in idx]),
                    cast(Any, params.aggregation),
                )
            )
        metrics = {k: float(np.mean([m[k] for m in per_repeat])) for k in per_repeat[0]}
        at_n_lv = [float(r[n_lv]) for r in rmsecv_r]
        name = cast(list[str], model.values["y_columns"])[0]
        validation = [r.validation for r in fold_runs]
        predictions: dict[str, NDArray[Any]] = {
            "row_index": np.concatenate([v.row_index for v in validation]),
            "sample_id": np.concatenate([np.array(v.sample_ids, dtype=np.str_) for v in validation]),
            "fold": np.concatenate([np.full(r.validation.n_samples, r.fold.fold) for r in fold_runs]),
            "repeat": np.concatenate([np.full(r.validation.n_samples, r.fold.repeat) for r in fold_runs]),
            f"y_true_{name}": np.concatenate(y_true),
            f"y_pred_{name}": np.concatenate([s[n_lv] for s in sweeps]),
        }  # fmt: skip
        return Results(
            kind="cv",
            metrics={**metrics, "n_lv": float(n_lv)},
            y_unit=validation[0].y_units[0] if validation[0].y_units else None,
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
                "n_lv_global_min": select_lv("global_min", rmsecv, press, fold_rmse),
                "lv_rule": params.lv_rule,
                "aggregation": params.aggregation,
            },
        )

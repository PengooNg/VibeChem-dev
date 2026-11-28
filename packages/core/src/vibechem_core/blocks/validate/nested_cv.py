# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/blocks/validate/nested_cv.py
"""
Block:          Nested cross-validation (inner tuning of LVs and preprocessing chain)
Class:          validate
Ports:          in  -> model : Model (refit_per_fold)
                in  -> folds : Folds (the outer folds)
                out -> results : Results (kind = nested_cv)
Reference:      Stone (1974), J. R. Stat. Soc. B 36, 111-147; Varma & Simon (2006),
                BMC Bioinformatics 7, 91; Filzmoser, Liebmann & Varmuza (2009),
                J. Chemometrics 23, 160-171
METHODS:        docs/METHODS.md#nested-cv, #grid-search, #cv
Implementation: own code on ``validate.cv`` (``cross_validate``) and the grid-search
                candidates; the engine runs the inner searches and the outer folds
Fitted:         No (the engine re-fits every subgraph per inner and outer fold)
Reviewer:       Quan

The engine runner makes the ``inner_folds`` on each outer fold's training rows, runs a
``validate.grid_search`` there with this block's ``search_space`` and CV parameters
(steps 1-2), re-fits the chosen chain and model on the outer training rows and calls
``apply`` with, per outer fold, that fold run and the inner choice (steps 3-4).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from vibechem_core.block import (
    BLOCK_PARAM_INVALID,
    Block,
    Param,
    SearchOption,
    SearchSpace,
    State,
    parse_params,
    port,
)
from vibechem_core.blocks.validate.cv import FoldRun, cross_validate
from vibechem_core.blocks.validate.grid_search import GridSearchParams
from vibechem_core.data import FoldSet, Results
from vibechem_core.errors import ParamError
from vibechem_core.registry import Registry

# One empty chain: only the LV count is tuned (N32)
LV_ONLY = SearchSpace(((None,),))


@dataclass(frozen=True)
class NestedCVParams(GridSearchParams):
    search_space: SearchSpace = Param(LV_ONLY)  # noqa: RUF009 (frozen value)
    inner_folds: SearchOption = Param(SearchOption("validate.kfold"))  # noqa: RUF009 (frozen value)


@dataclass(frozen=True)
class InnerChoice:
    """What the inner search of one outer fold chose: candidate index and chain (canonical
    JSON, METHODS.md#grid-search), LV count and the inner RMSECV at that count."""

    candidate: int
    chain: str
    n_lv: int
    rmsecv: float


def check_inner_folds(ref: SearchOption, registry: Registry) -> None:
    """``ParamError`` ``BLOCK_PARAM_INVALID`` (``param_id`` ``inner_folds``) when the block
    is not registered (``unknown_block``), is not a fold block (``not_a_fold_block``:
    exactly one input, of type ``Spectra``, and a ``Folds`` output) or its params are
    invalid (their own ``reason``, the option's ``param_id`` as ``value``)."""
    where: dict[str, Any] = {"param_id": "inner_folds"}
    if ref.block_id not in registry:
        raise ParamError(BLOCK_PARAM_INVALID, {**where, "reason": "unknown_block", "value": ref.block_id})  # fmt: skip
    block = registry.get(ref.block_id)
    meta = block.metadata()
    if [p.port_type for p in meta.inputs] != ["Spectra"] or all(
        p.port_type != "Folds" for p in meta.outputs
    ):
        raise ParamError(BLOCK_PARAM_INVALID, {**where, "reason": "not_a_fold_block", "value": ref.block_id})  # fmt: skip
    try:
        parse_params(block.params_type, ref.params)
    except ParamError as exc:
        value = exc.params.get("param_id")
        reason = {**where, "reason": exc.params.get("reason")}
        raise ParamError(BLOCK_PARAM_INVALID, reason if value is None else {**reason, "value": value}) from exc  # fmt: skip


class NestedCV(Block):
    block_id = "validate.nested_cv"
    version = "1.0.0"
    icon = "glyph-nested-cv"
    references = ("stone1974cv", "varma2006bias", "filzmoser2009repeated")
    fitted = False
    inputs = (port("model", "Model", refit_per_fold=True), port("folds", "Folds"))
    outputs = (port("results", "Results"),)
    params_type = NestedCVParams

    def apply(
        self,
        model: State,
        folds: FoldSet,
        params: NestedCVParams,
        fold_runs: Sequence[FoldRun],
        choices: Sequence[InnerChoice],
    ) -> Results:
        # Step 3: every outer fold predicts its validation rows with the chain and model
        # re-fitted on its training rows, at the LV count its inner search chose; the
        # validate.cv steps 2-3 and 6 on these out-of-fold predictions (mean over repeats)
        outer = cross_validate(model, folds, params, fold_runs, n_lv_per_fold=[c.n_lv for c in choices])  # fmt: skip

        # Step 4: the outer metrics, and per outer fold its inner choice
        predictions = dict(outer.predictions or {})
        n_lv = [c.n_lv for r, c in zip(fold_runs, choices, strict=True) for _ in range(r.validation.n_samples)]  # fmt: skip
        predictions["n_lv"] = np.asarray(n_lv)
        kept = ("per_column", "per_class", "aggregation", "lv_rule")
        return Results(
            kind="nested_cv",
            metrics={k: v for k, v in outer.metrics.items() if k != "n_lv"},
            y_unit=outer.y_unit,
            predictions=predictions,
            details={
                **{k: v for k, v in outer.details.items() if k in kept},
                "outer": [
                    {
                        "fold": r.fold.fold,
                        "repeat": r.fold.repeat,
                        "candidate": c.candidate,
                        "chain": c.chain,
                        "n_lv": c.n_lv,
                        "inner_rmsecv": c.rmsecv,
                    }
                    for r, c in zip(fold_runs, choices, strict=True)
                ],
                "inner_folds": {
                    "block_id": params.inner_folds.block_id,
                    "params": dict(params.inner_folds.params),
                },
            },
        )

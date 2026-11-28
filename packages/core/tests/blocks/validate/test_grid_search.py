# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/blocks/validate/test_grid_search.py
"""``validate.grid_search`` (docs/METHODS.md#grid-search): candidate chains and the
results table; the engine run of every candidate is tested in ``packages/engine/tests/runners/``."""

from __future__ import annotations

import json
from typing import Any, cast

import numpy as np
import pytest

from vibechem_core.block import SearchOption, SearchSpace, parse_params, search_space_value
from vibechem_core.blocks.model.pls import PLS
from vibechem_core.blocks.preprocess.detrend import Detrend
from vibechem_core.blocks.preprocess.msc import MSC
from vibechem_core.blocks.preprocess.savgol import SavitzkyGolay
from vibechem_core.blocks.preprocess.scaling import Autoscale, MeanCentre, Pareto
from vibechem_core.blocks.preprocess.snv import SNV
from vibechem_core.blocks.validate.grid_search import (
    DEFAULT_SEARCH_SPACE,
    GridSearch,
    GridSearchParams,
    candidate_chains,
    chain_label,
)
from vibechem_core.data import Results
from vibechem_core.errors import ParamError
from vibechem_core.registry import Registry

REGISTRY = Registry()
for _block in (SNV, MSC, Detrend, SavitzkyGolay, Autoscale, MeanCentre, Pareto, PLS):
    REGISTRY.register(_block)

SNV_: dict[str, Any] = {"block_id": "preprocess.snv"}
SG_DEFAULT: dict[str, Any] = {"block_id": "preprocess.savgol", "params": {}}
SG_11: dict[str, Any] = {"block_id": "preprocess.savgol", "params": {"window": 11, "polyorder": 2}}
AUTO: dict[str, Any] = {"block_id": "preprocess.autoscale", "params": {}}


def space(value: Any) -> SearchSpace:
    parsed = search_space_value(value)
    assert parsed is not None
    return parsed


def ids(chains: list[tuple[SearchOption, ...]]) -> list[list[str]]:
    return [[o.block_id.split(".")[1] for o in c] for c in chains]


def test_chains_follow_the_slot_product_and_drop_duplicates() -> None:
    # SNV in two slots, and SG with its defaults written out and left out
    chains = candidate_chains(
        space([[None, SNV_], [None, SNV_, SG_DEFAULT, SG_11], [None, AUTO]]), REGISTRY
    )
    assert ids(chains) == [
        [], ["autoscale"], ["snv"], ["snv", "autoscale"], ["savgol"], ["savgol", "autoscale"],
        ["snv", "snv"], ["snv", "snv", "autoscale"], ["snv", "savgol"], ["snv", "savgol", "autoscale"],
    ]  # fmt: skip
    assert len({chain_label(c) for c in chains}) == len(chains)
    assert chains[4][0].params == {"window": 11, "polyorder": 2, "deriv": 0, "mode": "interp"}


def test_bad_options_are_param_errors_on_search_space() -> None:
    cases = [
        ({"block_id": "preprocess.nope"}, "unknown_block", "preprocess.nope"),
        ({"block_id": "model.pls"}, "not_a_spectra_step", "model.pls"),
        ({"block_id": "preprocess.savgol", "params": {"window": 4}}, "not_odd", "window"),
    ]
    for option, reason, value in cases:
        with pytest.raises(ParamError) as err:
            candidate_chains(space([[None, SNV_], [AUTO, option]]), REGISTRY)
        assert err.value.code == "BLOCK_PARAM_INVALID"
        assert dict(err.value.params) == {
            "param_id": "search_space", "reason": reason, "slot": 1, "option": 1, "value": value,
        }  # fmt: skip


BAD: list[Any] = [
    [],
    [[]],
    [SNV_],
    [[{"block_id": 3}]],
    [[{"block_id": "a.b", "extra": 1}]],
    [[{"block_id": "a.b", "params": []}]],
]


@pytest.mark.parametrize("value", BAD)
def test_malformed_search_space_is_a_type_error(value: Any) -> None:
    with pytest.raises(ParamError) as err:
        parse_params(GridSearchParams, {"search_space": value})
    assert dict(err.value.params)["reason"] == "type"


def test_default_search_space_uses_registered_blocks_only() -> None:
    chains = candidate_chains(DEFAULT_SEARCH_SPACE, REGISTRY)
    assert len(chains) == 3 * 4 * 7 * 3
    detail: dict[str, Any] = GridSearch.metadata().to_detail_dict()
    entry: dict[str, Any] = next(p for p in detail["params"] if p["param_id"] == "search_space")
    assert entry["type"] == "search_space"
    assert search_space_value(json.loads(json.dumps(entry["default"]))) == DEFAULT_SEARCH_SPACE
    assert parse_params(GridSearchParams, {}).search_space == DEFAULT_SEARCH_SPACE


def cv_result(rmsecv: list[float], n_lv: int, r2: float) -> Results:
    return Results(
        kind="cv",
        metrics={"rmsecv": rmsecv[n_lv], "r2cv": r2, "n_lv": float(n_lv)},
        y_unit="%",
        predictions={"row_index": np.arange(3)},
        details={"rmsecv": rmsecv, "lv_rule": "one_se", "aggregation": "pooled"},
    )


def test_results_table_and_best_candidate() -> None:
    chains = candidate_chains(space([[None, SNV_, AUTO]]), REGISTRY)
    # rmsecv at the chosen LV: 0.5, 0.3, 0.3 -> the first of the tied pair (candidate 1)
    runs = [cv_result([1.0, 0.5, 0.4], 1, 0.1), cv_result([1.0, 0.2, 0.3], 2, 0.2),
            cv_result([1.0, 0.3, 0.1], 1, 0.3)]  # fmt: skip
    unused = cast(Any, None)  # model and folds are not read by apply
    out = GridSearch().apply(
        unused, unused, parse_params(GridSearchParams, {}), list(zip(chains, runs, strict=True))
    )
    assert out.kind == "search"
    assert out.metrics == runs[1].metrics
    assert out.details["best"] == 1
    assert out.details["best_chain"] == chain_label(chains[1])
    assert out.candidates is not None
    assert out.candidates["rmsecv_at_n_lv"].tolist() == [0.5, 0.3, 0.3]
    assert out.candidates["n_lv"].tolist() == [1.0, 2.0, 1.0]
    assert out.candidates["chain"].tolist() == [chain_label(c) for c in chains]

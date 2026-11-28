# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/blocks/validate/grid_search.py
"""
Block:          Preprocessing grid search (cross-validation of every candidate chain)
Class:          validate
Ports:          in  -> model : Model (refit_per_fold)
                in  -> folds : Folds
                out -> results : Results (kind = search)
Reference:      Engel et al. (2013), TrAC 50, 96-106 (preprocessing chain search);
                Stone (1974), J. R. Stat. Soc. B 36, 111-147
METHODS:        docs/METHODS.md#grid-search, #cv
Implementation: own code; ordering and deduplication after pengoo ``grid_search.py``
                (fixed-order product, ``_step_identity``; TECH_STACK.md §11.2, logic only)
Fitted:         No (the engine runs every candidate as a ``validate.cv`` branch)
Reviewer:       Quan

:func:`candidate_chains` turns the ``search_space`` parameter into the candidate chains
(steps 1-2). The engine runner builds each chain between the node feeding the model
block's first input and a copy of the model block, cross-validates it with
``validate.cv`` on the search's ``folds`` (step 3) and calls ``apply`` with the
candidates and their ``Results`` (steps 4-5). The other parameters are those of
``validate.cv`` and apply to every candidate.
"""

from __future__ import annotations

import dataclasses
import itertools
import json
from collections.abc import Sequence
from dataclasses import dataclass
from importlib import resources
from typing import Any, NoReturn, cast

import numpy as np
from numpy.typing import NDArray

from vibechem_core.block import (
    BLOCK_PARAM_INVALID,
    Block,
    BlockMeta,
    JSONValue,
    Param,
    SearchOption,
    SearchSpace,
    State,
    parse_params,
    port,
    search_space_value,
)
from vibechem_core.blocks.validate.cv import CVParams
from vibechem_core.data import FoldSet, Results
from vibechem_core.errors import ErrorParam, ParamError
from vibechem_core.registry import Registry

type Chain = tuple[SearchOption, ...]


def _default_space() -> SearchSpace:
    text = resources.files(__package__).joinpath("default_search_space.json").read_text("utf-8")
    space = search_space_value(json.loads(text))
    if space is None:
        raise ValueError("default_search_space.json is not a valid search space")
    return space


DEFAULT_SEARCH_SPACE = _default_space()


@dataclass(frozen=True)
class GridSearchParams(CVParams):
    search_space: SearchSpace = Param(DEFAULT_SEARCH_SPACE)  # noqa: RUF009 (frozen value)


def spectra_output(meta: BlockMeta) -> str | None:
    """Output port a chain step passes on, or ``None`` if the block is not a step: its
    first input is ``Spectra``, every other input is optional, and it has a ``Spectra``
    output."""
    if not meta.inputs or meta.inputs[0].port_type != "Spectra":
        return None
    if any(p.required for p in meta.inputs[1:]):
        return None
    return next((p.port_id for p in meta.outputs if p.port_type == "Spectra"), None)


def candidate_chains(space: SearchSpace, registry: Registry) -> list[Chain]:
    """Steps 1-2: the candidate chains of ``space``, deduplicated, in product order.

    Raises ``ParamError`` ``BLOCK_PARAM_INVALID`` (``param_id`` = ``search_space``,
    ``slot``, ``option``) for an unknown block (``reason`` ``unknown_block``), a block
    that is not a Spectra step (``not_a_spectra_step``) or bad option params (the
    option's own ``reason``, its ``param_id`` as ``value``).
    """
    # Step 1: every option checked against the registry, params filled with defaults
    slots: list[list[SearchOption | None]] = []
    for s, slot in enumerate(space.slots):
        slots.append([])
        for o, option in enumerate(slot):
            if option is None:
                slots[-1].append(None)
                continue
            where: dict[str, int] = {"slot": s, "option": o}
            if option.block_id not in registry:
                _invalid("unknown_block", option.block_id, where)
            block = registry.get(option.block_id)
            if spectra_output(block.metadata()) is None:
                _invalid("not_a_spectra_step", option.block_id, where)
            try:
                parsed: object = parse_params(block.params_type, option.params)  # pyright: ignore[reportUnknownVariableType]
            except ParamError as exc:
                _invalid(str(exc.params.get("reason")), exc.params.get("param_id"), where)
            full = json.loads(json.dumps(dataclasses.asdict(cast(Any, parsed))))  # tuples -> lists
            slots[-1].append(SearchOption(option.block_id, cast(dict[str, JSONValue], full)))

    # Step 2: fixed-order product (last slot fastest), null steps dropped; equal chains
    # (same blocks and full params in the same order) kept once, the first one
    chains: dict[str, Chain] = {}
    for combo in itertools.product(*slots):
        chain = tuple(o for o in combo if o is not None)
        chains.setdefault(chain_label(chain), chain)
    return list(chains.values())


def chain_label(chain: Chain) -> str:
    """Canonical JSON of a chain: ``[{"block_id", "params"}, ...]`` with sorted keys."""
    steps = [{"block_id": o.block_id, "params": dict(o.params)} for o in chain]
    return json.dumps(steps, sort_keys=True, separators=(",", ":"))


def _invalid(reason: str, value: ErrorParam, where: dict[str, int]) -> NoReturn:
    params: dict[str, Any] = {"param_id": "search_space", "reason": reason, **where}
    if isinstance(value, str):
        params["value"] = value
    raise ParamError(BLOCK_PARAM_INVALID, params)


class GridSearch(Block):
    block_id = "validate.grid_search"
    version = "1.0.0"
    icon = "glyph-grid-search"
    references = ("engel2013preprocessing", "stone1974cv")
    fitted = False
    inputs = (port("model", "Model", refit_per_fold=True), port("folds", "Folds"))
    outputs = (port("results", "Results"),)
    params_type = GridSearchParams

    def apply(
        self,
        model: State,  # noqa: ARG002  (the graph's model; candidates are copies of its block)
        folds: FoldSet,  # noqa: ARG002  (shared by every candidate; already used there)
        params: GridSearchParams,  # noqa: ARG002
        candidates: Sequence[tuple[Chain, Results]],
    ) -> Results:
        if not candidates:
            raise ValueError("a grid search needs at least one candidate")
        # Step 4: one row per candidate, in candidate order: its chain, its chosen LV count
        # and its CV metrics (validate.cv names)
        names = list(candidates[0][1].metrics)
        table: dict[str, NDArray[Any]] = {
            "candidate": np.arange(len(candidates)),
            "chain": np.array([chain_label(c) for c, _ in candidates], dtype=np.str_),
            **{m: np.array([r.metrics[m] for _, r in candidates]) for m in names},
        }

        # Step 5: best = smallest RMSECV at the candidate's own n_lv on its CV curve (the
        # value its LV rule chose on); ties -> the first candidate
        criterion = np.array([r.details["rmsecv"][int(r.metrics["n_lv"])] for _, r in candidates])
        table["rmsecv_at_n_lv"] = criterion
        best = int(np.argmin(criterion))
        chosen = candidates[best][1]
        return Results(
            kind="search",
            metrics=dict(chosen.metrics),
            y_unit=chosen.y_unit,
            predictions=chosen.predictions,
            candidates=table,
            details={
                "best": best,
                "best_chain": chain_label(candidates[best][0]),
                "n_candidates": len(candidates),
                "criterion": "rmsecv_at_n_lv",
                "lv_rule": chosen.details["lv_rule"],
                "aggregation": chosen.details["aggregation"],
            },
        )

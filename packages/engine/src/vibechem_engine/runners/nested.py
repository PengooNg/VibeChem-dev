# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/runners/nested.py
"""Nested CV as pipeline documents (METHODS.md#nested-cv steps 1-2).

A ``validate.nested_cv`` node ``N`` is first expanded like a grid search
(:func:`~vibechem_engine.runners.search.expand_search`): one ``validate.cv`` branch per
candidate chain on the outer folds; the runner expands only the branch each outer fold
chose, for that fold. The choice comes from a sub-run of :func:`inner_pipeline` per
outer fold: the nodes upstream of ``N``'s model, the ``inner_folds`` block on the fold
source stream and a ``validate.grid_search`` node ``<N>.inner`` with ``N``'s search
space and CV params. Its sources are the outer fold's training rows of the fold source
stream, so the inner folds, every inner fit and the compiler's leakage checks see only
those rows.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from vibechem_core.block import parse_params
from vibechem_core.blocks.validate.grid_search import GridSearch
from vibechem_core.blocks.validate.nested_cv import (
    InnerChoice,
    NestedCV,
    NestedCVParams,
    check_inner_folds,
)
from vibechem_core.data import Results
from vibechem_core.registry import Registry
from vibechem_engine.compiler.leakage import ancestors

__all__ = ["NESTED_CV", "check_nested", "inner_choice", "inner_pipeline", "inner_search_id"]

NESTED_CV = NestedCV.block_id


def inner_search_id(node_id: str) -> str:
    return f"{node_id}.inner"


def check_nested(params: Mapping[str, Any], registry: Registry) -> None:
    """``ParamError`` for bad params or ``inner_folds`` (before anything runs);
    ``ValueError`` when ``validate.grid_search`` is not registered."""
    if GridSearch.block_id not in registry:
        raise ValueError(f"{NESTED_CV} needs {GridSearch.block_id} in the registry")
    check_inner_folds(parse_params(NestedCVParams, params).inner_folds, registry)


def inner_pipeline(
    pipeline: Mapping[str, Any], node_id: str, source: tuple[str, str], registry: Registry
) -> dict[str, Any]:
    """The pipeline that tunes nested node ``node_id`` on one outer training set;
    ``source`` = the fold source stream (node, port), whose rows the sub-run supplies."""
    edges: list[dict[str, Any]] = list(pipeline["edges"])
    by_id = {n["node_id"]: n for n in pipeline["nodes"]}
    raw: Mapping[str, Any] = by_id[node_id].get("params", {})
    params = parse_params(NestedCVParams, raw)
    model = next(e for e in edges if e["to_node"] == node_id and e["to_port"] == "model")
    keep = ancestors(cast(Any, edges), model["from_node"])
    meta = registry.meta(params.inner_folds.block_id)
    folds_id, search_id = f"{node_id}.inner_folds", inner_search_id(node_id)
    search_params = {k: v for k, v in raw.items() if k != "inner_folds"}
    search_params["search_space"] = params.search_space.to_json()  # nested default: LVs only
    nodes = [by_id[n] for n in by_id if n in keep] + [
        {"node_id": folds_id, "block_id": meta.block_id, "params": dict(params.inner_folds.params)},
        {"node_id": search_id, "block_id": GridSearch.block_id, "params": search_params},
    ]
    folds_out = next(p.port_id for p in meta.outputs if p.port_type == "Folds")
    added = [
        (source[0], source[1], folds_id, meta.inputs[0].port_id),
        (model["from_node"], model["from_port"], search_id, "model"),
        (folds_id, folds_out, search_id, "folds"),
    ]
    return {
        **pipeline,
        "nodes": nodes,
        "edges": [e for e in edges if e["to_node"] in keep]
        + [
            {
                "edge_id": f"{search_id}.e{k}",
                "from_node": a,
                "from_port": ap,
                "to_node": b,
                "to_port": bp,
            }
            for k, (a, ap, b, bp) in enumerate(added)
        ],
    }


def inner_choice(results: Results) -> InnerChoice:
    """The inner search's best candidate, its LV count and RMSECV there."""
    best = int(results.details["best"])
    criterion = cast(Mapping[str, Any], results.candidates)["rmsecv_at_n_lv"][best]
    return InnerChoice(best, str(results.details["best_chain"]), int(results.metrics["n_lv"]), float(criterion))  # fmt: skip

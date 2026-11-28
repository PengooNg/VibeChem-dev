# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/runners/search.py
"""Grid-search candidates as pipeline branches (METHODS.md#grid-search step 3).

:func:`expand_search` adds one branch per candidate chain of a ``validate.grid_search``
node ``S`` to the pipeline document: the chain's steps between the node that feeds the
model block's first input and a copy of the model block (same params, same other
inputs), then a ``validate.cv`` node with the search's CV params on the search's
``folds``. The compiler then builds each branch's fold plan and checks it for leakage
like any other validation node, so a candidate's results are those of a separate
``validate.cv`` run of its chain. Generated node ids start with ``<S>.c<i>``.

A ``validate.nested_cv`` node is expanded the same way (its outer folds run on these
branches, METHODS.md#nested-cv). It also sets the search's workers w = min(``effective_jobs(n_jobs)``, executor workers)
and checks the serial limit (METHODS.md N31, decision by Quan: option A).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from vibechem_core.block import parse_params
from vibechem_core.blocks.validate.cv import CrossValidation, CVParams
from vibechem_core.blocks.validate.grid_search import (
    Chain,
    GridSearch,
    GridSearchParams,
    candidate_chains,
    check_search_size,
    check_serial,
    effective_jobs,
    spectra_output,
)
from vibechem_core.errors import VibeChemWarning
from vibechem_core.registry import Registry

__all__ = ["GRID_SEARCH", "Search", "expand_search"]

GRID_SEARCH = GridSearch.block_id
_CV_PARAMS = frozenset(f.name for f in dataclasses.fields(CVParams))


@dataclass(frozen=True, slots=True)
class Search:
    """One expanded search: per candidate its chain and its ``validate.cv`` node id, in
    candidate order; ``workers`` = the core budget of the stages with its branch tasks;
    ``warning`` = ``VALIDATION_SEARCH_PARALLEL_ONLY`` for the search node, if raised."""

    branches: list[tuple[Chain, str]]
    workers: int
    warning: VibeChemWarning | None


def expand_search(
    pipeline: Mapping[str, Any],
    node_id: str,
    registry: Registry,
    *,
    max_workers: int,
    cpu_count: int,
) -> tuple[dict[str, Any], Search]:
    """``pipeline`` with the candidate branches of search node ``node_id`` (any block with
    ``GridSearchParams``), and the :class:`Search` (``max_workers`` = the executor's workers).

    Raises ``ParamError`` (``BLOCK_PARAM_INVALID``) for bad search params, a search
    above the N31 caps or above the serial limit with one worker (checked before any
    branch is built); ``ValueError``
    when ``validate.cv`` is not registered. ``pipeline`` must have passed the graph checks.
    """
    if CrossValidation.block_id not in registry:
        raise ValueError(f"{GRID_SEARCH} needs {CrossValidation.block_id} in the registry")
    nodes = [dict(n) for n in pipeline["nodes"]]
    edges = [dict(e) for e in pipeline["edges"]]
    by_id = {n["node_id"]: n for n in nodes}
    search = by_id[node_id]
    raw: Mapping[str, Any] = search.get("params", {})
    params = cast(GridSearchParams, parse_params(registry.get(search["block_id"]).params_type, raw))
    chains = candidate_chains(params.search_space, registry)

    def into(node: str, port: str) -> dict[str, Any]:
        return next(e for e in edges if e["to_node"] == node and e["to_port"] == port)

    model_edge, folds_edge = into(node_id, "model"), into(node_id, "folds")
    model = by_id[model_edge["from_node"]]
    # M = the model's maximum LV count (N31); a bad value is the model node's own error later
    default_lv = getattr(registry.get(model["block_id"]).params_type(), "n_components", 1)
    n_lv = model.get("params", {}).get("n_components", default_lv)
    m = n_lv if type(n_lv) is int else 1
    check_search_size(len(chains), m)
    workers = min(effective_jobs(params.n_jobs, cpu_count), max_workers)
    warning = check_serial(len(chains) * m, workers)
    first = registry.meta(model["block_id"]).inputs[0].port_id
    feed = into(model["node_id"], first)
    others = [e for e in edges if e["to_node"] == model["node_id"] and e["to_port"] != first]
    cv_params = {k: v for k, v in raw.items() if k in _CV_PARAMS}

    branches: list[tuple[Chain, str]] = []
    for i, chain in enumerate(chains):
        cand = f"{node_id}.c{i}"
        added: list[tuple[str, str, str, str]] = []
        prev: tuple[str, str] = (feed["from_node"], feed["from_port"])
        for j, step in enumerate(chain):
            step_id, meta = f"{cand}.s{j}", registry.meta(step.block_id)
            nodes.append(
                {"node_id": step_id, "block_id": step.block_id, "params": dict(step.params)}
            )
            added.append((prev[0], prev[1], step_id, meta.inputs[0].port_id))
            prev = (step_id, str(spectra_output(meta)))
        model_id = f"{cand}.model"
        nodes.append({**model, "node_id": model_id})
        added.append((prev[0], prev[1], model_id, first))
        added += [(e["from_node"], e["from_port"], model_id, e["to_port"]) for e in others]
        nodes.append({"node_id": cand, "block_id": CrossValidation.block_id, "params": cv_params})
        added.append((model_id, model_edge["from_port"], cand, "model"))
        added.append((folds_edge["from_node"], folds_edge["from_port"], cand, "folds"))
        edges += [
            {
                "edge_id": f"{cand}.e{k}",
                "from_node": a,
                "from_port": ap,
                "to_node": b,
                "to_port": bp,
            }
            for k, (a, ap, b, bp) in enumerate(added)
        ]
        branches.append((chain, cand))
    return {**pipeline, "nodes": nodes, "edges": edges}, Search(branches, workers, warning)

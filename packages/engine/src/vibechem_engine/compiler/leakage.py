# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/compiler/leakage.py
"""Leakage rules: no ``fit`` task may see validation or test rows (ARCHITECTURE.md §3.2,
DATA_MODEL.md §4.6). Static, on the user graph; every finding is ``PIPELINE_LEAKAGE``.

1. :func:`fitted_before_source`: a fitted block upstream of a fold source was fitted
   once on rows that are some fold's validation rows (issue on the node).
2. :func:`row_leaks`, by row provenance. Every node without input edges is a data
   source. A stream carries *tags* ``(source node, subsets)``: the sources its rows or
   information come from, and the row subsets on the way (a ``train`` or ``test``
   output port, e.g. of a hold-out split, and inside a fold the fold's ``train`` rows).
   A node's outputs carry the union of its inputs' tags. A fit input is leaky (issue
   on the node and that input port) when one of its tags

   - passed a ``test`` output (fit on test rows), or
   - comes from a source whose other fit inputs were narrowed to a subset this tag did
     not pass (e.g. MSC ``reference`` wired from the unsplit dataset while ``spectra``
     are the training rows, R39).

   Checked once outside the folds and once per fold scope, where the fold source stream
   is narrowed to the fold's ``train`` rows and nodes outside the refit subgraph keep
   their full-row tags. Inputs from another data source are never leaky.

shortcut: provenance is by graph ancestry, so a same-source input that a block uses
only partly (or not at all) is still rejected; refine per port if a real block needs it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from vibechem_core.block import BlockMeta
from vibechem_engine.graph import GraphIssue

__all__ = ["PIPELINE_LEAKAGE", "FoldScope", "ancestors", "fitted_before_source", "row_leaks"]

PIPELINE_LEAKAGE = "PIPELINE_LEAKAGE"

type Edge = Mapping[str, Any]
type Stream = tuple[str, str]  # (node_id, output port_id)
type Tag = tuple[str, tuple[Stream, ...]]  # (data source node_id, row subsets on the path)
type Tagger = Callable[[str, str], frozenset[Tag]]

_SUBSET_PORTS = frozenset({"train", "test"})


@dataclass(frozen=True, slots=True)
class FoldScope:
    """One validation node's fold: ``source`` is narrowed, ``nodes`` are refitted."""

    node_id: str
    source: Stream
    nodes: frozenset[str]


def ancestors(edges: Sequence[Edge], node_id: str) -> set[str]:
    """``node_id`` and every node upstream of it."""
    seen: set[str] = set()
    frontier = [node_id]
    while frontier:
        n = frontier.pop()
        if n not in seen:
            seen.add(n)
            frontier += [e["from_node"] for e in edges if e["to_node"] == n]
    return seen


def fitted_before_source(
    metas: Mapping[str, BlockMeta], edges: Sequence[Edge], order: Sequence[str], source: str
) -> list[GraphIssue]:
    """Rule 1 for the fold source node ``source``."""
    upstream = ancestors(edges, source)
    return [GraphIssue(PIPELINE_LEAKAGE, n) for n in order if n in upstream and metas[n].fitted]


def row_leaks(
    metas: Mapping[str, BlockMeta],
    edges: Sequence[Edge],
    order: Sequence[str],
    scopes: Sequence[FoldScope],
) -> list[GraphIssue]:
    """Rule 2 outside the folds and in every fold scope, in topological order."""
    into: dict[str, list[Edge]] = {n: [] for n in metas}
    for e in edges:
        into[e["to_node"]].append(e)

    outer, outer_inputs = _tagger(metas, into, None, None)
    found: set[tuple[str, str]] = set()
    for inputs, nodes in [
        (outer_inputs, frozenset(metas)),
        *((_tagger(metas, into, s, outer)[1], s.nodes) for s in scopes),
    ]:
        found |= {(n, p) for n in nodes if metas[n].fitted for p in _leaky_ports(inputs(n))}
    rank = {n: i for i, n in enumerate(order)}
    return [
        GraphIssue(PIPELINE_LEAKAGE, n, p)
        for n, p in sorted(found, key=lambda f: (rank[f[0]], f[1]))
    ]


def _tagger(
    metas: Mapping[str, BlockMeta],
    into: Mapping[str, list[Edge]],
    scope: FoldScope | None,
    outer: Tagger | None,
) -> tuple[Tagger, Callable[[str], list[tuple[str, frozenset[Tag]]]]]:
    """Tags of a stream, and of each input of a node, in one context (``scope``)."""
    memo: dict[str, frozenset[Tag]] = {}

    def inputs(node: str) -> list[tuple[str, frozenset[Tag]]]:
        return [(e["to_port"], stream(e["from_node"], e["from_port"])) for e in into[node]]

    def node_tags(node: str) -> frozenset[Tag]:
        if node not in memo:
            if not into[node]:
                memo[node] = frozenset({(node, ())})
            else:
                tagged = inputs(node)
                # a leak is reported once, at the fit that sees it, not again downstream
                leaky = set(_leaky_ports(tagged)) if metas[node].fitted else set[str]()
                memo[node] = frozenset(t for p, tags in tagged if p not in leaky for t in tags)
        return memo[node]

    def stream(node: str, port: str) -> frozenset[Tag]:
        if scope is not None and outer is not None:
            if (node, port) == scope.source:
                return _narrow(outer(node, port), (scope.node_id, "train"))
            if node not in scope.nodes:
                return outer(node, port)
        tags = node_tags(node)
        return _narrow(tags, (node, port)) if port in _SUBSET_PORTS else tags

    return stream, inputs


def _narrow(tags: frozenset[Tag], subset: Stream) -> frozenset[Tag]:
    return frozenset((src, (*path, subset)) for src, path in tags)


def _leaky_ports(inputs: Sequence[tuple[str, frozenset[Tag]]]) -> list[str]:
    """Ports of one fit task whose tags break rule 2."""
    # training subsets only: a test subset is leaky by itself (first condition)
    subsets = {(src, s) for _, tags in inputs for src, path in tags for s in path if s[1] != "test"}
    return [
        port_id
        for port_id, tags in inputs
        if any(
            any(p == "test" for _, p in path)
            or any(s not in path for other, s in subsets if other == src)
            for src, path in tags
        )
    ]

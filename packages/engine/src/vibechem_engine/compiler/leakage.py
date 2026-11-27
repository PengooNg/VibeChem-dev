# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/compiler/leakage.py
"""Leakage rules: no ``fit`` task may see validation or test rows (ARCHITECTURE.md §3.2,
DATA_MODEL.md §4.6). Static, on the user graph; every finding is ``PIPELINE_LEAKAGE``.

1. :func:`fitted_before`: a fitted block upstream of a fold source or of a block with a
   used ``train``/``test`` output was fitted once on rows that are some fold's
   validation rows or the test rows (issue on the node).
2. :func:`row_leaks`, by row provenance. Every node without input edges is a data
   source, identified by its ``block_id`` and ``params`` (two nodes loading the same
   dataset are one source). A stream carries *tags* ``(source, subsets)``: the sources
   its rows or information come from, and the row subsets on the way (a ``train`` or
   ``test`` output port, e.g. of a hold-out split, and inside a fold the fold's
   ``train`` rows). A node's outputs carry the union of its inputs' tags. The first
   declared input of a fitted block holds its training rows (``spectra``). A fit input
   is leaky (issue on the node and that input port) when one of its tags

   - passed a ``test`` output (fit on test rows), or
   - is not a subset of the training rows of the same source: its subsets do not start
     with those of the first input (e.g. MSC ``reference`` wired from the unsplit
     dataset while ``spectra`` are the training rows, R39), or the first input itself
     mixes rows of one source with different subsets.

   A ``Model``/``Transform`` input is leaky when another input of the same node holds
   test rows of a split (``<split>.test``) and the state's tags from that source did
   not pass ``<split>.train`` (a model fitted on rows that include the test set,
   applied to it; DATA_MODEL.md §4.6 external test set).

   Checked once outside the folds and once per fold scope, where the fold source stream
   is narrowed to the fold's ``train`` rows and nodes outside the refit subgraph keep
   their full-row tags. Inputs from another data source are never leaky.

shortcut: provenance is by graph ancestry, so a same-source input that a block uses
only partly (or not at all) is still rejected; refine per port if a real block needs it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from vibechem_core.block import BlockMeta
from vibechem_engine.graph import GraphIssue

__all__ = [
    "PIPELINE_LEAKAGE",
    "FoldScope",
    "ancestors",
    "fitted_before",
    "row_leaks",
    "split_nodes",
]

PIPELINE_LEAKAGE = "PIPELINE_LEAKAGE"

type Edge = Mapping[str, Any]
type Stream = tuple[str, str]  # (node_id, output port_id)
type Tag = tuple[str, tuple[Stream, ...]]  # (data source node_id, row subsets on the path)
type Tagger = Callable[[str, str], frozenset[Tag]]

_SUBSET_PORTS = frozenset({"train", "test"})
_STATE_TYPES = frozenset({"Model", "Transform"})


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


def fitted_before(
    metas: Mapping[str, BlockMeta],
    edges: Sequence[Edge],
    order: Sequence[str],
    nodes: Iterable[str],
) -> list[GraphIssue]:
    """Rule 1 for fold source or split ``nodes``."""
    upstream = set[str]().union(*(ancestors(edges, n) for n in nodes))
    return [GraphIssue(PIPELINE_LEAKAGE, n) for n in order if n in upstream and metas[n].fitted]


def split_nodes(edges: Sequence[Edge]) -> set[str]:
    """Nodes whose ``train`` or ``test`` output is used."""
    return {e["from_node"] for e in edges if e["from_port"] in _SUBSET_PORTS}


def row_leaks(
    metas: Mapping[str, BlockMeta],
    edges: Sequence[Edge],
    order: Sequence[str],
    scopes: Sequence[FoldScope],
    sources: Mapping[str, str],
) -> list[GraphIssue]:
    """Rule 2 outside the folds and in every fold scope, in topological order.

    ``sources`` maps every node to its dataset identity (used for nodes without inputs).
    """
    into: dict[str, list[Edge]] = {n: [] for n in metas}
    for e in edges:
        into[e["to_node"]].append(e)

    outer, outer_inputs = _tagger(metas, into, order, sources, None, None)
    found: set[tuple[str, str]] = set()
    for inputs, nodes in [
        (outer_inputs, frozenset(metas)),
        *((_tagger(metas, into, order, sources, s, outer)[1], s.nodes) for s in scopes),
    ]:
        for n in nodes:
            tagged = inputs(n)
            fit_leaks = _leaky_ports(metas[n], tagged) if metas[n].fitted else []
            found |= {(n, p) for p in [*fit_leaks, *_stale_states(metas[n], tagged)]}
    rank = {n: i for i, n in enumerate(order)}
    return [
        GraphIssue(PIPELINE_LEAKAGE, n, p)
        for n, p in sorted(found, key=lambda f: (rank[f[0]], f[1]))
    ]


def _tagger(
    metas: Mapping[str, BlockMeta],
    into: Mapping[str, list[Edge]],
    order: Sequence[str],
    sources: Mapping[str, str],
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
                memo[node] = frozenset({(sources[node], ())})
            else:
                memo[node] = _output_tags(metas[node], inputs(node))
        return memo[node]

    def stream(node: str, port: str) -> frozenset[Tag]:
        if scope is not None and outer is not None:
            if (node, port) == scope.source:
                return _narrow(outer(node, port), (scope.node_id, "train"))
            if node not in scope.nodes:
                return outer(node, port)
        tags = node_tags(node)
        return _narrow(tags, (node, port)) if port in _SUBSET_PORTS else tags

    for node in order:  # fill the memo in topological order: no deep recursion
        node_tags(node)
    return stream, inputs


def _narrow(tags: frozenset[Tag], subset: Stream) -> frozenset[Tag]:
    return frozenset((src, (*path, subset)) for src, path in tags)


def _output_tags(meta: BlockMeta, inputs: Sequence[tuple[str, frozenset[Tag]]]) -> frozenset[Tag]:
    """Union of the input tags. For a fitted block, leaky inputs are left out (a leak is
    reported once, at the fit that sees it) and so are same-source inputs of the first
    input's sources: they passed the check, so they hold a subset of its rows."""
    if not meta.fitted:
        return frozenset(t for _, tags in inputs for t in tags)
    leaky, primary = set(_leaky_ports(meta, inputs)), meta.inputs[0].port_id
    first = frozenset(t for p, tags in inputs if p == primary and p not in leaky for t in tags)
    trained = {src for src, _ in first}
    others = (t for p, tags in inputs if p not in leaky | {primary} for t in tags)
    return first | {t for t in others if t[0] not in trained}


def _leaky_ports(meta: BlockMeta, inputs: Sequence[tuple[str, frozenset[Tag]]]) -> list[str]:
    """Ports of one fit task whose tags break rule 2."""
    primary = meta.inputs[0].port_id
    train: dict[str, set[tuple[Stream, ...]]] = {}
    for port_id, tags in inputs:
        if port_id == primary:
            for src, path in tags:
                train.setdefault(src, set()).add(path)

    def leaky(port_id: str, src: str, path: tuple[Stream, ...]) -> bool:
        if any(part == "test" for _, part in path):
            return True
        rows = train.get(src, set())
        if port_id == primary:
            return len(rows) > 1
        return any(path[: len(p)] != p for p in rows)

    return [p for p, tags in inputs if any(leaky(p, src, path) for src, path in tags)]


def _stale_states(meta: BlockMeta, inputs: Sequence[tuple[str, frozenset[Tag]]]) -> list[str]:
    """State input ports of one node that may have seen the test rows it is applied to."""
    states = {p.port_id for p in meta.inputs if p.port_type in _STATE_TYPES}
    tests = {
        (src, split)
        for port_id, tags in inputs
        if port_id not in states
        for src, path in tags
        for split, part in path
        if part == "test"
    }
    return [
        port_id
        for port_id, tags in inputs
        if port_id in states
        and any(
            (split, "train") not in path
            for src, path in tags
            for other, split in tests
            if other == src
        )
    ]

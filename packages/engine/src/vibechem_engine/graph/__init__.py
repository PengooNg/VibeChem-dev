# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/graph/__init__.py
"""Static validation of a pipeline graph (DATA_MODEL.md §2.6 shape, §4.4 graph rules).

:func:`validate_graph` checks every edge and input against the blocks' port
declarations and returns all problems as :class:`GraphIssue` items, the ``issues`` of
``POST …/validate``. Checks that need data (rows, axes, Y) run when a block runs.

A pipeline that references an unknown block, node or port, or repeats a ``node_id``,
is malformed rather than invalid: no §7 code covers it, so it raises ``ValueError``
(RISKS.md R50). The document's own shape (required keys) is the pipeline schema's job
(T2.03); a missing key raises ``KeyError``.

``graphlib`` finds one cycle per call, so a graph with two cycles reports one
``PIPELINE_CYCLE`` until it is fixed.
"""

from __future__ import annotations

import graphlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from vibechem_core.block import BlockMeta
from vibechem_core.errors import ErrorParam, message_key
from vibechem_core.registry import Registry
from vibechem_engine.ports import is_compatible

__all__ = [
    "PIPELINE_CYCLE",
    "PIPELINE_INPUT_MULTIPLE_EDGES",
    "PIPELINE_PORT_TYPE_MISMATCH",
    "PIPELINE_REQUIRED_INPUT_MISSING",
    "GraphIssue",
    "validate_graph",
]

PIPELINE_PORT_TYPE_MISMATCH = "PIPELINE_PORT_TYPE_MISMATCH"
PIPELINE_REQUIRED_INPUT_MISSING = "PIPELINE_REQUIRED_INPUT_MISSING"
PIPELINE_CYCLE = "PIPELINE_CYCLE"
PIPELINE_INPUT_MULTIPLE_EDGES = "PIPELINE_INPUT_MULTIPLE_EDGES"


@dataclass(frozen=True, slots=True)
class GraphIssue:
    """One ``issues`` entry of ``POST …/validate`` (DATA_MODEL.md §2.6)."""

    code: str
    node_id: str | None
    port_id: str | None = None
    params: Mapping[str, ErrorParam] = field(default_factory=dict[str, ErrorParam])
    severity: Literal["error", "warning"] = "error"

    def to_dict(self) -> dict[str, Any]:
        kind = "errors" if self.severity == "error" else "warnings"
        return {
            "severity": self.severity,
            "code": self.code,
            "node_id": self.node_id,
            "port_id": self.port_id,
            "message_key": message_key(self.code, kind),
            "params": dict(self.params),
        }


def _port_types(meta: BlockMeta, direction: Literal["inputs", "outputs"]) -> dict[str, str]:
    return {p.port_id: p.port_type for p in getattr(meta, direction)}


def validate_graph(pipeline: Mapping[str, Any], registry: Registry) -> list[GraphIssue]:
    """All static graph problems of ``pipeline``, in edge order, then node order.

    Raises ``ValueError`` for a malformed pipeline (see the module docstring).
    """
    nodes: Sequence[Mapping[str, Any]] = pipeline["nodes"]
    edges: Sequence[Mapping[str, Any]] = pipeline["edges"]
    metas: dict[str, BlockMeta] = {}
    for node in nodes:
        node_id = node["node_id"]
        if node_id in metas:
            raise ValueError(f"duplicate node_id {node_id!r}")
        if node["block_id"] not in registry:
            raise ValueError(f"node {node_id!r}: unknown block_id {node['block_id']!r}")
        metas[node_id] = registry.meta(node["block_id"])

    issues: list[GraphIssue] = []
    connected: set[tuple[str, str]] = set()
    predecessors: dict[str, set[str]] = {node_id: set() for node_id in metas}
    for edge in edges:
        src, dst = edge["from_node"], edge["to_node"]
        for node_id in (src, dst):
            if node_id not in metas:
                raise ValueError(f"edge {edge.get('edge_id')!r}: unknown node {node_id!r}")
        from_port, to_port = edge["from_port"], edge["to_port"]
        from_type = _port_types(metas[src], "outputs").get(from_port)
        to_type = _port_types(metas[dst], "inputs").get(to_port)
        if from_type is None or to_type is None:
            bad = f"output {from_port!r}" if from_type is None else f"input {to_port!r}"
            raise ValueError(f"edge {edge.get('edge_id')!r}: unknown {bad}")
        if not is_compatible(from_type, to_type):
            issues.append(
                GraphIssue(
                    PIPELINE_PORT_TYPE_MISMATCH,
                    dst,
                    to_port,
                    {
                        "from_port": from_port,
                        "to_port": to_port,
                        "from_type": from_type,
                        "to_type": to_type,
                    },
                )
            )
        multiple = next(p.multiple for p in metas[dst].inputs if p.port_id == to_port)
        if (dst, to_port) in connected and not multiple:
            issues.append(GraphIssue(PIPELINE_INPUT_MULTIPLE_EDGES, dst, to_port))
        connected.add((dst, to_port))
        predecessors[dst].add(src)

    for node_id, meta in metas.items():
        issues.extend(
            GraphIssue(PIPELINE_REQUIRED_INPUT_MISSING, node_id, p.port_id)
            for p in meta.inputs
            if p.required and (node_id, p.port_id) not in connected
        )

    try:
        graphlib.TopologicalSorter(predecessors).prepare()
    except graphlib.CycleError as err:
        cycle: list[str] = err.args[1]
        issues.append(GraphIssue(PIPELINE_CYCLE, cycle[0]))
    return issues

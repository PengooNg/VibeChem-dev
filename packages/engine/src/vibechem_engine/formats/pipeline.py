# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/formats/pipeline.py
"""Pipeline file ``pipelines/<pipeline_id>.vcp.json``, format version 1 (DATA_MODEL.md §6.3).

The file is the pipeline document of §2.6. :class:`PipelineFile` is its schema; the
committed ``pipeline.schema.json`` is its JSON Schema export. Beyond the JSON Schema the
model checks that node and edge ids are unique and that every edge names existing
nodes (RISKS.md R50). Ports, types and block parameters are checked by
``vibechem_engine.graph`` and ``parse_params`` when the pipeline is validated.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Annotated, Literal

from pydantic import Field, JsonValue, field_validator, model_validator

from vibechem_engine.formats._files import (
    SEMVER_PATTERN,
    TIMESTAMP_PATTERN,
    StrictModel,
    dump,
    id_pattern,
    read_json,
    validate,
    write_atomic,
)
from vibechem_engine.formats.migrations import migrate

__all__ = [
    "PIPELINE_FILE_INVALID",
    "Edge",
    "Node",
    "PipelineFile",
    "Position",
    "load_pipeline",
    "save_pipeline",
]

PIPELINE_FILE_INVALID = "PIPELINE_FILE_INVALID"

NodeId = Annotated[str, Field(pattern=id_pattern("nd"))]
PortId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
Timestamp = Annotated[str, Field(pattern=TIMESTAMP_PATTERN)]


class Position(StrictModel):
    x: float
    y: float


class Node(StrictModel):
    node_id: NodeId
    block_id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")]
    block_version: Annotated[str, Field(pattern=SEMVER_PATTERN)]
    params: dict[str, JsonValue]
    position: Position
    label: str | None


class Edge(StrictModel):
    edge_id: Annotated[str, Field(pattern=id_pattern("eg"))]
    from_node: NodeId
    from_port: PortId
    to_node: NodeId
    to_port: PortId


def _repeated(ids: Sequence[str]) -> list[str]:
    return sorted({i for i in ids if ids.count(i) > 1})


class PipelineFile(StrictModel):
    format_version: Literal[1]
    pipeline_id: Annotated[str, Field(pattern=id_pattern("ppl"))]
    name: Annotated[str, Field(min_length=1)]
    revision: Annotated[int, Field(ge=0)]
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    created_at: Timestamp
    updated_at: Timestamp

    @field_validator("nodes")
    @classmethod
    def _unique_nodes(cls, nodes: tuple[Node, ...]) -> tuple[Node, ...]:
        if repeated := _repeated([n.node_id for n in nodes]):
            raise ValueError(f"repeated node_id {repeated}")
        return nodes

    @field_validator("edges")
    @classmethod
    def _unique_edges(cls, edges: tuple[Edge, ...]) -> tuple[Edge, ...]:
        if repeated := _repeated([e.edge_id for e in edges]):
            raise ValueError(f"repeated edge_id {repeated}")
        return edges

    @model_validator(mode="after")
    def _edges_reference_nodes(self) -> PipelineFile:
        known = {n.node_id for n in self.nodes}
        for edge in self.edges:
            for node_id in (edge.from_node, edge.to_node):
                if node_id not in known:
                    raise ValueError(f"edge {edge.edge_id} names unknown node {node_id}")
        return self


def load_pipeline(path: str | os.PathLike[str]) -> PipelineFile:
    """Read, migrate and validate a pipeline file; ``FormatError`` if it is invalid."""
    doc = migrate("pipeline", read_json(path, PIPELINE_FILE_INVALID), PIPELINE_FILE_INVALID)
    return validate(PipelineFile, doc, PIPELINE_FILE_INVALID)


def save_pipeline(pipeline: PipelineFile, path: str | os.PathLike[str]) -> None:
    """Write ``pipeline`` to ``path`` (UTF-8 JSON, replaced atomically)."""
    write_atomic(path, dump(pipeline))

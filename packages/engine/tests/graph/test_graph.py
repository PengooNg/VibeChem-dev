# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/graph/test_graph.py
"""``vibechem_engine.graph``: the static graph rules of DATA_MODEL.md §4.4 return the
§7 codes (T2.02 "Done when")."""

from __future__ import annotations

from typing import Any

import pytest

from vibechem_core.block import Block, port
from vibechem_core.registry import Registry
from vibechem_engine.graph import validate_graph


class _Source(Block):
    block_id = "test.source"
    version = "1.0.0"
    icon = "glyph-dummy"
    fitted = False
    inputs = ()
    outputs = (port("spectra", "Spectra"), port("folds", "Folds"))

    def apply(self, **kwargs: Any) -> Any:  # noqa: ARG002
        return None


class _Step(Block):
    block_id = "test.step"
    version = "1.0.0"
    icon = "glyph-dummy"
    fitted = False
    inputs = (
        port("spectra", "Spectra"),
        port("extra", "Table", required=False, multiple=True),
    )
    outputs = (port("spectra", "Spectra"),)

    def apply(self, **kwargs: Any) -> Any:  # noqa: ARG002
        return None


REGISTRY = Registry()
REGISTRY.register(_Source)
REGISTRY.register(_Step)


def _pipeline(nodes: dict[str, str], edges: list[tuple[str, str, str, str]]) -> dict[str, Any]:
    return {
        "nodes": [{"node_id": n, "block_id": b} for n, b in nodes.items()],
        "edges": [
            {"edge_id": f"eg_{i}", "from_node": a, "from_port": ap, "to_node": b, "to_port": bp}
            for i, (a, ap, b, bp) in enumerate(edges)
        ],
    }


def _codes(pipeline: dict[str, Any]) -> list[tuple[str, str | None, str | None]]:
    return [(i.code, i.node_id, i.port_id) for i in validate_graph(pipeline, REGISTRY)]


def test_valid_chain_with_implicit_view_and_fan_out() -> None:
    p = _pipeline(
        {"a": "test.source", "b": "test.step", "c": "test.step"},
        [
            ("a", "spectra", "b", "spectra"),
            ("a", "spectra", "c", "spectra"),  # fan-out
            ("a", "spectra", "b", "extra"),  # Spectra -> Table implicit view
            ("c", "spectra", "b", "extra"),  # second edge into a multiple input
        ],
    )
    assert validate_graph(p, REGISTRY) == []


def test_type_mismatch() -> None:
    p = _pipeline({"a": "test.source", "b": "test.step"}, [("a", "folds", "b", "spectra")])
    [issue] = validate_graph(p, REGISTRY)
    assert (issue.code, issue.node_id, issue.port_id) == (
        "PIPELINE_PORT_TYPE_MISMATCH",
        "b",
        "spectra",
    )
    assert issue.params == {
        "from_port": "folds",
        "to_port": "spectra",
        "from_type": "Folds",
        "to_type": "Spectra",
    }
    assert issue.to_dict() == {
        "severity": "error",
        "code": "PIPELINE_PORT_TYPE_MISMATCH",
        "node_id": "b",
        "port_id": "spectra",
        "message_key": "errors.pipeline.port_type_mismatch",
        "params": issue.params,
    }


def test_required_input_missing() -> None:
    p = _pipeline({"a": "test.source", "b": "test.step"}, [("a", "spectra", "b", "extra")])
    assert _codes(p) == [("PIPELINE_REQUIRED_INPUT_MISSING", "b", "spectra")]


def test_second_edge_into_single_input() -> None:
    p = _pipeline(
        {"a": "test.source", "b": "test.step"},
        [("a", "spectra", "b", "spectra"), ("a", "spectra", "b", "spectra")],
    )
    assert _codes(p) == [("PIPELINE_INPUT_MULTIPLE_EDGES", "b", "spectra")]


def test_cycle() -> None:
    p = _pipeline(
        {"a": "test.source", "b": "test.step", "c": "test.step"},
        [
            ("a", "spectra", "b", "spectra"),
            ("b", "spectra", "c", "spectra"),
            ("c", "spectra", "b", "extra"),
        ],
    )
    [(code, node_id, port_id)] = _codes(p)
    assert (code, port_id) == ("PIPELINE_CYCLE", None)
    assert node_id in {"b", "c"}


def test_self_loop_is_a_cycle() -> None:
    p = _pipeline(
        {"a": "test.source", "b": "test.step"},
        [("a", "spectra", "b", "spectra"), ("b", "spectra", "b", "extra")],
    )
    assert _codes(p) == [("PIPELINE_CYCLE", "b", None)]


def test_all_issues_are_collected() -> None:
    p = _pipeline(
        {"a": "test.source", "b": "test.step", "c": "test.step"},
        [("a", "folds", "b", "spectra")],
    )
    assert _codes(p) == [
        ("PIPELINE_PORT_TYPE_MISMATCH", "b", "spectra"),
        ("PIPELINE_REQUIRED_INPUT_MISSING", "c", "spectra"),
    ]


@pytest.mark.parametrize(
    ("nodes", "edges"),
    [
        ({"a": "test.unknown"}, []),
        ({"a": "test.source", "b": "test.step"}, [("x", "spectra", "b", "spectra")]),
        ({"a": "test.source", "b": "test.step"}, [("a", "nope", "b", "spectra")]),
        ({"a": "test.source", "b": "test.step"}, [("a", "spectra", "b", "nope")]),
    ],
)
def test_malformed_references_raise(
    nodes: dict[str, str], edges: list[tuple[str, str, str, str]]
) -> None:
    with pytest.raises(ValueError, match=r"unknown"):
        validate_graph(_pipeline(nodes, edges), REGISTRY)


def test_duplicate_node_id_raises() -> None:
    p = {"nodes": [{"node_id": "a", "block_id": "test.source"}] * 2, "edges": []}
    with pytest.raises(ValueError, match=r"duplicate"):
        validate_graph(p, REGISTRY)

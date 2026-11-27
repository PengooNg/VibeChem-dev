# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/ports/__init__.py
"""Port type registry and edge compatibility rules (DATA_MODEL.md §4.1, §4.4).

An edge ``from_type -> to_type`` is valid when the types are equal or the pair is in
:data:`COMPATIBILITY`. The graph validator (T2.02) turns an invalid edge into
``PIPELINE_PORT_TYPE_MISMATCH``; the compiler (T2.04) uses :func:`edge_rule` to insert
the implicit view or unfold.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from vibechem_core.block import PORT_TYPES

__all__ = [
    "COMPATIBILITY",
    "PORT_TYPE_REGISTRY",
    "CompatibilityRule",
    "PortType",
    "edge_rule",
    "is_compatible",
    "port_types_payload",
]

type RuleName = Literal["implicit_view", "implicit_unfold"]


@dataclass(frozen=True, slots=True)
class PortType:
    """One row of DATA_MODEL.md §4.1."""

    name: str
    description_key: str
    shape_icon: str


@dataclass(frozen=True, slots=True)
class CompatibilityRule:
    """One row of DATA_MODEL.md §4.4: ``from_type`` may feed ``to_type`` via ``rule``."""

    from_type: str
    to_type: str
    rule: RuleName


PORT_TYPE_REGISTRY: tuple[PortType, ...] = (
    PortType("Spectra", "ports.spectra", "circle"),
    PortType("Table", "ports.table", "circle"),
    PortType("Model", "ports.model", "diamond"),
    PortType("Transform", "ports.transform", "diamond_outline"),
    PortType("Folds", "ports.folds", "triangle"),
    PortType("Results", "ports.results", "square"),
    PortType("ImageCube", "ports.image_cube", "hexagon"),
)

COMPATIBILITY: tuple[CompatibilityRule, ...] = (
    CompatibilityRule("Spectra", "Table", "implicit_view"),
    CompatibilityRule("Results", "Table", "implicit_view"),
    CompatibilityRule("ImageCube", "Spectra", "implicit_unfold"),
)

_RULES: dict[tuple[str, str], RuleName] = {(r.from_type, r.to_type): r.rule for r in COMPATIBILITY}


def _check_name(port_type: str) -> None:
    if port_type not in PORT_TYPES:
        raise ValueError(f"unknown port type {port_type!r}; one of {sorted(PORT_TYPES)}")


def is_compatible(from_type: str, to_type: str) -> bool:
    """True when an output of ``from_type`` may feed an input of ``to_type`` (§4.4).

    Raises ``ValueError`` for a name outside §4.1 (a caller bug, never a user's edge).
    """
    _check_name(from_type)
    _check_name(to_type)
    return from_type == to_type or (from_type, to_type) in _RULES


def edge_rule(from_type: str, to_type: str) -> RuleName | None:
    """Conversion rule of a valid edge; ``None`` when the types are equal (no conversion).

    Raises ``ValueError`` for an incompatible pair, so ``None`` always means "valid".
    """
    if not is_compatible(from_type, to_type):
        raise ValueError(f"port type {from_type!r} cannot feed {to_type!r} (DATA_MODEL §4.4)")
    return _RULES.get((from_type, to_type))


def port_types_payload() -> dict[str, list[dict[str, str]]]:
    """Body of ``GET /port-types`` (DATA_MODEL.md §2.3)."""
    return {
        "port_types": [
            {"name": t.name, "description_key": t.description_key, "shape_icon": t.shape_icon}
            for t in PORT_TYPE_REGISTRY
        ],
        "compatibility": [
            {"from": r.from_type, "to": r.to_type, "rule": r.rule} for r in COMPATIBILITY
        ],
    }

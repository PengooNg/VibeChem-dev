# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/ports/test_ports.py
"""``vibechem_engine.ports``: every compatibility rule of DATA_MODEL.md §4.4 (T2.01
"Done when"), written out by hand from the doc table."""

from __future__ import annotations

import itertools

import pytest

from vibechem_core.block import PORT_TYPES
from vibechem_engine.ports import (
    COMPATIBILITY,
    PORT_TYPE_REGISTRY,
    edge_rule,
    is_compatible,
    port_types_payload,
)

# The only valid edges between different types (§4.4 table).
ALLOWED = {
    ("Spectra", "Table"): "implicit_view",
    ("Results", "Table"): "implicit_view",
    ("ImageCube", "Spectra"): "implicit_unfold",
}


def test_registry_matches_core_type_names() -> None:
    names = [t.name for t in PORT_TYPE_REGISTRY]
    assert len(names) == len(set(names))
    assert set(names) == PORT_TYPES


@pytest.mark.parametrize("pair", sorted(ALLOWED))
def test_listed_rules(pair: tuple[str, str]) -> None:
    assert edge_rule(*pair) == ALLOWED[pair]
    assert is_compatible(*pair)


@pytest.mark.parametrize("port_type", sorted(PORT_TYPES))
def test_equal_types_connect_without_conversion(port_type: str) -> None:
    assert is_compatible(port_type, port_type)
    assert edge_rule(port_type, port_type) is None


def test_every_other_pair_is_rejected() -> None:
    rejected = [
        (a, b) for a, b in itertools.permutations(sorted(PORT_TYPES), 2) if (a, b) not in ALLOWED
    ]
    assert len(rejected) == 7 * 6 - len(ALLOWED)
    for a, b in rejected:
        assert not is_compatible(a, b), (a, b)
        assert edge_rule(a, b) is None


@pytest.mark.parametrize(
    "pair",
    [
        ("Model", "Transform"),
        ("Transform", "Model"),
        ("Spectra", "ImageCube"),
        ("Table", "Spectra"),
        ("Table", "Results"),
    ]
    + [(t, "Folds") for t in sorted(PORT_TYPES - {"Folds"})],
)
def test_named_refusals(pair: tuple[str, str]) -> None:
    # Spelled out in §4.4 "Not convertible, on purpose"; conversions are one-way.
    assert not is_compatible(*pair)


@pytest.mark.parametrize(
    "pair", [("Any", "Table"), ("Spectra", "spectra"), ("", "Model"), ("Any", "Any")]
)
def test_unknown_names_raise(pair: tuple[str, str]) -> None:
    with pytest.raises(ValueError, match="unknown port type"):
        is_compatible(*pair)


def test_payload_shape() -> None:
    payload = port_types_payload()
    assert payload["compatibility"] == [
        {"from": a, "to": b, "rule": r} for (a, b), r in ALLOWED.items()
    ]
    assert len(COMPATIBILITY) == len(ALLOWED)
    by_name = {t["name"]: t for t in payload["port_types"]}
    assert by_name["Transform"] == {
        "name": "Transform",
        "description_key": "ports.transform",
        "shape_icon": "diamond_outline",
    }
    assert by_name["ImageCube"]["description_key"] == "ports.image_cube"

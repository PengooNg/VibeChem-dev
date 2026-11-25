# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/api/test_schemas.py
"""``vibechem_engine.api.schemas``: the dummy blocks' ``/blocks/{id}`` JSON is valid
against DATA_MODEL.md §5 (T1.03 "Done when")."""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest
from pydantic import ValidationError

from vibechem_core.block import Block
from vibechem_core.testing import DummyCenter, DummyOffset, DummySchema
from vibechem_engine.api.schemas import BlockDetail, EnumParam, IntParam


@pytest.mark.parametrize("block", [DummyOffset, DummyCenter, DummySchema])
def test_dummy_block_detail_is_valid_and_round_trips(block: type[Block]) -> None:
    detail = json.loads(json.dumps(block.metadata().to_detail_dict()))  # as sent over HTTP
    model = BlockDetail.model_validate(detail)
    assert model.model_dump(mode="json", exclude_unset=True) == detail


def test_every_implemented_type_is_covered_by_the_dummy_schema_block() -> None:
    model = BlockDetail.model_validate(DummySchema.metadata().to_detail_dict())
    assert {p.type for p in model.params} == {"int", "float", "bool", "enum", "string"}
    window = model.params[0]
    assert isinstance(window, IntParam)
    assert window.odd_only is True
    deriv = model.params[4]
    assert isinstance(deriv, EnumParam)
    assert deriv.choices == [0, 1, 2]


def _detail() -> dict[str, Any]:
    return copy.deepcopy(DummySchema.metadata().to_detail_dict())


def _param(detail: dict[str, Any], param_id: str) -> dict[str, Any]:
    return next(p for p in detail["params"] if p["param_id"] == param_id)


@pytest.mark.parametrize(
    ("param_id", "change", "match"),
    [
        ("window", {"type": "range"}, "union_tag_invalid|does not match"),
        ("window", {"default": 15.0}, "integer"),
        ("window", {"default": 16}, "not odd"),
        ("window", {"default": 3}, "outside"),
        ("window", {"min": 200}, "greater than max"),
        ("window", {"colour": "red"}, "Extra inputs"),
        ("clip", {"default": 0}, "boolean"),
        ("clip", {"min": 0}, "Extra inputs"),
        ("mode", {"default": "max"}, "not one of the choices"),
        ("mode", {"choices": []}, "at least 1"),
        ("mode", {"choices": ["mean", 1]}, "one kind"),
        ("deriv", {"default": True}, "not one of the choices"),
        ("deriv", {"choices": [0, 1, 1]}, "duplicates"),
        ("polyorder", {"constraint": "polyorder < size"}, "another number param"),
        ("polyorder", {"constraint": "window < polyorder"}, "must start with"),
        ("polyorder", {"constraint": "polyorder == window"}, "pattern"),
        ("label", {"visible_if": {"param_id": "window", "values": [1]}}, "bool or enum"),
        ("label", {"visible_if": {"param_id": "mode", "values": []}}, "at least 1"),
        ("label", {"label_key": ""}, "at least 1"),
    ],
)
def test_invalid_param_entries_are_rejected(
    param_id: str, change: dict[str, Any], match: str
) -> None:
    detail = _detail()
    _param(detail, param_id).update(change)
    with pytest.raises(ValidationError, match=match):
        BlockDetail.model_validate(detail)


@pytest.mark.parametrize(
    ("change", "match"),
    [
        ({"help_key": None}, "string"),
        ({"tier": "P3"}, "P0"),
        ({"implementation": {"library": "scipy"}}, "function"),
        ({"block_id": "schema"}, "pattern"),
        ({"inputs": [{"port_id": "spectra", "port_type": "Any"}]}, "Spectra"),
    ],
)
def test_invalid_block_fields_are_rejected(change: dict[str, Any], match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        BlockDetail.model_validate(_detail() | change)


def test_param_ids_must_be_unique() -> None:
    detail = _detail()
    detail["params"].append(copy.deepcopy(detail["params"][0]))
    with pytest.raises(ValidationError, match="unique"):
        BlockDetail.model_validate(detail)


def test_json_schema_has_one_entry_per_param_type() -> None:
    schema = BlockDetail.model_json_schema()
    params = schema["properties"]["params"]["items"]
    assert params["discriminator"]["propertyName"] == "type"
    assert set(params["discriminator"]["mapping"]) == {"int", "float", "bool", "enum", "string"}
    json.dumps(schema)

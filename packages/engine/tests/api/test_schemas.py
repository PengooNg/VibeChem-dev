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
from vibechem_core.blocks.preprocess.cut import Cut
from vibechem_core.blocks.preprocess.detrend import Detrend
from vibechem_core.blocks.preprocess.msc import MSC
from vibechem_core.blocks.preprocess.savgol import SavitzkyGolay
from vibechem_core.blocks.preprocess.scaling import Autoscale, MeanCentre, Pareto
from vibechem_core.blocks.preprocess.snv import SNV
from vibechem_core.blocks.split.kennard_stone import KennardStone
from vibechem_core.blocks.split.random_split import RandomSplit
from vibechem_core.blocks.split.spxy import SPXY
from vibechem_core.testing import DummyCenter, DummyOffset, DummySchema
from vibechem_engine.api.schemas import BlockDetail, EnumParam, IntParam, WavelengthRangesParam


@pytest.mark.parametrize(
    "block",
    [
        *(DummyOffset, DummyCenter, DummySchema, Cut, SNV, MSC, Detrend, SavitzkyGolay),
        *(MeanCentre, Autoscale, Pareto, RandomSplit, KennardStone, SPXY),
    ],
)
def test_block_detail_is_valid_and_round_trips(block: type[Block]) -> None:
    detail = json.loads(json.dumps(block.metadata().to_detail_dict()))  # as sent over HTTP
    model = BlockDetail.model_validate(detail)
    assert model.model_dump(mode="json", exclude_unset=True) == detail


def test_every_implemented_type_is_covered_by_the_dummy_schema_block() -> None:
    model = BlockDetail.model_validate(DummySchema.metadata().to_detail_dict())
    assert {p.type for p in model.params} == {
        "int",
        "float",
        "bool",
        "enum",
        "string",
        "wavelength_ranges",
    }
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
        ("label", {"visible_if": {"param_id": "mode", "values": ["max"]}}, "not valid"),
        ("label", {"visible_if": {"param_id": "clip", "values": [1]}}, "not valid"),
        ("polyorder", {"default": 20, "max": 30}, "defaults break"),
        ("ranges", {"default": []}, "at least 1"),
        ("ranges", {"default": [[900.0]]}, "at least 2"),
        ("ranges", {"default": [[900.0, 1000.0, 1100.0]]}, "at most 2"),
        ("ranges", {"default": [[900.0, "1700"]]}, "float"),
        ("ranges", {"default": [[900.0, float("inf")]]}, "finite"),
        ("ranges", {"default": [900.0, 1700.0]}, "list"),
        ("ranges", {"unit": "nm"}, "Extra inputs"),
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


def test_float_choices_survive_a_javascript_round_trip() -> None:
    detail = _detail()
    _param(detail, "scale").update({"type": "enum", "default": 1, "choices": [0.5, 1]})
    for key in ("min", "unit"):
        del _param(detail, "scale")[key]
    model = BlockDetail.model_validate(detail)  # JSON.stringify([0.5, 1.0]) == "[0.5,1]"
    scale = next(p for p in model.params if p.param_id == "scale")
    assert isinstance(scale, EnumParam)


def test_param_ids_must_be_unique() -> None:
    detail = _detail()
    detail["params"].append(copy.deepcopy(detail["params"][0]))
    with pytest.raises(ValidationError, match="unique"):
        BlockDetail.model_validate(detail)


def test_json_schema_has_one_entry_per_param_type() -> None:
    schema = BlockDetail.model_json_schema()
    params = schema["properties"]["params"]["items"]
    assert params["discriminator"]["propertyName"] == "type"
    assert set(params["discriminator"]["mapping"]) == {
        "int",
        "float",
        "bool",
        "enum",
        "string",
        "wavelength_ranges",
    }
    json.dumps(schema)


def test_wavelength_ranges_entry_accepts_integers_and_either_order() -> None:
    detail = _detail()
    _param(detail, "ranges")["default"] = [[1700, 900], [2100.5, 2300]]  # as JavaScript sends
    model = BlockDetail.model_validate(detail)
    ranges = next(p for p in model.params if p.param_id == "ranges")
    assert isinstance(ranges, WavelengthRangesParam)
    assert ranges.default == [[1700.0, 900.0], [2100.5, 2300.0]]

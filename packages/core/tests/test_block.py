# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/test_block.py
"""Tests for ``vibechem_core.block``: Param, port, State, Block metadata, fit/apply."""

from dataclasses import FrozenInstanceError, dataclass
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
import pytest

from vibechem_core import block as block_module
from vibechem_core.block import (
    Block,
    NoParams,
    Param,
    ParamSpec,
    Port,
    State,
    param_specs,
    port,
)
from vibechem_core.data import Axis, SpectralDataset
from vibechem_core.errors import message_key
from vibechem_core.testing import DummyCenter, DummyOffset, DummyOffsetParams


def make_dataset(X: list[list[float]]) -> SpectralDataset:
    x = np.asarray(X, dtype=np.float64)
    n, p = x.shape
    return SpectralDataset(
        x,
        Axis(np.arange(p), "index"),
        signal_unit="arbitrary",
        sample_ids=[f"s{i}" for i in range(n)],
        row_index=np.arange(n),
        source_id="ds_test",
    )


# ---- fit / apply (Done when) --------------------------------------------------------


def test_stateless_dummy_block_applies() -> None:
    data = make_dataset([[1.0, 2.0], [3.0, 4.0]])
    out = DummyOffset().apply(spectra=data, params=DummyOffsetParams(offset=0.5))
    np.testing.assert_array_equal(out.X, [[1.5, 2.5], [3.5, 4.5]])
    assert out.history == ("Offset(0.5)",)
    np.testing.assert_array_equal(data.X, [[1.0, 2.0], [3.0, 4.0]])  # input unchanged


def test_fitted_dummy_block_fits_on_train_rows_and_applies_to_other_rows() -> None:
    data = make_dataset([[1.0, 10.0], [3.0, 30.0], [100.0, 100.0]])
    train, other = data.subset([0, 1]), data.subset([2])
    block = DummyCenter()
    state = block.fit(spectra=train, params=NoParams())
    np.testing.assert_array_equal(state.arrays["mean"], [2.0, 20.0])  # train rows only
    assert state.values["n_fitted"] == 2
    out = block.apply(spectra=other, params=NoParams(), state=state)
    np.testing.assert_array_equal(out.X, [[98.0, 80.0]])
    assert list(out.row_index) == [2]


def test_stateless_block_has_no_fit() -> None:
    with pytest.raises(NotImplementedError, match="DummyOffset does not implement fit"):
        DummyOffset().fit()


def test_base_apply_is_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="Block does not implement apply"):
        Block().apply()


# ---- Param --------------------------------------------------------------------------


@dataclass(frozen=True)
class _Params:
    ddof: int = Param(1, choices=(0, 1), tooltip_key="tip")
    window: int = Param(15, min=5, max=101, advanced=True)


def test_param_sets_the_default_and_records_the_spec() -> None:
    assert _Params() == _Params(ddof=1, window=15)
    specs = dict(param_specs(_Params))
    assert specs["ddof"] == ParamSpec(default=1, choices=(0, 1), tooltip_key="tip")
    assert specs["window"] == ParamSpec(default=15, min=5, max=101, advanced=True)
    assert list(specs) == ["ddof", "window"]


def test_params_are_frozen() -> None:
    with pytest.raises(FrozenInstanceError):
        _Params().ddof = 0  # type: ignore[misc]


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"default": 2, "choices": (0, 1)}, "not one of the choices"),
        ({"default": 1, "min": 3, "max": 2}, "greater than max"),
        ({"default": 1, "min": 2}, "outside"),
        ({"default": 9.5, "max": 2.0}, "outside"),
    ],
)
def test_param_rejects_inconsistent_declarations(kwargs: dict[str, Any], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        Param(**kwargs)


def test_bool_default_skips_range_check() -> None:
    assert Param(True, min=5) is not None


def test_no_params_has_no_fields() -> None:
    assert param_specs(NoParams) == ()


def test_param_specs_requires_frozen_dataclass_and_param_fields() -> None:
    @dataclass
    class NotFrozen:
        a: int = Param(1)

    @dataclass(frozen=True)
    class PlainField:
        a: int = 1

    class NotDataclass:
        pass

    with pytest.raises(TypeError, match="frozen dataclass"):
        param_specs(NotFrozen)
    with pytest.raises(TypeError, match="frozen dataclass"):
        param_specs(NotDataclass)
    with pytest.raises(TypeError, match=r"PlainField\.a must be declared with Param"):
        param_specs(PlainField)


# ---- port ---------------------------------------------------------------------------


def test_port_defaults_and_dicts() -> None:
    p = port("spectra", "Spectra")
    assert p == Port("spectra", "Spectra", required=True, multiple=False)
    assert p.to_dict("input") == {
        "port_id": "spectra",
        "port_type": "Spectra",
        "required": True,
        "multiple": False,
    }
    assert p.to_dict("output") == {"port_id": "spectra", "port_type": "Spectra"}


def test_port_optional_fields_appear_when_set() -> None:
    p = port("slave", "Spectra", requires=("y",), rows_match="master", axis_match="master")
    assert p.to_dict("input") == {
        "port_id": "slave",
        "port_type": "Spectra",
        "required": True,
        "multiple": False,
        "requires": ["y"],
        "rows_match": "master",
        "axis_match": "master",
    }
    m = port("model", "Model", refit_per_fold=True, required=False, multiple=True)
    assert m.to_dict("input")["refit_per_fold"] is True
    assert m.to_dict("input")["required"] is False


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"port_id": "Spectra", "port_type": "Spectra"}, "snake_case"),
        ({"port_id": "x", "port_type": "Any"}, "unknown port type"),
        ({"port_id": "x", "port_type": "Spectra", "requires": ("labels",)}, "unknown requires"),
        ({"port_id": "x", "port_type": "Spectra", "refit_per_fold": True}, "refit_per_fold"),
    ],
)
def test_port_rejects_invalid_declarations(kwargs: dict[str, Any], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        port(**kwargs)


# ---- State --------------------------------------------------------------------------


def test_state_arrays_are_read_only_copies() -> None:
    source = np.array([1.0, 2.0])
    state = State({"k": 1}, {"mean": source})
    source[0] = 99.0
    assert state.arrays["mean"][0] == 1.0
    assert not state.arrays["mean"].flags.writeable
    with pytest.raises(TypeError):
        state.arrays["other"] = source  # type: ignore[index]
    with pytest.raises(TypeError):
        state.values["k"] = 2  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        state.values = {}  # type: ignore[misc]


def test_state_defaults_to_empty() -> None:
    state = State()
    assert dict(state.values) == {}
    assert dict(state.arrays) == {}


def test_state_rejects_object_arrays() -> None:
    with pytest.raises(TypeError, match="dtype object"):
        State(arrays={"bad": np.array([{"a": 1}], dtype=object)})


# ---- metadata -----------------------------------------------------------------------


def test_metadata_of_dummy_blocks() -> None:
    meta = DummyOffset.metadata()
    assert meta.block_class == "testing"
    assert meta.tier == "P0"
    assert meta.title_key == "blocks.testing.offset.title"
    assert meta.params == (("offset", param_specs(DummyOffsetParams)[0][1]),)
    assert DummyCenter.metadata().to_dict() == {
        "block_id": "testing.center",
        "version": "1.0.0",
        "block_class": "testing",
        "title_key": "blocks.testing.center.title",
        "tooltip_key": "blocks.testing.center.tip",
        "icon": "glyph-dummy",
        "fitted": True,
        "tier": "P1",
        "references": [],
        "inputs": [
            {"port_id": "spectra", "port_type": "Spectra", "required": True, "multiple": False}
        ],
        "outputs": [
            {"port_id": "spectra", "port_type": "Spectra"},
            {"port_id": "transform", "port_type": "Transform"},
        ],
    }


class _Valid(Block):
    block_id = "preprocess.valid"
    version = "1.2.3"
    icon = "glyph-x"
    fitted = False
    inputs: ClassVar[tuple[Port, ...]] = (port("a", "Spectra"), port("b", "Spectra"))
    outputs: ClassVar[tuple[Port, ...]] = (port("out", "Spectra"),)

    def apply(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        return None


def _variant(**attrs: Any) -> type[Block]:
    return type("Variant", (_Valid,), attrs)


def test_valid_block_and_block_class_override() -> None:
    assert _Valid.metadata().block_class == "preprocess"
    assert _variant(block_class="explore").metadata().block_class == "explore"
    assert _variant(references=("barnes1989snv",)).metadata().references == ("barnes1989snv",)


@pytest.mark.parametrize(
    ("attrs", "error", "match"),
    [
        ({"block_id": "snv"}, ValueError, "block_id"),
        ({"block_id": "Pre.snv"}, ValueError, "block_id"),
        ({"version": "1.0"}, ValueError, "semantic version"),
        ({"version": "01.0.0"}, ValueError, "semantic version"),
        ({"icon": ""}, ValueError, "icon"),
        ({"fitted": 1}, TypeError, "fitted must be a bool"),
        ({"tier": "P3"}, ValueError, "tier"),
        ({"block_class": "Pre-process"}, ValueError, "block_class"),
        ({"references": ["a"]}, TypeError, "references"),
        ({"references": ("",)}, TypeError, "references"),
        ({"inputs": [port("a", "Spectra")]}, TypeError, "inputs must be a tuple"),
        ({"outputs": ("out",)}, TypeError, "outputs must be a tuple"),
        ({"inputs": (port("a", "Spectra"), port("a", "Table"))}, ValueError, "duplicate"),
        ({"inputs": (port("a", "Spectra", rows_match="z"),)}, ValueError, "unknown input"),
        ({"inputs": (port("a", "Spectra", axis_match="a"),)}, ValueError, "unknown input"),
        ({"outputs": (port("out", "Spectra", required=False),)}, ValueError, "only set port_id"),
        ({"params_type": dict}, TypeError, "frozen dataclass"),
        ({"fitted": True}, TypeError, "fit must be implemented"),
    ],
)
def test_metadata_rejects_definition_mistakes(
    attrs: dict[str, Any], error: type[Exception], match: str
) -> None:
    with pytest.raises(error, match=match):
        _variant(**attrs).metadata()


def test_metadata_requires_every_attribute_and_apply() -> None:
    class Missing(Block):
        block_id = "preprocess.missing"

    class NoApply(Block):
        block_id = "preprocess.no_apply"
        version = "1.0.0"
        icon = "glyph-x"
        fitted = False
        inputs = ()
        outputs = ()

    class FitWithoutFitted(_Valid):
        def fit(self, *args: Any, **kwargs: Any) -> State:  # noqa: ARG002
            return State()

    with pytest.raises(TypeError, match="Missing must define version"):
        Missing.metadata()
    with pytest.raises(TypeError, match="must implement apply"):
        NoApply.metadata()
    with pytest.raises(TypeError, match="fit must be implemented"):
        FitWithoutFitted.metadata()


def test_matching_another_input_is_allowed() -> None:
    meta = _variant(
        inputs=(port("a", "Spectra"), port("b", "Spectra", rows_match="a", axis_match="a"))
    ).metadata()
    assert meta.inputs[1].rows_match == "a"


# ---- error codes (Done when: match DATA_MODEL.md §7) --------------------------------


def _catalogue_codes(module: str) -> set[str]:
    """Codes that DATA_MODEL.md §7 lists as defined in ``module``."""
    data_model = Path(__file__).resolve().parents[3] / "docs" / "DATA_MODEL.md"
    section = data_model.read_text(encoding="utf-8").split("## 7. Error codes catalogue")[1]
    rows = (line.split("|") for line in section.splitlines() if line.startswith("| `"))
    return {r[1].strip(" `") for r in rows if r[3].strip(" `") == module}


def test_block_error_codes_match_the_catalogue() -> None:
    defined = {
        value
        for name, value in vars(block_module).items()
        if name.startswith("BLOCK_") and isinstance(value, str)
    }
    assert defined == _catalogue_codes("core/block")
    assert defined == {
        "BLOCK_INPUT_REQUIREMENT_MISSING",
        "BLOCK_INPUT_ROWS_MISMATCH",
        "BLOCK_INPUT_AXIS_MISMATCH",
    }
    for name in defined:
        assert getattr(block_module, name) == name
        assert message_key(name).startswith("errors.block.input_")

# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/test_block.py
"""Tests for ``vibechem_core.block``: Param, port, State, Block metadata, fit/apply."""

import json
import pickle
from dataclasses import FrozenInstanceError, dataclass, make_dataclass
from pathlib import Path
from typing import Any, ClassVar, cast

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from vibechem_core import block as block_module
from vibechem_core.block import (
    BLOCK_PARAM_INVALID,
    Block,
    NoParams,
    Param,
    ParamSpec,
    Port,
    State,
    load_state,
    param_specs,
    parse_params,
    port,
    save_state,
)
from vibechem_core.data import Axis, SpectralDataset
from vibechem_core.errors import ParamError, message_key
from vibechem_core.testing import (
    DummyCenter,
    DummyOffset,
    DummyOffsetParams,
    DummySchema,
    DummySchemaParams,
)


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
        ({"default": float("nan"), "min": 0.0}, "default must be finite"),
        ({"default": 5, "min": float("nan")}, "min must be finite"),
        ({"default": 5, "max": float("inf")}, "max must be finite"),
        ({"default": True, "choices": (0, 1)}, "not one of the choices"),
    ],
)
def test_param_rejects_inconsistent_declarations(kwargs: dict[str, Any], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        Param(**kwargs)


def test_range_is_only_for_numbers() -> None:
    # Changed in T1.03: DATA_MODEL.md §5.1 allows min/max only for int and float.
    with pytest.raises(ValueError, match="only allowed for int and float"):
        Param(True, min=5)


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


def test_state_values_are_deep_copied_json() -> None:
    lv = [1, 2]
    nested = {"lv": lv, "info": {"name": "pls"}}
    state = State({"nested": nested, "x": np.float64(0.5), "t": (1, None)})
    lv.append(3)
    assert state.values["nested"] == {"lv": [1, 2], "info": {"name": "pls"}}
    assert state.values["t"] == [1, None]
    assert type(state.values["x"]) is float


@pytest.mark.parametrize(
    ("value", "match"),
    [
        (object(), "is a object, not JSON"),
        (np.int64(1), "is a int64, not JSON"),
        (float("nan"), "not finite"),
        ({1: "a"}, "non-string keys"),
        ([np.zeros(2)], r"'v\[0\]' is a ndarray"),
    ],
)
def test_state_rejects_values_that_are_not_json(value: Any, match: str) -> None:
    with pytest.raises(TypeError, match=match):
        State({"v": value})


def test_state_pickles_in_memory_for_worker_processes() -> None:
    state = State({"k": [1]}, {"m": np.array([1.0, 2.0])})
    copy = pickle.loads(pickle.dumps(state))
    assert dict(copy.values) == {"k": [1]}
    np.testing.assert_array_equal(copy.arrays["m"], [1.0, 2.0])
    assert not copy.arrays["m"].flags.writeable


def test_state_rejects_object_arrays() -> None:
    with pytest.raises(TypeError, match="dtype object"):
        State(arrays={"bad": np.array([{"a": 1}], dtype=object)})


# ---- State save / load (T1.02b, Done when) ------------------------------------------


def assert_same_state(actual: State, expected: State) -> None:
    assert dict(actual.values) == dict(expected.values)
    assert list(actual.arrays) == list(expected.arrays)
    for name, array in expected.arrays.items():
        loaded = actual.arrays[name]
        assert loaded.dtype == array.dtype, name
        assert loaded.shape == array.shape, name
        np.testing.assert_array_equal(loaded, array)
        assert not loaded.flags.writeable


def test_fitted_dummy_block_round_trips_state(tmp_path: Path) -> None:
    data = make_dataset([[1.0, 10.0], [3.0, 30.0], [100.0, 100.0]])
    block = DummyCenter()
    state = block.fit(spectra=data.subset([0, 1]), params=NoParams())
    save_state(state, tmp_path / "center")
    loaded = load_state(tmp_path / "center")
    assert_same_state(loaded, state)
    out = block.apply(spectra=data, params=NoParams(), state=loaded)
    np.testing.assert_array_equal(out.X, [[-1.0, -10.0], [1.0, 10.0], [98.0, 80.0]])


def test_stateless_dummy_block_has_empty_state_that_round_trips(tmp_path: Path) -> None:
    save_state(State(), tmp_path)
    loaded = load_state(tmp_path)
    assert_same_state(loaded, State())
    out = DummyOffset().apply(spectra=make_dataset([[1.0]]), params=DummyOffsetParams(2.0))
    np.testing.assert_array_equal(out.X, [[3.0]])


def test_state_round_trip_keeps_values_dtypes_shapes_and_names(tmp_path: Path) -> None:
    values = {"n": 2**62, "flag": True, "zero": 0, "x": 0.1, "none": None, "s": "ü/é"}
    values |= {"nested": {"lv": [1, 2.5, [False]], "info": {}}}
    arrays = {
        "mean": np.array([1.0, 2.0]),
        "X_fit_": np.asfortranarray(np.arange(6, dtype=np.int32).reshape(2, 3)),
        "Mean": np.float32(3.5),  # 0-d; differs from "mean" only by case
        "a/../b": np.array([True, False]),  # names never become file names
        "big_endian": np.array([1.5, -2.0], dtype=">f8"),
        "complex": np.array([1 + 2j]),
        "text": np.array(["ab", "cde"]),
        "empty": np.zeros((0, 4)),
    }
    state = State(values, arrays)
    save_state(state, tmp_path)
    loaded = load_state(tmp_path)
    assert_same_state(loaded, state)
    assert type(loaded.values["flag"]) is bool
    assert type(loaded.values["zero"]) is int


def test_state_files_are_json_and_npy_without_pickle(tmp_path: Path) -> None:
    save_state(State({"k": 1}, {"m": np.array([1.0, 2.0])}), tmp_path)
    assert sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*.*")) == [
        "arrays/0.npy",
        "state.json",
    ]
    doc = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert doc == {"state_version": 1, "values": {"k": 1}, "arrays": ["m"]}
    np.testing.assert_array_equal(
        np.load(tmp_path / "arrays" / "0.npy", allow_pickle=False), [1, 2]
    )


def write_state_json(directory: Path, text: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "state.json").write_text(text, encoding="utf-8")


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("{not json", "state.json is not valid JSON"),
        ('{"state_version": 1, "values": {"x": NaN}, "arrays": []}', "NaN is not JSON"),
        ("[]", "must be a JSON object"),
        ('{"state_version": 2, "values": {}, "arrays": []}', "state_version 2"),
        ('{"values": {}, "arrays": []}', "state_version None"),
        ('{"state_version": 1, "values": [], "arrays": []}', "'values' must be an object"),
        ('{"state_version": 1, "values": {}, "arrays": [1]}', "'arrays' must be a list of str"),
        ('{"state_version": 1, "values": {}, "arrays": ["a", "a"]}', "duplicate"),
        ('{"state_version": 1, "values": {}, "arrays": [], "x": 1}', "unknown keys"),
        ('{"state_version": 1.0, "values": {}, "arrays": []}', "state_version 1.0"),
        ('{"state_version": true, "values": {}, "arrays": []}', "state_version True"),
        ('{"state_version": 1, "values": {"x": 1e400}, "arrays": []}', "1e400 is not finite"),
        (
            '{"state_version": 1, "arrays": [], "values": {"x": '
            + "[" * 100_000
            + "]" * 100_000
            + "}}",
            "nested too deeply",
        ),
    ],
)
def test_load_state_rejects_invalid_state_json(tmp_path: Path, text: str, match: str) -> None:
    write_state_json(tmp_path, text)
    with pytest.raises(ValueError, match=match):
        load_state(tmp_path)


def test_load_state_never_unpickles(tmp_path: Path) -> None:
    write_state_json(tmp_path, '{"state_version": 1, "values": {}, "arrays": ["bad"]}')
    (tmp_path / "arrays").mkdir()
    np.save(tmp_path / "arrays" / "0.npy", np.array([{"a": 1}], dtype=object), allow_pickle=True)
    with pytest.raises(ValueError, match="allow_pickle=False"):
        load_state(tmp_path)


def test_load_state_rejects_npz_in_place_of_npy(tmp_path: Path) -> None:
    write_state_json(tmp_path, '{"state_version": 1, "values": {}, "arrays": ["m"]}')
    (tmp_path / "arrays").mkdir()
    with (tmp_path / "arrays" / "0.npy").open("wb") as f:
        np.savez(f, m=np.zeros(2))
    with pytest.raises(ValueError, match=r"arrays/0.npy is not a \.npy array"):
        load_state(tmp_path)


def test_load_state_rejects_empty_npy(tmp_path: Path) -> None:
    write_state_json(tmp_path, '{"state_version": 1, "values": {}, "arrays": ["m"]}')
    (tmp_path / "arrays").mkdir()
    (tmp_path / "arrays" / "0.npy").write_bytes(b"")
    with pytest.raises(ValueError, match=r"arrays/0.npy is empty"):
        load_state(tmp_path)


def test_save_state_refuses_a_directory_that_holds_a_state(tmp_path: Path) -> None:
    save_state(State(arrays={"a": [1], "b": [2]}), tmp_path / "one")
    with pytest.raises(FileExistsError):
        save_state(State(arrays={"a": [3]}), tmp_path / "one")
    (tmp_path / "two" / "arrays").mkdir(parents=True)  # stale arrays without state.json
    with pytest.raises(FileExistsError):
        save_state(State(), tmp_path / "two")
    assert list(load_state(tmp_path / "one").arrays) == ["a", "b"]


def test_state_rejects_non_string_array_names() -> None:
    with pytest.raises(TypeError, match="state array name 1 must be a str"):
        State(arrays={1: [0.0]})  # type: ignore[dict-item]


def test_load_state_reports_missing_files(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_state(tmp_path)
    write_state_json(tmp_path, '{"state_version": 1, "values": {}, "arrays": ["m"]}')
    with pytest.raises(FileNotFoundError):
        load_state(tmp_path)


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
        ({"inputs": (port("a", "Spectra", rows_match="z"),)}, ValueError, "another single input"),
        ({"inputs": (port("a", "Spectra", axis_match="a"),)}, ValueError, "another single input"),
        (
            {"inputs": (port("a", "Spectra", multiple=True), port("b", "Spectra", rows_match="a"))},
            ValueError,
            "another single input",
        ),
        ({"block_class": ""}, ValueError, "block_class"),
        ({"block_class": 5}, ValueError, "block_class"),
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
        "BLOCK_PARAM_INVALID",
    }
    for name in defined:
        assert getattr(block_module, name) == name
        assert message_key(name).startswith("errors.block.")


# ---- parameter schema (T1.03, DATA_MODEL.md §5) --------------------------------------


def test_schema_types_follow_the_default_or_choices() -> None:
    types = {name: spec.type for name, spec in param_specs(DummySchemaParams)}
    assert types == {
        "window": "int",
        "polyorder": "int",
        "scale": "float",
        "mode": "enum",
        "deriv": "enum",
        "clip": "bool",
        "label": "string",
    }


def _detail_params(block: type[Block]) -> list[dict[str, Any]]:
    detail = block.metadata().to_detail_dict()
    return cast(list[dict[str, Any]], detail["params"])


def test_param_entry_has_optional_fields_only_when_set() -> None:
    params = {p["param_id"]: p for p in _detail_params(DummySchema)}
    assert params["window"] == {
        "param_id": "window",
        "type": "int",
        "default": 15,
        "min": 5,
        "max": 101,
        "odd_only": True,
        "unit": "points",
        "label_key": "blocks.testing.schema.params.window",
        "tooltip_key": "blocks.testing.schema.params.window.tip",
        "advanced": False,
    }
    assert params["polyorder"]["constraint"] == "polyorder < window"
    assert params["deriv"]["choices"] == [0, 1, 2]
    assert params["label"]["visible_if"] == {"param_id": "mode", "values": ["median"]}
    assert params["clip"] == {
        "param_id": "clip",
        "type": "bool",
        "default": False,
        "label_key": "blocks.testing.schema.params.clip",
        "tooltip_key": "blocks.testing.schema.params.clip.tip",
        "advanced": False,
    }
    assert params["scale"]["advanced"] is True


def test_explicit_translation_keys_are_kept() -> None:
    params = {p["param_id"]: p for p in _detail_params(_variant(params_type=_Params))}
    assert params["ddof"]["tooltip_key"] == "tip"
    assert params["ddof"]["label_key"] == "blocks.preprocess.valid.params.ddof"


def test_detail_dict_is_the_list_entry_plus_params_and_help() -> None:
    meta = DummyOffset.metadata()
    detail = meta.to_detail_dict()
    assert {k: v for k, v in detail.items() if k in meta.to_dict()} == meta.to_dict()
    assert detail["params"] == [
        {
            "param_id": "offset",
            "type": "float",
            "default": 0.0,
            "min": -1e6,
            "max": 1e6,
            "label_key": "blocks.testing.offset.params.offset",
            "tooltip_key": "blocks.testing.offset.params.offset.tip",
            "advanced": False,
        }
    ]
    assert detail["references"] == []
    assert detail["implementation"] == {
        "library": "vibechem",
        "function": "vibechem_core.testing.DummyOffset",
    }
    assert detail["help_key"] == "blocks.testing.offset.help"
    assert detail["custom_panel"] is None
    assert DummyCenter.metadata().to_detail_dict()["params"] == []
    json.dumps(DummySchema.metadata().to_detail_dict(), allow_nan=False)  # plain JSON


def test_implementation_and_custom_panel_overrides() -> None:
    block = _variant(implementation=("scipy", "scipy.signal.savgol_filter"), custom_panel="roi")
    detail = block.metadata().to_detail_dict()
    assert detail["implementation"] == {
        "library": "scipy",
        "function": "scipy.signal.savgol_filter",
    }
    assert detail["custom_panel"] == "roi"


@pytest.mark.parametrize(
    "attrs",
    [
        {"implementation": ("scipy",)},
        {"implementation": ("", "f")},
        {"implementation": ()},
        {"custom_panel": ""},
    ],
)
def test_implementation_and_custom_panel_are_checked(attrs: dict[str, Any]) -> None:
    with pytest.raises(TypeError, match=r"implementation|custom_panel"):
        _variant(**attrs).metadata()


@pytest.mark.parametrize(
    ("kwargs", "error", "match"),
    [
        ({"default": None}, TypeError, "int, float, bool or str"),
        ({"default": [1]}, TypeError, "int, float, bool or str"),
        ({"default": "a", "unit": "nm"}, ValueError, "only allowed for int and float"),
        ({"default": 1, "choices": (1, 2), "min": 0}, ValueError, "only allowed for int"),
        ({"default": 1.0, "odd_only": True}, ValueError, "odd_only"),
        ({"default": 4, "odd_only": True}, ValueError, "not odd"),
        ({"default": 1, "choices": (1, 1.5)}, ValueError, "type of the default"),
        ({"default": 1, "choices": (1, 1)}, ValueError, "duplicates"),
        ({"default": 1, "unit": ""}, ValueError, "unit"),
        ({"default": 1, "constraint": "a<b"}, ValueError, "constraint"),
        ({"default": 1, "constraint": "a == b"}, ValueError, "constraint"),
        ({"default": 1, "visible_if": ("m", ())}, ValueError, "visible_if"),
        ({"default": 1, "visible_if": ("Mode", (1,))}, ValueError, "visible_if"),
    ],
)
def test_param_rejects_schema_mistakes(
    kwargs: dict[str, Any], error: type[Exception], match: str
) -> None:
    with pytest.raises(error, match=match):
        Param(**kwargs)


def _params_class(**fields: tuple[Any, Any]) -> type[Any]:
    """A frozen params dataclass built from ``name=(annotation, Param(...))``."""
    spec = [(name, ann, value) for name, (ann, value) in fields.items()]
    return make_dataclass("P", spec, frozen=True)


@pytest.mark.parametrize(
    ("fields", "error", "match"),
    [
        ({"a": (float, Param(1))}, TypeError, "annotated float but its default is 1"),
        ({"a": (int, Param(1.0))}, TypeError, "annotated int"),
        ({"a": (int, Param(1, constraint="b < 2"))}, ValueError, "must start with 'a'"),
        ({"a": (int, Param(1, constraint="a < b"))}, ValueError, "another int or float"),
        ({"a": (int, Param(1, constraint="a < a"))}, ValueError, "another int or float"),
        (
            {"a": (int, Param(1, constraint="a < b")), "b": (str, Param("x"))},
            ValueError,
            "another int or float",
        ),
        (
            {"a": (int, Param(3, constraint="a < b")), "b": (int, Param(2))},
            ValueError,
            "defaults break the constraint",
        ),
        ({"a": (int, Param(1, visible_if=("b", (True,))))}, ValueError, "bool or enum"),
        (
            {"a": (int, Param(1, visible_if=("b", (True,)))), "b": (int, Param(1))},
            ValueError,
            "bool or enum",
        ),
        (
            {"a": (int, Param(1, visible_if=("b", (1,)))), "b": (bool, Param(True))},
            ValueError,
            "not valid for 'b'",
        ),
    ],
)
def test_param_specs_checks_references_and_annotations(
    fields: dict[str, tuple[Any, Any]], error: type[Exception], match: str
) -> None:
    with pytest.raises(error, match=match):
        param_specs(_params_class(**fields))


def test_constraint_with_a_number_and_string_annotations() -> None:
    p = _params_class(a=("int", Param(1, constraint="a <= 2.5e0")))  # string annotation
    assert dict(param_specs(p))["a"].constraint == "a <= 2.5e0"
    assert parse_params(p, {"a": 2}) == p(a=2)
    with pytest.raises(ParamError) as exc:
        parse_params(p, {"a": 3})
    assert exc.value.params["reason"] == "constraint"


# ---- parse_params (DATA_MODEL.md §5.3) -----------------------------------------------


def test_parse_params_fills_defaults_and_accepts_valid_values() -> None:
    assert parse_params(DummySchemaParams, {}) == DummySchemaParams()
    values = {
        "window": 21,
        "polyorder": 3,
        "scale": 2,
        "mode": "median",
        "deriv": 1,
        "clip": True,
        "label": "x",
    }
    parsed = parse_params(DummySchemaParams, values)
    assert parsed == DummySchemaParams(21, 3, 2.0, "median", 1, True, "x")
    assert type(parsed.scale) is float  # JSON integer stored as float
    assert parse_params(NoParams, {}) == NoParams()


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ({"size": 3}, {"param_id": "size", "reason": "unknown"}),
        ({"window": 15.0}, {"param_id": "window", "reason": "type", "value": 15.0}),
        ({"window": True}, {"param_id": "window", "reason": "type", "value": True}),
        ({"window": "15"}, {"param_id": "window", "reason": "type", "value": "15"}),
        ({"scale": "1"}, {"param_id": "scale", "reason": "type", "value": "1"}),
        ({"scale": True}, {"param_id": "scale", "reason": "type", "value": True}),
        ({"scale": float("nan")}, {"param_id": "scale", "reason": "type"}),
        ({"scale": 10**400}, {"param_id": "scale", "reason": "type", "value": 10**400}),
        ({"scale": [1]}, {"param_id": "scale", "reason": "type"}),
        ({"clip": 1}, {"param_id": "clip", "reason": "type", "value": 1}),
        ({"label": None}, {"param_id": "label", "reason": "type"}),
        ({"window": 3}, {"param_id": "window", "reason": "below_min", "value": 3}),
        ({"window": 103}, {"param_id": "window", "reason": "above_max", "value": 103}),
        ({"scale": -0.5}, {"param_id": "scale", "reason": "below_min", "value": -0.5}),
        ({"window": 17.5}, {"param_id": "window", "reason": "type", "value": 17.5}),
        ({"window": 16}, {"param_id": "window", "reason": "not_odd", "value": 16}),
        ({"mode": "max"}, {"param_id": "mode", "reason": "not_a_choice", "value": "max"}),
        ({"deriv": True}, {"param_id": "deriv", "reason": "not_a_choice", "value": True}),
        ({"deriv": 1.0}, {"param_id": "deriv", "reason": "not_a_choice", "value": 1.0}),
        (
            {"window": 5, "polyorder": 5},
            {"param_id": "polyorder", "reason": "constraint", "constraint": "polyorder < window"},
        ),
    ],
)
def test_parse_params_reports_the_first_problem(
    values: dict[str, Any], expected: dict[str, Any]
) -> None:
    with pytest.raises(ParamError) as exc:
        parse_params(DummySchemaParams, values)
    assert exc.value.code == BLOCK_PARAM_INVALID
    assert exc.value.message_key == "errors.block.param_invalid"
    assert dict(exc.value.params) == expected


def test_float_choices_accept_json_integers() -> None:
    p = _params_class(a=(float, Param(0.5, choices=(0.5, 1.0))))
    parsed = parse_params(p, {"a": 1})  # JSON.stringify(1.0) == "1"
    assert parsed == p(a=1.0)
    assert type(parsed.a) is float
    with pytest.raises(ParamError, match="not_a_choice"):
        parse_params(p, {"a": True})


def test_params_must_be_an_object() -> None:
    with pytest.raises(ParamError) as exc:
        parse_params(DummySchemaParams, cast(Any, []))
    assert dict(exc.value.params) == {"reason": "type"}


def test_hidden_parameters_are_still_validated() -> None:
    with pytest.raises(ParamError, match="label"):
        parse_params(DummySchemaParams, {"mode": "mean", "label": 5})


@given(window=st.integers(-10, 120), polyorder=st.integers(-2, 10))
def test_parse_params_accepts_exactly_the_valid_int_values(window: int, polyorder: int) -> None:
    valid = 5 <= window <= 101 and window % 2 == 1 and 0 <= polyorder <= 6 and polyorder < window
    try:
        parsed = parse_params(DummySchemaParams, {"window": window, "polyorder": polyorder})
    except ParamError:
        assert not valid
    else:
        assert valid
        assert (parsed.window, parsed.polyorder) == (window, polyorder)

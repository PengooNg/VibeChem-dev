# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/formats/test_model.py
"""Model package v1: round trip and rejection of unsafe or invalid zips (DATA_MODEL.md §6.4)."""

from __future__ import annotations

import copy
import io
import json
import pickle
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from vibechem_core.block import State
from vibechem_engine.formats import (
    FormatError,
    ModelManifest,
    ModelPackage,
    read_model,
    write_model,
)

PIPELINE: dict[str, Any] = {
    "format_version": 1,
    "pipeline_id": "ppl_01JD8V",
    "name": "NIR SNV",
    "revision": 0,
    "nodes": [
        {"node_id": "nd_b", "block_id": "preprocess.snv", "block_version": "1.0.0",
         "params": {}, "position": {"x": 0.0, "y": 0.0}, "label": None},
    ],
    "edges": [],
    "created_at": "2026-11-17T05:45:00Z",
    "updated_at": "2026-11-17T05:45:00Z",
}  # fmt: skip
MANIFEST: dict[str, Any] = {
    "format_version": 1,
    "name": "honey_pls_v3",
    "vibechem_version": "1.0.0",
    "trained_at": "2026-11-17T06:10:00Z",
    "pipeline": PIPELINE,
    "states": [{"node_id": "nd_b", "block_id": "preprocess.snv", "block_version": "1.0.0"}],
}
STATE = State(
    {"n_lv": 3, "algorithm": "nipals"}, {"W": np.arange(6.0).reshape(3, 2), "mean": [1.5]}
)


def package() -> ModelPackage:
    return ModelPackage(ModelManifest.model_validate_json(json.dumps(MANIFEST)), [STATE])


def test_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "m.vcm"
    write_model(package(), path)
    back = read_model(path)
    assert back.manifest == package().manifest
    assert dict(back.states[0].values) == dict(STATE.values)
    assert list(back.states[0].arrays) == ["W", "mean"]
    for name, array in STATE.arrays.items():
        np.testing.assert_array_equal(back.states[0].arrays[name], array)
    assert sorted(zipfile.ZipFile(path).namelist()) == [
        "manifest.json",
        "states/0/arrays/0.npy",
        "states/0/arrays/1.npy",
        "states/0/state.json",
    ]


def zip_with(tmp_path: Path, entries: dict[str, bytes], manifest: object = MANIFEST) -> Path:
    path = tmp_path / "bad.vcm"
    with zipfile.ZipFile(path, "w") as zf:
        if manifest is not None:
            zf.writestr("manifest.json", json.dumps(manifest))
        for name, data in entries.items():
            zf.writestr(name, data)
    return path


def npy(array: np.ndarray[Any, Any], *, allow_pickle: bool = False) -> bytes:
    buffer = io.BytesIO()
    np.save(buffer, array, allow_pickle=allow_pickle)
    return buffer.getvalue()


GOOD_STATE = {
    "states/0/state.json": json.dumps({"state_version": 1, "values": {}, "arrays": ["a"]}).encode(),
    "states/0/arrays/0.npy": npy(np.zeros(2)),
}


def params_of(path: Path) -> dict[str, Any]:
    with pytest.raises(FormatError) as info:
        read_model(path)
    assert info.value.code == "MODEL_PACKAGE_INVALID"
    return dict(info.value.params)


def test_hand_built_zip_is_read(tmp_path: Path) -> None:
    states = read_model(zip_with(tmp_path, GOOD_STATE)).states
    np.testing.assert_array_equal(states[0].arrays["a"], np.zeros(2))


@pytest.mark.parametrize(
    "entry",
    [
        "../evil.json",
        "states/0/../../evil",
        "/abs.json",
        "states/0/arrays/x.pkl",
        "states/1/state.json",
        "states/00/state.json",
        "states/٣/state.json",
    ],
)
def test_rejects_unexpected_entries(tmp_path: Path, entry: str) -> None:
    params = params_of(zip_with(tmp_path, {**GOOD_STATE, entry: b"{}"}))
    assert params == {"reason": "entry", "entry": entry}


def test_rejects_missing_manifest(tmp_path: Path) -> None:
    assert params_of(zip_with(tmp_path, GOOD_STATE, manifest=None))["reason"] == "entry"


def test_rejects_pickled_array(tmp_path: Path) -> None:
    entries = {
        **GOOD_STATE,
        "states/0/arrays/0.npy": npy(np.array([{"a": 1}], dtype=object), allow_pickle=True),
    }
    params = params_of(zip_with(tmp_path, entries))
    assert params["reason"] == "state"
    assert params["index"] == 0


def test_rejects_missing_state(tmp_path: Path) -> None:
    assert params_of(zip_with(tmp_path, {}))["reason"] == "state"


def test_rejects_not_a_zip(tmp_path: Path) -> None:
    path = tmp_path / "m.vcm"
    path.write_bytes(pickle.dumps({"a": 1}))
    assert params_of(path)["reason"] == "zip"


def test_rejects_too_large(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vibechem_engine.formats.model.MAX_MODEL_BYTES", 100)
    assert params_of(zip_with(tmp_path, GOOD_STATE))["reason"] == "too_large"


@pytest.mark.parametrize(
    ("change", "location"),
    [
        ({"block_version": "2.0.0"}, ""),
        ({"node_id": "nd_zz"}, ""),
    ],
)
def test_manifest_states_must_match_nodes(
    tmp_path: Path, change: dict[str, str], location: str
) -> None:
    manifest = copy.deepcopy(MANIFEST)
    manifest["states"][0].update(change)
    params = params_of(zip_with(tmp_path, GOOD_STATE, manifest))
    assert params["reason"] == "schema"
    assert params["location"] == location


def test_package_needs_one_state_per_entry() -> None:
    with pytest.raises(ValueError, match="1 manifest entries"):
        ModelPackage(package().manifest, [])


def test_rejects_extra_array_file(tmp_path: Path) -> None:
    params = params_of(zip_with(tmp_path, {**GOOD_STATE, "states/0/arrays/1.npy": npy(np.ones(1))}))
    assert params["reason"] == "state"


def test_rejects_array_header_larger_than_data(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    header = {"descr": "<f8", "fortran_order": False, "shape": (40_000_000_000,)}
    np.lib.format.write_array_header_1_0(buffer, header)  # type: ignore[no-untyped-call]
    entries = {**GOOD_STATE, "states/0/arrays/0.npy": buffer.getvalue() + bytes(8)}
    params = params_of(zip_with(tmp_path, entries))
    assert params["reason"] == "state"
    assert "shape" in str(params["detail"])


@pytest.mark.parametrize("flag", [0x20, 0x40])
def test_rejects_unsupported_zip_flags(tmp_path: Path, flag: int) -> None:
    path = zip_with(tmp_path, GOOD_STATE)
    data = bytearray(path.read_bytes())
    at = data.index(b"PK") + 8  # flag bits of the first central directory entry
    data[at] |= flag
    path.write_bytes(bytes(data))
    assert params_of(path)["reason"] == "zip"


def test_rejects_long_state_index(tmp_path: Path) -> None:
    entry = f"states/{'9' * 5000}/state.json"
    assert params_of(zip_with(tmp_path, {**GOOD_STATE, entry: b"{}"}))["reason"] == "entry"


def test_embedded_pipeline_version_error_names_pipeline(tmp_path: Path) -> None:
    manifest = copy.deepcopy(MANIFEST)
    manifest["pipeline"]["format_version"] = 3
    params = params_of(zip_with(tmp_path, GOOD_STATE, manifest))
    assert params == {"reason": "version", "found": 3, "supported": 1, "location": "pipeline"}

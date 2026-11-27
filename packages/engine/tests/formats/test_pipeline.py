# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/formats/test_pipeline.py
"""Pipeline file v1: round trip, schema rejections, migrations (DATA_MODEL.md §6.3, §6.5)."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

import pytest

from vibechem_engine import formats
from vibechem_engine.formats import FormatError, PipelineFile, load_pipeline, save_pipeline
from vibechem_engine.formats import migrations as mig

SCHEMA_DIR = Path(formats.__file__).parent / "schemas"

PIPELINE: dict[str, Any] = {
    "format_version": 1,
    "pipeline_id": "ppl_01JD8V",
    "name": "NIR PLS – nested CV",
    "revision": 12,
    "nodes": [
        {"node_id": "nd_a", "block_id": "data.dataset", "block_version": "1.0.0",
         "params": {"dataset_id": "ds_01JD8T"}, "position": {"x": 80.0, "y": 120.5},
         "label": None},
        {"node_id": "nd_b", "block_id": "preprocess.snv", "block_version": "1.0.0",
         "params": {"ddof": 1, "ranges": [[1100, 1200.5]]}, "position": {"x": 300.0, "y": 120.0},
         "label": "SNV – 日本語"},
    ],
    "edges": [
        {"edge_id": "eg_1", "from_node": "nd_a", "from_port": "spectra",
         "to_node": "nd_b", "to_port": "spectra"},
    ],
    "created_at": "2026-11-17T05:45:00Z",
    "updated_at": "2026-11-17T06:02:31.250Z",
}  # fmt: skip


def write(tmp_path: Path, doc: object) -> Path:
    path = tmp_path / "p.vcp.json"
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return path


def reason_of(path: Path) -> dict[str, Any]:
    with pytest.raises(FormatError) as info:
        load_pipeline(path)
    assert info.value.code == "PIPELINE_FILE_INVALID"
    return dict(info.value.params)


def test_round_trip_keeps_every_field(tmp_path: Path) -> None:
    loaded = load_pipeline(write(tmp_path, PIPELINE))
    assert loaded.model_dump(mode="json") == PIPELINE
    save_pipeline(loaded, tmp_path / "again.vcp.json")
    data = (tmp_path / "again.vcp.json").read_bytes()
    assert load_pipeline(tmp_path / "again.vcp.json") == loaded
    assert b"\r\n" not in data
    assert "日本語".encode() in data
    assert not list(tmp_path.glob("*.tmp"))


def mutated(path: str, value: object) -> dict[str, Any]:
    doc = copy.deepcopy(PIPELINE)
    *parents, last = path.split(".")
    target: Any = doc
    for part in parents:
        target = target[int(part)] if part.isdigit() else target[part]
    if value is KeyError:
        del target[last]
    else:
        target[last] = value
    return doc


@pytest.mark.parametrize(
    ("path", "value", "location"),
    [
        ("name", KeyError, "name"),
        ("extra_key", 1, "extra_key"),
        ("revision", "12", "revision"),
        ("revision", True, "revision"),
        ("revision", -1, "revision"),
        ("nodes.0.node_id", "a", "nodes.0.node_id"),
        ("nodes.0.node_id", "nd_../x", "nodes.0.node_id"),
        ("nodes.0.block_version", "1.0", "nodes.0.block_version"),
        ("nodes.0.position", {"x": 1.0}, "nodes.0.position.y"),
        ("nodes.0.params", [1], "nodes.0.params"),
        ("edges.0.to_port", "Spectra", "edges.0.to_port"),
        ("created_at", "2026-11-17 05:45:00", "created_at"),
        ("nodes.1.node_id", "nd_a", "nodes"),
        ("edges", [PIPELINE["edges"][0], PIPELINE["edges"][0]], "edges"),
        ("edges.0.to_node", "nd_zz", ""),
    ],
)
def test_schema_rejects_invalid_files(
    tmp_path: Path, path: str, value: object, location: str
) -> None:
    params = reason_of(write(tmp_path, mutated(path, value)))
    assert params["reason"] == "schema"
    assert params["location"] == location


@pytest.mark.parametrize(
    "text",
    [b"\xff\xfe", b"{", b"[]", b'{"a": NaN}', b'{"a": 1, "a": 2}'],
)
def test_rejects_non_json(tmp_path: Path, text: bytes) -> None:
    path = tmp_path / "p.vcp.json"
    path.write_bytes(text)
    assert reason_of(path)["reason"] == "json"


def test_rejects_too_large(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vibechem_engine.formats._files.MAX_JSON_BYTES", 10)
    assert reason_of(write(tmp_path, PIPELINE))["reason"] == "too_large"


@pytest.mark.parametrize("version", [2, 0, "1", None])
def test_rejects_unsupported_version(tmp_path: Path, version: object) -> None:
    params = reason_of(write(tmp_path, mutated("format_version", version)))
    assert params == {"reason": "version", "found": version if type(version) is int else None,
                      "supported": 1}  # fmt: skip


def test_example_migration_upgrades_old_files(monkeypatch: pytest.MonkeyPatch) -> None:
    # The example migration of DATA_MODEL.md §6.5: a v2 that renames `label` to `title`.
    monkeypatch.setitem(mig.CURRENT_VERSIONS, "example", 2)
    monkeypatch.setattr(mig, "MIGRATIONS", {})

    @mig.migration("example", 1)
    def _example_1_to_2(doc: dict[str, Any]) -> dict[str, Any]:
        doc["format_version"] = 2
        for node in doc["nodes"]:
            node["title"] = node.pop("label")
        return doc

    upgraded = mig.migrate("example", copy.deepcopy(PIPELINE), "PIPELINE_FILE_INVALID")
    assert upgraded["format_version"] == 2
    assert [n["title"] for n in upgraded["nodes"]] == [None, "SNV – 日本語"]
    with pytest.raises(ValueError, match="already exists"):
        mig.migration("example", 1)(_example_1_to_2)


def test_migration_must_set_the_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(mig.CURRENT_VERSIONS, "example", 2)

    def _forgets_version(doc: dict[str, Any]) -> dict[str, Any]:
        return doc

    monkeypatch.setattr(mig, "MIGRATIONS", {("example", 1): _forgets_version})
    with pytest.raises(RuntimeError, match="did not set format_version"):
        mig.migrate("example", copy.deepcopy(PIPELINE), "PIPELINE_FILE_INVALID")


def test_committed_json_schemas_match_the_models() -> None:
    for name, schema in formats.json_schemas().items():
        path = SCHEMA_DIR / name
        text = json.dumps(schema, indent=1, ensure_ascii=False) + "\n"
        if os.environ.get("VIBECHEM_UPDATE_SCHEMAS") == "1":
            path.write_text(text, encoding="utf-8", newline="\n")
        assert path.read_text(encoding="utf-8") == text, (
            f"{name} is stale: rerun with VIBECHEM_UPDATE_SCHEMAS=1"
        )


def test_model_is_immutable() -> None:
    pipeline = PipelineFile.model_validate_json(json.dumps(PIPELINE))
    with pytest.raises(ValueError, match="frozen"):
        pipeline.name = "x"  # type: ignore[misc]

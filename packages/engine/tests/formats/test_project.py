# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/formats/test_project.py
"""Project manifest v1: round trip and schema rejections (DATA_MODEL.md §6.2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from vibechem_engine.formats import FormatError, load_project, save_project

PROJECT: dict[str, Any] = {
    "format_version": 1,
    "project_id": "prj_01JD8P",
    "name": "Honey NIR adulteration",
    "created_at": "2026-11-17T05:40:12Z",
    "updated_at": "2026-11-17T05:40:12Z",
    "datasets": ["ds_01JD8T"],
    "pipelines": ["ppl_01JD8V", "ppl_01JD9A"],
}


def test_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "project.json"
    path.write_text(json.dumps(PROJECT), encoding="utf-8")
    loaded = load_project(path)
    assert loaded.model_dump(mode="json") == PROJECT
    save_project(loaded, path)
    assert load_project(path) == loaded


@pytest.mark.parametrize(
    ("key", "value", "location"),
    [
        ("path", "somewhere/HoneyNIR.vibechem", "path"),
        ("datasets", ["ds_1", "ds_1"], "datasets"),
        ("pipelines", ["ds_1"], "pipelines.0"),
        ("project_id", "ppl_1", "project_id"),
    ],
)
def test_schema_rejects_invalid_files(
    tmp_path: Path, key: str, value: object, location: str
) -> None:
    path = tmp_path / "project.json"
    path.write_text(json.dumps({**PROJECT, key: value}), encoding="utf-8")
    with pytest.raises(FormatError) as info:
        load_project(path)
    assert info.value.code == "PROJECT_FILE_INVALID"
    assert info.value.params["reason"] == "schema"
    assert info.value.params["location"] == location

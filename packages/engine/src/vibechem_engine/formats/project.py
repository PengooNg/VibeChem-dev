# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/formats/project.py
"""Project manifest ``project.json``, format version 1 (DATA_MODEL.md §6.2).

The manifest names the project and lists its datasets (``data/<dataset_id>/``) and
pipelines (``pipelines/<pipeline_id>.vcp.json``) by id, in display order. It holds no
absolute path, so a project folder can be moved or shared (ADR-006); the API's
``path`` field (§2.4) is where the engine opened it.
"""

from __future__ import annotations

import os
from typing import Annotated, Literal

from pydantic import Field, field_validator

from vibechem_engine.formats._files import (
    StrictModel,
    dump,
    id_pattern,
    read_json,
    validate,
    write_atomic,
)
from vibechem_engine.formats.migrations import migrate
from vibechem_engine.formats.pipeline import Timestamp, repeated

__all__ = ["PROJECT_FILE_INVALID", "ProjectFile", "load_project", "save_project"]

PROJECT_FILE_INVALID = "PROJECT_FILE_INVALID"


class ProjectFile(StrictModel):
    format_version: Literal[1]
    project_id: Annotated[str, Field(pattern=id_pattern("prj"))]
    name: Annotated[str, Field(min_length=1)]
    created_at: Timestamp
    updated_at: Timestamp
    datasets: tuple[Annotated[str, Field(pattern=id_pattern("ds"))], ...]
    pipelines: tuple[Annotated[str, Field(pattern=id_pattern("ppl"))], ...]

    @field_validator("datasets", "pipelines")
    @classmethod
    def _unique(cls, ids: tuple[str, ...]) -> tuple[str, ...]:
        if twice := repeated(ids):
            raise ValueError(f"repeated id {twice}")
        return ids


def load_project(path: str | os.PathLike[str]) -> ProjectFile:
    """Read, migrate and validate ``project.json``; ``FormatError`` if it is invalid.

    Migration happens in memory; writing the upgraded file back (after the backup of
    §2.4) is the caller's job.
    """
    doc = migrate("project", read_json(path, PROJECT_FILE_INVALID), PROJECT_FILE_INVALID)
    return validate(ProjectFile, doc, PROJECT_FILE_INVALID)


def save_project(project: ProjectFile, path: str | os.PathLike[str]) -> None:
    """Write ``project`` to ``path`` (UTF-8 JSON, replaced atomically)."""
    write_atomic(path, dump(project))

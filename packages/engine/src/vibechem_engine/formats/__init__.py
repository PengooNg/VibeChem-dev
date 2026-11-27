# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/formats/__init__.py
"""File formats of a project folder (DATA_MODEL.md §6): pipeline, project, model package.

JSON documents are validated with pydantic models (strict JSON types, unknown keys
rejected); the committed ``*.schema.json`` files are their JSON Schema exports
(:func:`json_schemas`). Nothing here uses pickle (ADR-007).
"""

from __future__ import annotations

from typing import Any

from vibechem_engine.formats._files import FormatError
from vibechem_engine.formats.pipeline import (
    PIPELINE_FILE_INVALID,
    PipelineFile,
    load_pipeline,
    save_pipeline,
)

__all__ = [
    "PIPELINE_FILE_INVALID",
    "FormatError",
    "PipelineFile",
    "json_schemas",
    "load_pipeline",
    "save_pipeline",
]


def json_schemas() -> dict[str, dict[str, Any]]:
    """JSON Schema of each format, keyed by the committed file name."""
    return {"pipeline.schema.json": PipelineFile.model_json_schema()}

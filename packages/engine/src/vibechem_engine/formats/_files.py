# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/formats/_files.py
"""Shared reading, validation and writing of the JSON file formats (DATA_MODEL.md §6).

Every problem with a file's content raises :class:`FormatError` with the format's code
and a ``reason`` (§6.1): ``json``, ``too_large``, ``schema``, ``version`` and, for model
packages, ``zip``, ``entry`` and ``state``. A missing or unreadable file is an
``OSError``, left to the caller.
"""

from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, cast

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationError

from vibechem_core.errors import ErrorParam, VibeChemError

MAX_JSON_BYTES = 16 * 1024 * 1024
"""Largest JSON file (pipeline, project, model manifest) read (§6.1)."""

ID_PATTERN = r"[0-9A-Za-z]+"
SEMVER_PATTERN = r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"


def _real_time(value: str) -> str:
    datetime.strptime(value.removesuffix("Z").split(".")[0], "%Y-%m-%dT%H:%M:%S")
    return value


# ASCII digits only ([0-9], not \d: the schema regex engine matches any Unicode digit).
Timestamp = Annotated[
    str,
    Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z$"),
    AfterValidator(_real_time),
]


def repeated(ids: Iterable[str]) -> list[str]:
    return sorted(i for i, n in Counter(ids).items() if n > 1)


class FormatError(VibeChemError):
    """A pipeline, project or model file is invalid (DATA_MODEL.md §6.1, §7)."""


class StrictModel(BaseModel):
    """Base of every file model: exact JSON types, no unknown keys, no NaN, immutable."""

    model_config = ConfigDict(strict=True, extra="forbid", allow_inf_nan=False, frozen=True)


def fail(code: str, reason: str, **params: ErrorParam) -> FormatError:
    return FormatError(code, {"reason": reason, **params})


def _reject_constant(constant: str) -> object:
    raise ValueError(f"{constant} is not JSON")


def _finite_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(f"{text} is not a finite number")
    return value


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    keys = [k for k, _ in pairs]
    if len(set(keys)) != len(keys):
        raise ValueError(f"duplicate keys in an object: {sorted(keys)}")
    return dict(pairs)


def parse_json(data: bytes, code: str) -> dict[str, Any]:
    """The JSON object in ``data``; NaN, Infinity and repeated keys are rejected."""
    if len(data) > MAX_JSON_BYTES:
        raise fail(code, "too_large", limit=MAX_JSON_BYTES)
    try:
        doc: object = json.loads(
            data.decode("utf-8"),
            parse_constant=_reject_constant,
            parse_float=_finite_float,
            object_pairs_hook=_no_duplicate_keys,
        )
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise fail(code, "json", detail=str(exc)[:200]) from None
    if not isinstance(doc, dict):
        raise fail(code, "json", detail="the file must hold a JSON object")
    return cast(dict[str, Any], doc)


def read_json(path: str | os.PathLike[str], code: str) -> dict[str, Any]:
    """Parse the JSON object in the file at ``path`` (at most :data:`MAX_JSON_BYTES`)."""
    with Path(path).open("rb") as f:
        data = f.read(MAX_JSON_BYTES + 1)
    return parse_json(data, code)


def validate[M: BaseModel](model: type[M], doc: dict[str, Any], code: str) -> M:
    """``doc`` as ``model``; the first schema problem → ``FormatError`` reason ``schema``.

    Validated in JSON mode, so strictness follows JSON types (arrays → tuples, integers →
    floats) exactly as for a file read from disk.
    """
    try:
        return model.model_validate_json(json.dumps(doc))
    except ValidationError as exc:
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise fail(code, "schema", location=location, detail=first["msg"][:200]) from None


def dump(model: BaseModel) -> bytes:
    return (model.model_dump_json(indent=1) + "\n").encode("utf-8")


def write_atomic(path: str | os.PathLike[str], data: bytes) -> None:
    """Write ``data`` to ``path`` through a temporary file, so a crash never leaves half a file."""
    target = Path(path)
    tmp = target.with_name(target.name + ".tmp")
    try:
        with tmp.open("wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(target)
    finally:
        tmp.unlink(missing_ok=True)


def id_pattern(prefix: str) -> str:
    return f"^{re.escape(prefix)}_{ID_PATTERN}$"

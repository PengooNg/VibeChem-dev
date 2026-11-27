# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/formats/model.py
"""Model package ``models/<name>.vcm``, format version 1 (DATA_MODEL.md §6.4).

A zip holding ``manifest.json`` and one fitted state per fitted node, ``states/<i>/``
in the state layout of ``vibechem_core.block.save_state`` (``state.json`` +
``arrays/<j>.npy``). The manifest stamps each state with its node, block and block
version (RISKS.md R35). No pickle (ADR-007): arrays load with ``allow_pickle=False``.

Reading trusts nothing in the zip: only the entry names of §6.4 are accepted (so no
entry can point outside the temporary folder the states are unpacked into), encrypted
or unusually compressed entries are refused, and the declared uncompressed size is
capped (``zipfile`` never reads past an entry's declared size).
"""

from __future__ import annotations

import os
import re
import tempfile
import zipfile
import zlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from vibechem_core.block import State, load_state, save_state
from vibechem_engine.formats._files import (
    SEMVER_PATTERN,
    StrictModel,
    dump,
    fail,
    parse_json,
    validate,
)
from vibechem_engine.formats.migrations import migrate
from vibechem_engine.formats.pipeline import NodeId, PipelineFile, Timestamp, repeated

__all__ = [
    "MODEL_PACKAGE_INVALID",
    "ModelManifest",
    "ModelPackage",
    "StateEntry",
    "read_model",
    "write_model",
]

MODEL_PACKAGE_INVALID = "MODEL_PACKAGE_INVALID"

MAX_MODEL_BYTES = 2 * 1024**3
"""Largest total uncompressed size of a model package read (§6.4)."""

_COMPRESSIONS = (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
_ENTRY = re.compile(r"manifest\.json|states/(?:\d+/(?:state\.json|arrays/(?:\d+\.npy)?)?)?")


class StateEntry(StrictModel):
    node_id: NodeId
    block_id: str
    block_version: Annotated[str, Field(pattern=SEMVER_PATTERN)]


class ModelManifest(StrictModel):
    format_version: Literal[1]
    name: Annotated[str, Field(min_length=1)]
    vibechem_version: Annotated[str, Field(min_length=1)]
    trained_at: Timestamp
    pipeline: PipelineFile
    states: tuple[StateEntry, ...]

    @model_validator(mode="after")
    def _states_match_nodes(self) -> ModelManifest:
        if twice := repeated([s.node_id for s in self.states]):
            raise ValueError(f"repeated state node_id {twice}")
        nodes = {n.node_id: (n.block_id, n.block_version) for n in self.pipeline.nodes}
        for s in self.states:
            if nodes.get(s.node_id) != (s.block_id, s.block_version):
                raise ValueError(f"state {s.node_id} does not match a pipeline node")
        return self


@dataclass(frozen=True)
class ModelPackage:
    """A manifest and its states; ``states[i]`` belongs to ``manifest.states[i]``."""

    manifest: ModelManifest
    states: Sequence[State]

    def __post_init__(self) -> None:
        if len(self.states) != len(self.manifest.states):
            raise ValueError(
                f"{len(self.states)} states for {len(self.manifest.states)} manifest entries"
            )


def write_model(package: ModelPackage, path: str | os.PathLike[str]) -> None:
    """Write ``package`` as a ``.vcm`` zip to ``path`` (replaced atomically)."""
    target = Path(path)
    tmp = target.with_name(target.name + ".tmp")
    with (
        tempfile.TemporaryDirectory() as folder,
        zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf,
    ):
        zf.writestr("manifest.json", dump(package.manifest))
        for i, state in enumerate(package.states):
            root = Path(folder) / str(i)
            save_state(state, root)
            zf.write(root / "state.json", f"states/{i}/state.json")
            for j in range(len(state.arrays)):
                zf.write(root / "arrays" / f"{j}.npy", f"states/{i}/arrays/{j}.npy")
    tmp.replace(target)


def read_model(path: str | os.PathLike[str]) -> ModelPackage:
    """Read a ``.vcm`` package; ``FormatError`` ``MODEL_PACKAGE_INVALID`` if it is invalid."""
    try:
        with zipfile.ZipFile(path) as zf:
            return _read(zf)
    except (zipfile.BadZipFile, zlib.error) as exc:
        raise fail(MODEL_PACKAGE_INVALID, "zip", detail=str(exc)[:200]) from None


def _read(zf: zipfile.ZipFile) -> ModelPackage:
    infos = zf.infolist()
    names = [info.filename for info in infos]
    for info in infos:
        if not _ENTRY.fullmatch(info.filename) or names.count(info.filename) > 1:
            raise fail(MODEL_PACKAGE_INVALID, "entry", entry=info.filename[:200])
        if info.flag_bits & 0x1 or info.compress_type not in _COMPRESSIONS:
            raise fail(
                MODEL_PACKAGE_INVALID,
                "zip",
                detail=f"{info.filename[:200]}: encrypted or unsupported compression",
            )
    if sum(info.file_size for info in infos) > MAX_MODEL_BYTES:
        raise fail(MODEL_PACKAGE_INVALID, "too_large", limit=MAX_MODEL_BYTES)
    if "manifest.json" not in names:
        raise fail(MODEL_PACKAGE_INVALID, "entry", entry="manifest.json")

    doc = parse_json(zf.read("manifest.json"), MODEL_PACKAGE_INVALID)
    doc = migrate("model", doc, MODEL_PACKAGE_INVALID)
    if isinstance(doc.get("pipeline"), dict):  # the embedded pipeline has its own version
        doc["pipeline"] = migrate("pipeline", doc["pipeline"], MODEL_PACKAGE_INVALID)
    manifest = validate(ModelManifest, doc, MODEL_PACKAGE_INVALID)

    n = len(manifest.states)
    for name in names:
        if name.startswith("states/") and name.count("/") >= 2 and int(name.split("/")[1]) >= n:
            raise fail(MODEL_PACKAGE_INVALID, "entry", entry=name[:200])
    states: list[State] = []
    with tempfile.TemporaryDirectory() as folder:
        for i in range(n):
            root = Path(folder) / str(i)
            (root / "arrays").mkdir(parents=True)
            prefix = f"states/{i}/"
            for name in names:
                if name.startswith(prefix) and not name.endswith("/"):
                    (root / name.removeprefix(prefix)).write_bytes(zf.read(name))
            try:
                states.append(load_state(root))
            except (ValueError, FileNotFoundError) as exc:
                raise fail(MODEL_PACKAGE_INVALID, "state", index=i, detail=str(exc)[:200]) from None
    return ModelPackage(manifest, states)

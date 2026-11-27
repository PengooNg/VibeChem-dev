# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/cache/__init__.py
"""Content-addressed result cache (ARCHITECTURE.md §2.2 step 4, §2.3, §3.3, §3.6).

:func:`result_key` gives one task output its key (DATA_MODEL.md §1 "Result keys"):
``res_`` + SHA-256 of the canonical JSON of everything that decides the result, so a
parameter change alters that task's keys and, through ``input_keys``, every key
downstream.

:class:`ResultCache` stores one :class:`~vibechem_core.block.State` per key in the
project's ``cache/`` folder (layout: DATA_MODEL.md §6.6), with a size cap (least
recently used entries go first) and a SHA-256 checksum per file: a damaged entry is
deleted and reported as a miss, so the task is recomputed.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import time
import uuid
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from vibechem_core.block import State, load_state, save_state
from vibechem_engine.compiler import Task

__all__ = ["ENTRY_VERSION", "KEY_VERSION", "ResultCache", "check_key", "result_key"]

_log = logging.getLogger(__name__)
ENTRY_VERSION = 1
"""Version of ``entry.json``; an entry with another version is discarded."""

KEY_VERSION = 1
"""Bumped when the key recipe changes, so old entries are never read as new ones."""
_KEY = re.compile(r"res_[0-9a-f]{64}")
_FILE = re.compile(r"state\.json|arrays/(0|[1-9][0-9]*)\.npy")  # the save_state layout


def result_key(
    task: Task,
    output: str,
    *,
    block_id: str,
    block_version: str,
    params: Mapping[str, object],
    input_keys: Sequence[str],
    seed: int | None,
) -> str:
    """Key of output ``output`` of ``task``.

    ``input_keys[i]`` is the result key of ``task.inputs[i]``; ``params`` as parsed by
    the block (defaults filled). Hashed: kind, block id and version, params, inputs
    (port, key, conversion rule; sorted by port, edge order kept within a port), seed,
    fold, part and output. Not hashed: ``task_id``/``node_id`` (a renamed node keeps
    its results). ``ValueError`` for non-JSON params or a bad input key.
    """
    if len(input_keys) != len(task.inputs):
        raise ValueError(f"input_keys has {len(input_keys)} keys for {len(task.inputs)} inputs")
    for key in input_keys:
        check_key(key)
    pairs = sorted(zip(task.inputs, input_keys, strict=True), key=lambda pair: pair[0].port_id)
    inputs = [[i.port_id, k, i.rule] for i, k in pairs]
    doc: dict[str, object] = {
        "key_version": KEY_VERSION,
        "kind": task.kind,
        "block_id": block_id,
        "block_version": block_version,
        "params": params,
        "inputs": inputs,
        "seed": seed,
        "fold": task.fold,
        "part": task.part,
        "output": output,
    }
    try:
        text = json.dumps(doc, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"params of {block_id} are not JSON: {exc}") from None
    return "res_" + hashlib.sha256(text.encode()).hexdigest()


def check_key(key: str) -> str:
    """``key`` if it is a result key, else ``ValueError`` (keys become folder names)."""
    if not isinstance(key, str) or not _KEY.fullmatch(key):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise ValueError(f"{key!r} is not a result key (res_ + 64 lowercase hex)")
    return key


class _Entry:
    __slots__ = ("files", "size")

    def __init__(self, size: int, files: dict[str, str]) -> None:
        self.size, self.files = size, files


class ResultCache:
    """The result cache in folder ``root`` (a project's ``cache/``), capped at ``cap_bytes``.

    Opening scans ``root/entries/`` (rebuilding the in-memory index) and deletes leftovers
    in ``root/tmp/``. One engine process owns the folder; not thread-safe.
    """

    def __init__(self, root: str | os.PathLike[str], cap_bytes: int) -> None:
        if type(cap_bytes) is not int or cap_bytes < 0:
            raise ValueError(f"cap_bytes must be an int >= 0, got {cap_bytes!r}")
        self.root, self.cap_bytes = Path(root), cap_bytes
        self._entries_dir, self._tmp = self.root / "entries", self.root / "tmp"
        self._entries_dir.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(self._tmp, ignore_errors=True)  # stale half-written entries only
        self._tmp.mkdir(exist_ok=True)
        self._index: OrderedDict[str, _Entry] = OrderedDict()  # oldest use first
        self.size_bytes = 0
        found: list[tuple[int, str, _Entry]] = []
        for folder in self._entries_dir.iterdir():
            entry = _read_entry(folder)
            if entry is None:
                _log.warning("cache: discarding invalid entry %s", folder.name)
                _remove(folder)
                continue
            found.append(((folder / "entry.json").stat().st_mtime_ns, "res_" + folder.name, entry))
        self._stamp = max((f[0] for f in found), default=0)
        for _, key, entry in sorted(found, key=lambda f: f[0]):
            self._index[key] = entry
            self.size_bytes += entry.size

    def __contains__(self, key: str) -> bool:
        return check_key(key) in self._index

    def __len__(self) -> int:
        return len(self._index)

    def get(self, key: str) -> State | None:
        """The state stored under ``key``, or ``None`` (missing, or damaged and deleted)."""
        entry = self._index.get(check_key(key))
        if entry is None:
            return None
        folder = self._folder(key)
        try:
            for name, digest in entry.files.items():
                if _sha256(folder / name) != digest:
                    raise ValueError(f"checksum mismatch in {name}")
            state = load_state(folder)
        except (OSError, ValueError) as exc:
            _log.warning("cache: discarding damaged entry %s (%s)", key, exc)
            self._drop(key)
            return None
        self._touch(key)
        return state

    def put(self, key: str, state: State) -> int:
        """Store ``state`` under ``key``, then evict to the cap; returns the bytes freed.

        A key already stored is only marked as used (same key, same content). The new
        entry itself is never evicted, so one entry larger than the cap stays until the
        next ``put``.
        """
        if check_key(key) in self._index:
            self._touch(key)
            return 0
        staging = self._tmp / uuid.uuid4().hex
        save_state(state, staging)
        files = {
            p.relative_to(staging).as_posix(): _sha256(p)
            for p in sorted(staging.rglob("*"))
            if p.is_file()
        }
        size = sum((staging / name).stat().st_size for name in files)
        doc = {"entry_version": ENTRY_VERSION, "key": key, "size_bytes": size, "files": files}
        (staging / "entry.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
        staging.replace(self._folder(key))
        self._index[key] = _Entry(size, files)
        self.size_bytes += size
        self._touch(key)
        freed = 0
        while self.size_bytes > self.cap_bytes and len(self._index) > 1:
            oldest = next(iter(self._index))
            freed += self._index[oldest].size
            self._drop(oldest)
        return freed

    def clear(self) -> int:
        """Delete every entry; returns the bytes freed."""
        freed = self.size_bytes
        for key in list(self._index):
            self._drop(key)
        return freed

    def _folder(self, key: str) -> Path:
        return self._entries_dir / key.removeprefix("res_")

    def _touch(self, key: str) -> None:
        # strictly increasing stamps (1 µs steps survive NTFS's 100 ns mtime resolution)
        self._stamp = max(time.time_ns(), self._stamp + 1_000)
        os.utime(self._folder(key) / "entry.json", ns=(self._stamp, self._stamp))
        self._index.move_to_end(key)

    def _drop(self, key: str) -> None:
        self.size_bytes -= self._index.pop(key).size
        _remove(self._folder(key))


def _read_entry(folder: Path) -> _Entry | None:
    """The entry in ``folder``, or ``None`` if its name or ``entry.json`` is invalid."""
    if not _KEY.fullmatch("res_" + folder.name) or not folder.is_dir():
        return None
    try:
        doc: object = json.loads((folder / "entry.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict):
        return None
    meta = cast(dict[str, object], doc)
    size, files = meta.get("size_bytes"), meta.get("files")
    if (
        set(meta) != {"entry_version", "key", "size_bytes", "files"}
        or meta["entry_version"] != ENTRY_VERSION
        or meta["key"] != "res_" + folder.name
        or type(size) is not int
        or not isinstance(files, dict)
        or "state.json" not in files
        or not all(
            isinstance(k, str) and _FILE.fullmatch(k) and isinstance(v, str)
            for k, v in cast(dict[object, object], files).items()
        )
    ):
        return None
    return _Entry(size, cast(dict[str, str], files))


def _sha256(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def _remove(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()

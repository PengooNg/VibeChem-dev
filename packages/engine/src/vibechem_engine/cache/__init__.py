# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/cache/__init__.py
"""Content-addressed result cache (ARCHITECTURE.md §2.2 step 4, §2.3, §3.3, §3.6).

:func:`result_key` gives one task output its key (DATA_MODEL.md §1 "Result keys"):
``res_`` + SHA-256 of the canonical JSON of everything that decides the result, so a
parameter change alters that task's keys and, through ``input_keys``, every key
downstream.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence

from vibechem_engine.compiler import Task

__all__ = ["KEY_VERSION", "result_key"]

KEY_VERSION = 1
"""Bumped when the key recipe changes, so old entries are never read as new ones."""
_KEY = re.compile(r"res_[0-9a-f]{64}")


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

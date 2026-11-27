# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/cache/test_keys.py
"""``vibechem_engine.cache.result_key``: key stability (T2.06 "Done when")."""

from __future__ import annotations

import hashlib
import re
from typing import Any

import pytest

from vibechem_engine.cache import result_key
from vibechem_engine.compiler import Task, TaskInput

UP = "res_" + "a" * 64
UP2 = "res_" + "b" * 64
TASK = Task("nd_1:apply", "nd_1", "apply", (TaskInput("spectra", "nd_0:run", "spectra"),))


def _key(task: Task = TASK, output: str = "spectra", **kw: Any) -> str:
    args: dict[str, Any] = {
        "block_id": "preprocess.msc",
        "block_version": "1.0.0",
        "params": {"reference": "mean", "window": 3},
        "input_keys": [UP],
        "seed": None,
    }
    args.update(kw)
    return result_key(task, output, **args)


def test_pinned_value_from_hand_written_canonical_json() -> None:
    doc = (
        '{"block_id":"preprocess.msc","block_version":"1.0.0","fold":null,'
        '"inputs":[["spectra","' + UP + '",null]],"key_version":1,"kind":"apply",'
        '"output":"spectra","params":{"reference":"mean","window":3},"part":null,"seed":null}'
    )
    assert _key() == "res_" + hashlib.sha256(doc.encode()).hexdigest()
    assert re.fullmatch(r"res_[0-9a-f]{64}", _key())


def test_param_order_and_task_id_do_not_matter() -> None:
    renamed = Task("other-id", "nd_9", "apply", TASK.inputs)
    assert _key(params={"window": 3, "reference": "mean"}) == _key()
    assert _key(renamed) == _key()


def test_input_order_across_ports_does_not_matter_but_within_a_port_does() -> None:
    a, b = TaskInput("spectra", "t1", "x"), TaskInput("reference", "t2", "y")
    two = Task("t", "n", "run", (a, b))
    swapped = Task("t", "n", "run", (b, a))
    assert _key(two, input_keys=[UP, UP2]) == _key(swapped, input_keys=[UP2, UP])
    multi = Task("t", "n", "run", (a, TaskInput("spectra", "t3", "z")))
    assert _key(multi, input_keys=[UP, UP2]) != _key(multi, input_keys=[UP2, UP])


@pytest.mark.parametrize(
    "change",
    [
        {"block_id": "preprocess.snv"},
        {"block_version": "1.0.1"},
        {"params": {"reference": "median", "window": 3}},
        {"params": {"reference": "mean", "window": 3.0}},
        {"input_keys": [UP2]},
        {"seed": 0},
        {"output": "state"},
        {"task": Task("t", "n", "fit", TASK.inputs)},
        {"task": Task("t", "n", "apply", (TaskInput("spectra", "x", "y", "implicit_view"),))},
        {"task": Task("t", "n", "apply", TASK.inputs, (0, 0), "train")},
        {"task": Task("t", "n", "apply", TASK.inputs, (1, 0), "train")},
        {"task": Task("t", "n", "apply", TASK.inputs, (0, 0), "validation")},
    ],
)
def test_every_field_changes_the_key(change: dict[str, Any]) -> None:
    assert _key(**change) != _key()


def test_rejects_non_json_params_and_bad_input_keys() -> None:
    with pytest.raises(ValueError, match="JSON"):
        _key(params={"x": float("nan")})
    with pytest.raises(ValueError, match="JSON"):
        _key(params={"x": object()})
    with pytest.raises(ValueError, match="input_keys"):
        _key(input_keys=[])
    with pytest.raises(ValueError, match="result key"):
        _key(input_keys=["res_xyz"])

# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/blocks/test_default_registry.py
"""``default_registry`` and the ``data.dataset`` block (T2.11, DATA_MODEL.md §2.3)."""

from __future__ import annotations

import pytest

from vibechem_core.blocks import default_registry
from vibechem_core.blocks.data.dataset import Dataset


def test_default_registry_holds_every_block_once_and_is_new_each_time() -> None:
    first, second = default_registry(), default_registry()
    assert first is not second
    assert len(first) == 23
    for block_id in (
        "data.dataset",
        "preprocess.snv",
        "model.pls",
        "validate.cv",
        "validate.nested_cv",
    ):
        assert block_id in first


def test_dataset_block_is_a_source_with_a_dataset_id_param() -> None:
    meta = default_registry().meta("data.dataset")
    assert meta.block_class == "data"
    assert meta.inputs == ()
    assert [(p.port_id, p.port_type) for p in meta.outputs] == [("spectra", "Spectra")]
    assert [name for name, _ in meta.params] == ["dataset_id"]


def test_dataset_block_never_runs() -> None:
    with pytest.raises(RuntimeError, match="supplied by the engine"):
        Dataset().apply()

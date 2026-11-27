# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/data/test_folds.py
"""Tests for ``FoldSet`` / ``Fold`` (DATA_MODEL.md §4.2 ``Folds``)."""

from __future__ import annotations

import numpy as np
import pytest

from vibechem_core.data import Fold, FoldSet


def test_fold_rejects_overlap_and_is_read_only() -> None:
    with pytest.raises(ValueError, match="share"):
        Fold(0, 0, [1, 2], [2, 3])
    fold = Fold(0, 0, [1, 2], [3])
    assert fold.train.dtype == np.int64
    assert not fold.train.flags.writeable
    fs = FoldSet("holdout", "ds", 3, (fold,), groups_respected=True)
    assert (fs.n_folds, fs.n_repeats) == (1, 1)
    with pytest.raises(ValueError, match="scheme"):
        FoldSet("nope", "ds", 3, (fold,), groups_respected=True)

# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/data/folds.py
"""``FoldSet``: the Python object behind the ``Folds`` port type (DATA_MODEL.md §4.2).

Index values are ``row_index`` values of the source dataset, not positions, so a
fold can be mapped onto any downstream object. A hold-out split is one ``Fold``
whose ``validation`` is the test set. Arrays are private read-only copies.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from vibechem_core.data._validate import index_array, text

SCHEMES = frozenset(
    {
        "kfold", "venetian", "contiguous", "loo", "repeated_kfold",
        "monte_carlo", "group_kfold", "holdout", "custom",
    }
)  # fmt: skip
"""``scheme`` values of DATA_MODEL.md §4.2 ``Folds``."""


@dataclass(frozen=True, eq=False)
class Fold:
    """One fold: training and validation ``row_index`` values (disjoint, unique)."""

    fold: int
    repeat: int
    train: NDArray[np.int64]
    validation: NDArray[np.int64]

    def __init__(self, fold: int, repeat: int, train: ArrayLike, validation: ArrayLike) -> None:
        tr, va = index_array("train", train), index_array("validation", validation)
        for name, rows in (("train", tr), ("validation", va)):
            if np.unique(rows).size != rows.size:
                raise ValueError(f"{name} row_index values must be unique")
        if np.intersect1d(tr, va).size:
            raise ValueError("train and validation share row_index values")
        for field, value in (("fold", fold), ("repeat", repeat), ("train", tr), ("validation", va)):
            object.__setattr__(self, field, value)


@dataclass(frozen=True, eq=False)
class FoldSet:
    """Row-index sets for validation: k folds, repeats, or one train/test hold-out."""

    scheme: str
    source_id: str
    n_samples: int
    folds: tuple[Fold, ...]
    groups_respected: bool
    seed: int | None = None

    def __post_init__(self) -> None:
        if self.scheme not in SCHEMES:
            raise ValueError(f"unknown scheme {self.scheme!r}; one of {sorted(SCHEMES)}")
        text("source_id", self.source_id)
        object.__setattr__(self, "folds", tuple(self.folds))
        if not self.folds:
            raise ValueError("a FoldSet needs at least one fold")

    @property
    def n_folds(self) -> int:
        return len({f.fold for f in self.folds})

    @property
    def n_repeats(self) -> int:
        return len({f.repeat for f in self.folds})

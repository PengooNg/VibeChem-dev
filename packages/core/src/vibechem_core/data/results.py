# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/data/results.py
"""``Results``: the Python object behind the ``Results`` port type (DATA_MODEL.md §4.2).

Tables (``predictions``, ``candidates``) are column name -> NumPy array mappings, like
every core table; ``details`` holds JSON values only.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from numpy.typing import NDArray

type ResultsKind = Literal["cv", "nested_cv", "test_set", "permutation", "search", "statistics"]


@dataclass(frozen=True)
class Results:
    """Metrics (METHODS.md §8 names, original Y units) and tables of a validation block."""

    kind: ResultsKind
    metrics: Mapping[str, float]
    y_unit: str | None = None
    predictions: Mapping[str, NDArray[Any]] | None = None
    candidates: Mapping[str, NDArray[Any]] | None = None
    leakage_safe: bool = True
    details: Mapping[str, Any] = field(default_factory=dict[str, Any])

# SPDX-License-Identifier: GPL-3.0-or-later
# packages/native/python/vibechem_native/__init__.py
"""Optional C++20 kernels with automatic fallback to NumPy references.

``BACKEND`` is ``"native"`` when the compiled extension ``vibechem_native._core``
imports, otherwise ``"python"`` and every kernel runs its NumPy reference
(TECH_STACK.md §5, ADR-002). Results match within floating-point rounding.
"""

import logging
import operator
import os

import numpy as np
from numpy.typing import ArrayLike, NDArray

from vibechem_native._reference import row_mean_reference

logger = logging.getLogger(__name__)

try:
    from vibechem_native import _core
except ImportError as exc:  # extension not built, or hidden on purpose
    _core = None
    logger.info("vibechem_native extension unavailable, using NumPy fallback: %s", exc)

BACKEND = "python" if _core is None else "native"

__all__ = ["BACKEND", "row_mean"]


def row_mean(X: ArrayLike, n_threads: int = 1) -> NDArray[np.float64]:
    """Mean of each row of a 2-D array.

    Parameters
    ----------
    X : array_like, shape (n_rows, n_cols)
        Values; converted to C-contiguous float64. ``n_cols`` must be > 0.
    n_threads : int, default 1
        Worker threads for the native kernel, capped at the CPU count (ignored by
        the fallback). Must be an integer >= 1 on both backends.

    Returns
    -------
    ndarray of float64, shape (n_rows,)

    Raises
    ------
    ValueError
        If ``X`` is complex, not 2-D, has no columns, or ``n_threads < 1``.
    TypeError
        If ``n_threads`` is not an integer.
    """
    n_threads = operator.index(n_threads)
    if np.iscomplexobj(X):
        raise ValueError("row_mean needs real values, got a complex array")
    X_c = np.ascontiguousarray(X, dtype=np.float64)
    if X_c.ndim != 2 or X_c.shape[1] == 0:
        raise ValueError(f"row_mean needs a 2-D array with at least one column, got {X_c.shape}")
    if n_threads < 1:
        raise ValueError(f"n_threads must be >= 1, got {n_threads}")
    if _core is None:
        return row_mean_reference(X_c)
    out = np.empty(X_c.shape[0], dtype=np.float64)
    _core.row_mean(X_c, out, min(n_threads, os.cpu_count() or 1))
    return out

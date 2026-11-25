# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/data/_validate.py
"""Input checks shared by ``Axis``, ``Spatial`` and ``SpectralDataset``.

Every helper returns a private, read-only copy (arrays) or an immutable tuple, so
the data-model objects never share mutable state with their callers.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
from numpy.typing import ArrayLike, NDArray

_INT64_MAX = np.iinfo(np.int64).max


def frozen_array[ScalarT: np.generic](values: ArrayLike, dtype: type[ScalarT]) -> NDArray[ScalarT]:
    """Return a read-only copy of ``values`` as ``dtype``."""
    array = np.array(values, dtype=dtype, copy=True)
    array.flags.writeable = False
    return array


def real_array(name: str, array: NDArray[np.generic]) -> NDArray[np.float64]:
    """Read-only float64 copy of a real-valued (int, unsigned or float) array."""
    if array.dtype.kind not in "iuf":
        raise ValueError(f"{name} must be real numbers, got dtype {array.dtype}")
    return frozen_array(array, np.float64)


def index_array(name: str, values: ArrayLike) -> NDArray[np.int64]:
    """Read-only int64 copy of a 1-D integer array (values must fit in int64)."""
    array = np.asarray(values)
    if array.ndim != 1:
        raise ValueError(f"{name} must be 1-D, got shape {array.shape}")
    if array.size and array.dtype.kind not in "iu":
        raise ValueError(f"{name} must be integers, got dtype {array.dtype}")
    if array.size and array.dtype.kind == "u" and array.max() > _INT64_MAX:
        raise ValueError(f"{name} values exceed the int64 range")
    return frozen_array(array, np.int64)


def text(name: str, value: object) -> str:
    """A non-empty ``str`` (run-time check: values may come from files)."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string, got {value!r}")
    return str(value)


def strings(name: str, values: Iterable[object]) -> tuple[str, ...]:
    """Tuple of ``str``; a single string is rejected instead of split into characters."""
    if isinstance(values, str):
        raise TypeError(f"{name} must be a sequence of strings, not a single string")
    items = tuple(values)
    if not all(isinstance(item, str) for item in items):
        raise TypeError(f"{name} must be strings")
    return tuple(str(item) for item in items)

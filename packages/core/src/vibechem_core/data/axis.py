# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/data/axis.py
"""Spectral axis and pixel layout of a ``SpectralDataset`` (DATA_MODEL.md §4.2).

``Axis`` is the ``axis`` field of the ``Spectra`` port type; ``Spatial`` is its
``spatial`` field (rows unfolded from an ``ImageCube``). Both are immutable: the
arrays are private read-only copies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, get_args

import numpy as np
from numpy.typing import ArrayLike, NDArray

AxisUnit = Literal["nm", "cm-1", "um", "index"]
"""Units allowed for a spectral axis (DATA_MODEL.md §4.2)."""

AXIS_UNITS: tuple[AxisUnit, ...] = get_args(AxisUnit)


def frozen_array[ScalarT: np.generic](values: ArrayLike, dtype: type[ScalarT]) -> NDArray[ScalarT]:
    """Return a read-only copy of ``values`` as ``dtype``."""
    array = np.array(values, dtype=dtype, copy=True)
    array.flags.writeable = False
    return array


@dataclass(frozen=True, eq=False)
class Axis:
    """Spectral axis: one value per variable, strictly monotonic, with a unit.

    Parameters
    ----------
    values : array_like, shape (p,)
        Axis positions (e.g. wavelengths). Strictly increasing or strictly
        decreasing, finite, at least one value.
    unit : {"nm", "cm-1", "um", "index"}
        Unit of ``values``.
    """

    values: NDArray[np.float64]
    unit: AxisUnit

    def __init__(self, values: ArrayLike, unit: AxisUnit) -> None:
        array = np.asarray(values)
        if array.ndim != 1 or array.size == 0:
            raise ValueError(f"axis values must be a non-empty 1-D array, got shape {array.shape}")
        if not np.issubdtype(array.dtype, np.number):
            raise ValueError(f"axis values must be numeric, got dtype {array.dtype}")
        frozen = frozen_array(array, np.float64)
        if not np.isfinite(frozen).all():
            raise ValueError("axis values must be finite")
        steps = np.diff(frozen)
        if not ((steps > 0).all() or (steps < 0).all()):
            raise ValueError("axis values must be strictly monotonic")
        if unit not in AXIS_UNITS:
            raise ValueError(f"axis unit must be one of {AXIS_UNITS}, got {unit!r}")
        object.__setattr__(self, "values", frozen)
        object.__setattr__(self, "unit", unit)

    @property
    def p(self) -> int:
        """Number of variables."""
        return int(self.values.size)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Axis):
            return NotImplemented
        return self.unit == other.unit and np.array_equal(self.values, other.values)

    __hash__ = None  # type: ignore[assignment]  # mutable-looking arrays; not hashable


@dataclass(frozen=True, eq=False)
class Spatial:
    """Pixel positions of rows unfolded from an ``ImageCube`` (P2).

    Parameters
    ----------
    height, width : int
        Image size in pixels (both >= 1).
    pixel : array_like of int, shape (n,)
        Row-major pixel index of each row; unique, in ``[0, height * width)``.
    cube_id : str
        ``cube_id`` of the source ``ImageCube``.
    """

    height: int
    width: int
    pixel: NDArray[np.int64]
    cube_id: str

    def __init__(self, height: int, width: int, pixel: ArrayLike, cube_id: str) -> None:
        if height < 1 or width < 1:
            raise ValueError(f"spatial height and width must be >= 1, got {height} x {width}")
        array = np.asarray(pixel)
        if array.ndim != 1:
            raise ValueError(f"spatial pixel must be 1-D, got shape {array.shape}")
        if array.size and not np.issubdtype(array.dtype, np.integer):
            raise ValueError(f"spatial pixel must be integers, got dtype {array.dtype}")
        frozen = frozen_array(array, np.int64)
        if frozen.size and (frozen.min() < 0 or frozen.max() >= height * width):
            raise ValueError(f"spatial pixel must lie in [0, {height * width})")
        if np.unique(frozen).size != frozen.size:
            raise ValueError("spatial pixel values must be unique")
        object.__setattr__(self, "height", height)
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "pixel", frozen)
        object.__setattr__(self, "cube_id", cube_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Spatial):
            return NotImplemented
        return (self.height, self.width, self.cube_id) == (
            other.height,
            other.width,
            other.cube_id,
        ) and np.array_equal(self.pixel, other.pixel)

    __hash__ = None  # type: ignore[assignment]

# SPDX-License-Identifier: GPL-3.0-or-later
# packages/native/python/vibechem_native/_reference.py
"""NumPy reference for the stub kernel of the native skeleton (T0.05).

Phase 3 kernels use their reference functions in ``vibechem_core``; this stub has
no core counterpart, so its reference lives here.
"""

import numpy as np
from numpy.typing import NDArray


def row_mean_reference(X: NDArray[np.float64]) -> NDArray[np.float64]:
    """Mean of each row of a 2-D float64 array; shape ``(n_rows,)``."""
    return X.mean(axis=1)

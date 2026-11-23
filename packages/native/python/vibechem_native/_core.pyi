# SPDX-License-Identifier: GPL-3.0-or-later
# Type stub for the compiled extension (bindings/module.cpp); keep in sync by hand.
import numpy as np
from numpy.typing import NDArray

def row_mean(X: NDArray[np.float64], out: NDArray[np.float64], n_threads: int = 1) -> None: ...

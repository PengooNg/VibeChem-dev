# SPDX-License-Identifier: GPL-3.0-or-later
# conftest.py
"""Test-process settings that must exist before NumPy loads (BUG #84)."""

import os
import sys

# The loky workers run BLAS on one thread (executor `_WORKER_ENV`). Tests that compare them with
# an in-process run cap the test process with threadpoolctl, which cannot see Accelerate (NumPy's
# BLAS on macOS 14+ wheels); Accelerate reads this variable only when it loads.
if "numpy" in sys.modules:
    raise RuntimeError("NumPy loaded before conftest.py: VECLIB_MAXIMUM_THREADS would be ignored")
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"

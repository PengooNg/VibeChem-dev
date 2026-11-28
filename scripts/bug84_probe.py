# SPDX-License-Identifier: GPL-3.0-or-later
# scripts/bug84_probe.py
"""Temporary BUG #84 probe (removed before merge): do BLAS results depend on threads or alignment?"""

import hashlib
import os
import sys

import numpy as np


def aligned(a: np.ndarray, offset: int) -> np.ndarray:
    """Copy of ``a`` whose data starts ``offset`` bytes after a 4096-byte boundary."""
    buf = np.empty(a.nbytes + 8192, dtype=np.uint8)
    start = (-buf.ctypes.data) % 4096 + offset
    out = buf[start : start + a.nbytes].view(a.dtype).reshape(a.shape)
    out[...] = a
    return out


def digest(*arrays: np.ndarray) -> str:
    return hashlib.sha256(b"".join(np.ascontiguousarray(x).tobytes() for x in arrays)).hexdigest()[:12]


def ops(x: np.ndarray, y: np.ndarray) -> dict[str, str]:
    u, s, vt = np.linalg.svd(x, full_matrices=False)
    return {
        "xtx": digest(x.T @ x),
        "xty": digest(x.T @ y),
        "xv": digest(x @ x[0]),
        "dot": digest(np.array(x[:, 0] @ x[:, 1])),
        "lstsq": digest(np.linalg.lstsq(x, y, rcond=None)[0]),
        "svd_s": digest(s),
    }


rng = np.random.default_rng(1)
for rows, cols in ((50, 401), (600, 300)):
    x0 = rng.normal(size=(rows, cols))
    y0 = rng.normal(size=rows)
    by_offset = {off: ops(aligned(x0, off), aligned(y0, off)) for off in (0, 8, 16, 32, 48)}
    for name in by_offset[0]:
        values = {off: r[name] for off, r in by_offset.items()}
        print(f"VECLIB={os.environ.get('VECLIB_MAXIMUM_THREADS')} {rows}x{cols} {name}: "
              f"{'SAME' if len(set(values.values())) == 1 else 'DIFF'} {values}")
blas = np.show_config(mode="dicts")["Build Dependencies"]["blas"]["name"]
print("numpy", np.__version__, "blas", blas, sys.platform)

# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/api/arrow.py
"""Arrow IPC encoding of plot previews (DATA_MODEL.md §1 "Binary data", §2.8).

pyarrow ships no type information, so the pyright checks for unknown types are off
in this file only; the public function is fully typed.
"""
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

import numpy as np
import pyarrow as pa
from numpy.typing import NDArray

__all__ = ["ARROW_STREAM", "spectra_to_arrow"]

ARROW_STREAM = "application/vnd.apache.arrow.stream"


def spectra_to_arrow(x: NDArray[np.float64], y: NDArray[np.float64]) -> bytes:
    """Encode spectra as an Arrow IPC stream: columns ``x``, ``y_0`` … ``y_{n-1}`` (float32).

    ``y`` has one spectrum per row; ``y_i`` is row ``i`` (0-based).
    """
    columns = {"x": pa.array(x, type=pa.float32())}
    for i, row in enumerate(y):
        columns[f"y_{i}"] = pa.array(row, type=pa.float32())
    table = pa.table(columns)
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    content: bytes = sink.getvalue().to_pybytes()
    return content

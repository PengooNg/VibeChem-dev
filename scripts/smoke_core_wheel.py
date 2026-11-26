# SPDX-License-Identifier: GPL-3.0-or-later
# scripts/smoke_core_wheel.py
"""Wheel smoke test: the installed ``vibechem-core`` reproduces a published PLS value.

Used by the ``wheels`` job in ``.github/workflows/ci.yml`` (TASKS.md T1.15) on the wheel
from ``uv build --package vibechem-core``, installed into an isolated environment:

    uv run --isolated --no-project --with dist/vibechem_core-*.whl python -I scripts/smoke_core_wheel.py

Fits PLS (2 LV) on gasoline samples 1-50 and checks the test RMSEP on 51-60 against
Mevik & Wehrens (2007). ``--allow-source`` skips the check that the package comes from
an installed wheel (for the unit test in the workspace).
"""

from __future__ import annotations

import argparse
import sys
from importlib.metadata import version
from pathlib import Path

import numpy as np

import vibechem_core
from vibechem_core.block import parse_params
from vibechem_core.blocks.model.pls import PLS, PLSParams
from vibechem_core.data import Axis, SpectralDataset
from vibechem_core.reference_datasets import load_expected, load_reference_dataset

TESTDATA = Path(__file__).resolve().parents[1] / "testdata"


def smoke(testdata_dir: Path = TESTDATA) -> tuple[str, float, float]:
    """Return (package location, RMSEP at 2 LV, published value); raise if outside tolerance."""
    data = load_reference_dataset("gasoline_nir", testdata_dir=testdata_dir)
    expected = load_expected("gasoline_nir_pls", testdata_dir=testdata_dir)
    full = SpectralDataset(
        data.spectra,
        Axis(data.axis, "nm"),
        signal_unit="absorbance",
        sample_ids=[str(s) for s in data.sample_ids],
        row_index=np.arange(60),
        source_id="gasoline_nir",
        y=data.target.astype(np.float64)[:, None],
        y_columns=["octane"],
        y_units=["octane number"],
    )
    train, test = full.subset(np.arange(50)), full.subset(np.arange(50, 60))
    params = parse_params(PLSParams, {"n_components": 2})
    table = PLS().apply(test, params, PLS().fit(train, params))
    assert test.y is not None
    rmsep = float(np.sqrt(np.mean((table["y_pred_octane"] - test.y[:, 0]) ** 2)))
    published = float(expected["values"]["rmsep_test"][2])
    if not np.isclose(rmsep, published, rtol=expected["tolerance"]["rtol"], atol=0.0):
        raise AssertionError(f"RMSEP {rmsep:.6f} != published {published} (rtol 1e-3)")
    return str(Path(vibechem_core.__file__).parent), rmsep, published


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="vibechem-core wheel smoke test")
    parser.add_argument("--allow-source", action="store_true")
    args = parser.parse_args(argv)
    location, rmsep, published = smoke()
    if not args.allow_source and "site-packages" not in location:
        print(f"FAIL: vibechem_core imported from {location}, not an installed wheel")
        return 1
    print(f"vibechem-core {version('vibechem-core')} from {location}")
    print(f"PASS: gasoline test RMSEP (2 LV) {rmsep:.4f}, published {published}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

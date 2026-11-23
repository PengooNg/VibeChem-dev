<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# vibechem-core (`vibechem_core`)

**Status:** stub. The package is set up (T0.03: `pyproject.toml`, `__version__`, one smoke test); the first code arrives in Phase 1.

**Purpose:** the science library. It holds the spectral data model, file readers and writers, blocks (one file per block), the block registry, metrics and error codes. No pipeline execution, no API, no UI.

**Public API:** none yet. It will cover `SpectralDataset`, the `Block` contract (`block.py`), the registry and the blocks.

**Allowed dependencies** (TECH_STACK.md §3.1): numpy, scipy, scikit-learn, approved chemometrics libraries from TECH_STACK.md §11 (imported only inside block files), and `vibechem_native` (optional).
**Never imports:** `vibechem_engine`, fastapi, anything UI.

**Tests:** `packages/core/tests/`, which mirrors `src/vibechem_core/` exactly (`test_<module>.py`).

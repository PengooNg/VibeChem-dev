<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# vibechem-native (`vibechem_native`)

**Status:** stub. The C++ skeleton arrives in T0.05; the real kernels come in Phase 3.

**Purpose:** optional C++20 kernels (Eigen, nanobind, scikit-build-core) for hot loops. Every kernel has a Python reference in `vibechem_core`, equivalence tests and an automatic fallback to that reference (TECH_STACK.md §5).

**Layout:** `src/`, `include/vibechem/`, `bindings/` (C++) · `python/vibechem_native/` (Python wrapper and fallback dispatch).

**Allowed dependencies** (TECH_STACK.md §3.1): numpy and `vibechem_core` reference functions (for the fallback).
**Never imports:** `vibechem_engine`.

**Tests:** `tests/cpp/` (Catch2) and `tests/python/` (equivalence against the core reference).

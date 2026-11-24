<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# vibechem-native (`vibechem_native`)

**Status:** skeleton (T0.05). It has one stub kernel, `row_mean`. The real kernels come in Phase 3.

**Purpose:** optional C++20 kernels (nanobind, scikit-build-core; Eigen when a kernel needs it) for hot loops. Every kernel has a Python reference, equivalence tests and an automatic fallback to that reference (TECH_STACK.md §5). Phase 3 kernels take their reference from `vibechem_core`. The stub's reference lives in `vibechem_native/_reference.py` because it has no counterpart in core.

**Layout:** `src/` and `include/vibechem/` hold the kernels (a plain C++ library, `vibechem_kernels`). `bindings/` holds the nanobind module `vibechem_native._core`. `python/vibechem_native/` holds the Python wrapper, the fallback dispatch and the type stub `_core.pyi`, which is kept in sync with `bindings/` by hand.

**Public API:**
- `vibechem_native.BACKEND`: `"native"` when the compiled extension imports, otherwise `"python"` (every kernel then runs its NumPy reference).
- `vibechem_native.row_mean(X, n_threads=1)`: mean of each row of a 2-D array, returned as float64 with shape `(n_rows,)`. Raises `ValueError` for a non-2-D input, zero columns or `n_threads < 1`.

**Build:** `uv sync` at the repo root builds the extension (stable ABI, CPython 3.12 and newer). It rebuilds when the C++ sources, `CMakeLists.txt` or `pyproject.toml` change. It needs a C++20 compiler (TECH_STACK.md §2). CMake 3.28 or newer is fetched automatically when none is installed.

**Allowed dependencies** (TECH_STACK.md §3.1): numpy and `vibechem_core` reference functions (for the fallback).
**Never imports:** `vibechem_engine`.

**Tests:**
- `tests/python/` (pytest): the native kernel against the reference, plus the fallback with the extension hidden. Run them with `uv run python scripts/check.py --fast --only native`.
- `tests/cpp/` (Catch2 v3, fetched by CMake). They are not part of the wheel build. Run them from the repo root:
  ```
  cmake -S packages/native -B build/native-tests -DVIBECHEM_BUILD_TESTS=ON
  cmake --build build/native-tests --config Release
  ctest --test-dir build/native-tests -C Release
  ```
  On Windows, Visual Studio ships a `cmake` in `Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin`. CI runs these tests from T0.06.

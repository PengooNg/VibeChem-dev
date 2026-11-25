<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Reader test files: provenance

Sample files for the reader tests in `packages/core/tests/io/`. They are test data only: they live next to the tests (not in `testdata/`, which the installers bundle) and are never shipped (TECH_STACK.md §11.1 rule 4). Each file has a row in `THIRD_PARTY.md`.

| File | Format | Source | Licence | Used by |
|---|---|---|---|---|
| `peach_juice.dpt` | Bruker DPT (ASCII): headerless, tab separated, axis (cm⁻¹) + one intensity column, 1816 points from 4000.11610 to 499.53234, two comment lines (`#`, `;`) at the end | `quasars/orange-spectroscopy` `orangecontrib/spectroscopy/datasets/peach_juice.dpt` at commit `df9246d7d6d7537b18ef5852e30c6ce212ebc92c` (upstream SHA-256 `a2b80596d20bc76788f912e23a3b981a334059189084667b505d4149600b93a2`, CRLF line endings; git stores it with LF per `.gitattributes`) | GPL-3.0-or-later (repository licence; no per-file notes), approved by Quan 2026-11-25 as test data | `test_table.py` (T1.05) |

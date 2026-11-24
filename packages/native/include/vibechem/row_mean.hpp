// SPDX-License-Identifier: GPL-3.0-or-later
// packages/native/include/vibechem/row_mean.hpp
#pragma once

#include <cstddef>
#include <span>

namespace vibechem {

/// Mean of each row of a C-contiguous (row-major) matrix.
///
/// Stub kernel of the native skeleton (T0.05); real kernels arrive in Phase 3.
/// Python reference: vibechem_native._reference.row_mean_reference
/// METHODS.md section: none (skeleton only).
///
/// @param X        n_rows * n_cols values, row-major
/// @param n_rows   number of rows
/// @param n_cols   number of columns (> 0)
/// @param out      n_rows values, receives the row means
/// @param n_threads number of worker threads (>= 1); rows are split into
///                  contiguous blocks, so results do not depend on n_threads
void row_mean(std::span<const double> X, std::size_t n_rows, std::size_t n_cols,
              std::span<double> out, int n_threads = 1);

}  // namespace vibechem

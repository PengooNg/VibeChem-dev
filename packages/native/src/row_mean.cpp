// SPDX-License-Identifier: GPL-3.0-or-later
// packages/native/src/row_mean.cpp
#include "vibechem/row_mean.hpp"

#include <algorithm>
#include <stdexcept>
#include <thread>
#include <vector>

namespace vibechem {

namespace {

// Step 1: Mean of rows [first, last): sum each row left to right, divide by n_cols
void row_mean_range(std::span<const double> X, std::size_t n_cols, std::span<double> out,
                    std::size_t first, std::size_t last) {
    for (std::size_t i = first; i < last; ++i) {
        const auto row = X.subspan(i * n_cols, n_cols);
        double sum = 0.0;
        for (const double value : row) {
            sum += value;
        }
        out[i] = sum / static_cast<double>(n_cols);
    }
}

}  // namespace

void row_mean(std::span<const double> X, std::size_t n_rows, std::size_t n_cols,
              std::span<double> out, int n_threads) {
    if (n_cols == 0 || n_threads < 1 || X.size() != n_rows * n_cols || out.size() != n_rows) {
        throw std::invalid_argument("row_mean: inconsistent shape or n_threads < 1");
    }

    // Step 2: Split the rows into one contiguous block per thread
    const std::size_t n_workers = std::min<std::size_t>(static_cast<std::size_t>(n_threads),
                                                        std::max<std::size_t>(n_rows, 1));
    if (n_workers == 1) {
        row_mean_range(X, n_cols, out, 0, n_rows);
        return;
    }
    const std::size_t block = (n_rows + n_workers - 1) / n_workers;

    // Step 3: Run the blocks in parallel; jthread joins when the vector goes out of scope
    std::vector<std::jthread> workers;
    workers.reserve(n_workers);
    for (std::size_t first = 0; first < n_rows; first += block) {
        const std::size_t last = std::min(first + block, n_rows);
        workers.emplace_back(row_mean_range, X, n_cols, out, first, last);
    }
}

}  // namespace vibechem

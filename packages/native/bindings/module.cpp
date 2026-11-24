// SPDX-License-Identifier: GPL-3.0-or-later
// packages/native/bindings/module.cpp
// nanobind bindings for vibechem_native._core. Call through the Python wrapper
// (vibechem_native.row_mean), which validates input and falls back to NumPy.
#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>

#include "vibechem/row_mean.hpp"

namespace nb = nanobind;

using Matrix = nb::ndarray<const double, nb::ndim<2>, nb::c_contig, nb::device::cpu>;
using Vector = nb::ndarray<double, nb::ndim<1>, nb::c_contig, nb::device::cpu>;

NB_MODULE(_core, m) {
    m.doc() = "VibeChem C++20 kernels (use vibechem_native, not this module directly)";

    // Python reference: vibechem_native._reference.row_mean_reference
    m.def(
        "row_mean",
        [](const Matrix& X, Vector out, int n_threads) {
            const std::size_t n_rows = X.shape(0);
            const std::size_t n_cols = X.shape(1);
            vibechem::row_mean({X.data(), X.size()}, n_rows, n_cols, {out.data(), out.size()},
                               n_threads);
        },
        nb::arg("X"), nb::arg("out"), nb::arg("n_threads") = 1,
        nb::call_guard<nb::gil_scoped_release>(),
        "Write the mean of each row of X into out (GIL released).");
}

// SPDX-License-Identifier: GPL-3.0-or-later
// packages/native/tests/cpp/test_row_mean.cpp
#include <catch2/catch_test_macros.hpp>
#include <catch2/matchers/catch_matchers_floating_point.hpp>

#include <stdexcept>
#include <vector>

#include "vibechem/row_mean.hpp"

using Catch::Matchers::WithinAbs;

TEST_CASE("row_mean of a hand-computed 2x3 matrix", "[row_mean]") {
    const std::vector<double> X{1.0, 2.0, 3.0, 4.0, 5.0, 9.0};
    std::vector<double> out(2);
    vibechem::row_mean(X, 2, 3, out);
    REQUIRE_THAT(out[0], WithinAbs(2.0, 1e-15));
    REQUIRE_THAT(out[1], WithinAbs(6.0, 1e-15));
}

TEST_CASE("row_mean result does not depend on n_threads", "[row_mean]") {
    const std::size_t n_rows = 37;
    const std::size_t n_cols = 11;
    std::vector<double> X(n_rows * n_cols);
    for (std::size_t k = 0; k < X.size(); ++k) {
        X[k] = static_cast<double>((k * 7919) % 101) - 50.0;
    }
    std::vector<double> expected(n_rows);
    vibechem::row_mean(X, n_rows, n_cols, expected, 1);
    for (const int n_threads : {2, 3, 8, 37, 100}) {
        std::vector<double> out(n_rows);
        vibechem::row_mean(X, n_rows, n_cols, out, n_threads);
        REQUIRE(out == expected);
    }
}

TEST_CASE("row_mean with zero rows writes nothing", "[row_mean]") {
    const std::vector<double> X;
    std::vector<double> out;
    REQUIRE_NOTHROW(vibechem::row_mean(X, 0, 4, out, 4));
}

TEST_CASE("row_mean rejects inconsistent input", "[row_mean]") {
    const std::vector<double> X{1.0, 2.0, 3.0, 4.0};
    std::vector<double> out(2);
    REQUIRE_THROWS_AS(vibechem::row_mean(X, 2, 3, out), std::invalid_argument);
    REQUIRE_THROWS_AS(vibechem::row_mean(X, 2, 2, out, 0), std::invalid_argument);
    std::vector<double> short_out(1);
    REQUIRE_THROWS_AS(vibechem::row_mean(X, 2, 2, short_out), std::invalid_argument);
    const std::vector<double> empty;
    std::vector<double> none;
    REQUIRE_THROWS_AS(vibechem::row_mean(empty, 0, 0, none), std::invalid_argument);
}

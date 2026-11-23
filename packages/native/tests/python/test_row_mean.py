# SPDX-License-Identifier: GPL-3.0-or-later
# packages/native/tests/python/test_row_mean.py
"""Equivalence and fallback tests for the stub kernel ``row_mean`` (T0.05)."""

import subprocess
import sys

import numpy as np
import pytest

import vibechem_native
from vibechem_native._reference import row_mean_reference


def test_extension_is_built() -> None:
    # `uv sync` builds the extension; without it the equivalence tests below would
    # silently compare the reference with itself.
    assert vibechem_native.BACKEND == "native"


def test_reference_hand_computed() -> None:
    X = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 9.0]])
    np.testing.assert_array_equal(row_mean_reference(X), [2.0, 6.0])


@pytest.mark.parametrize("n_threads", [1, 2, 3, 8, 64])
@pytest.mark.parametrize("shape", [(0, 4), (1, 1), (1, 700), (7, 3), (50, 401)])
def test_native_matches_reference(shape: tuple[int, int], n_threads: int) -> None:
    rng = np.random.default_rng(20261123)
    X = rng.normal(loc=3.0, scale=10.0, size=shape)
    result = vibechem_native.row_mean(X, n_threads=n_threads)
    assert result.shape == (shape[0],)
    assert result.dtype == np.float64
    np.testing.assert_allclose(result, row_mean_reference(X), rtol=1e-12, atol=1e-12)


def test_result_independent_of_thread_count() -> None:
    X = np.random.default_rng(7).normal(size=(37, 129))
    one = vibechem_native.row_mean(X, n_threads=1)
    for n_threads in (2, 5, 37):
        np.testing.assert_array_equal(vibechem_native.row_mean(X, n_threads=n_threads), one)


def test_converts_non_contiguous_and_integer_input() -> None:
    X = np.arange(24).reshape(4, 6)
    view = X[:, ::2]  # non-contiguous int view
    np.testing.assert_allclose(
        vibechem_native.row_mean(view), row_mean_reference(view.astype(np.float64))
    )


@pytest.mark.parametrize("bad", [np.zeros(3), np.zeros((2, 2, 2)), np.zeros((3, 0))])
def test_rejects_bad_shape(bad: np.ndarray) -> None:
    with pytest.raises(ValueError, match="2-D array"):
        vibechem_native.row_mean(bad)


def test_rejects_bad_thread_count() -> None:
    with pytest.raises(ValueError, match="n_threads"):
        vibechem_native.row_mean(np.ones((2, 2)), n_threads=0)
    with pytest.raises(TypeError):
        vibechem_native.row_mean(np.ones((2, 2)), n_threads=2.0)  # pyright: ignore[reportArgumentType]


def test_huge_thread_count_is_capped() -> None:
    X = np.ones((5, 3))
    np.testing.assert_array_equal(vibechem_native.row_mean(X, n_threads=2**40), np.ones(5))


def test_rejects_complex_input() -> None:
    with pytest.raises(ValueError, match="real values"):
        vibechem_native.row_mean(np.array([[1 + 5j, 2 + 5j]]))


def test_fallback_when_extension_hidden() -> None:
    # Hide the compiled module (sys.modules entry None makes its import fail) in a
    # fresh interpreter, then check the wrapper falls back to the NumPy reference.
    code = (
        "import sys; sys.modules['vibechem_native._core'] = None\n"
        "import numpy as np, vibechem_native\n"
        "X = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 9.0]])\n"
        "print(vibechem_native.BACKEND, vibechem_native.row_mean(X, n_threads=4).tolist())\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True, timeout=60
    )
    assert proc.stdout.strip() == "python [2.0, 6.0]"

# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/blocks/model/test_pls.py
"""Tests for ``model.pls`` (docs/METHODS.md#pls, #pls-lv-sweep, #simpls, #vip)."""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from sklearn.cross_decomposition import PLSRegression  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]

from vibechem_core.block import (
    BLOCK_INPUT_AXIS_MISMATCH,
    BLOCK_INPUT_REQUIREMENT_MISSING,
    BLOCK_PARAM_INVALID,
    load_state,
    parse_params,
    save_state,
)
from vibechem_core.blocks.model.pls import (
    BLOCK_PLS_COMPONENTS_CAPPED,
    BLOCK_PLS_EQUIVALENT_MLR,
    BLOCK_PLS_PRECISION_LOST,
    PLS,
    PLSParams,
    predict_sweep,
    vip,
)
from vibechem_core.blocks.preprocess.scaling import Autoscale, ScalingParams
from vibechem_core.blocks.split import BLOCK_CONSTANT_RESPONSE, BLOCK_MISSING_VALUES
from vibechem_core.data import Axis, SpectralDataset
from vibechem_core.errors import BlockInputError, ParamError, VibeChemWarning
from vibechem_core.reference_datasets import load_expected, load_reference_dataset
from vibechem_core.testing import assert_close, assert_reference

SOURCE = "Mevik & Wehrens 2007, testdata/expected/gasoline_nir_pls.json"


def lib(actual: Any, expected: Any, name: str) -> None:
    assert_close(actual, expected, rtol=1e-10, atol=1e-12, name=name)  # T-lib (METHODS §1)


def iterative(actual: Any, expected: Any, name: str) -> None:
    assert_close(actual, expected, rtol=1e-6, atol=1e-9, name=name)  # T-iter (METHODS §1)


def make_dataset(X: Any, y: Any, unit: str = "nm") -> SpectralDataset:
    x = np.asarray(X, dtype=np.float64)
    y2 = np.asarray(y, dtype=np.float64).reshape(len(x), -1)
    n, p = int(x.shape[0]), int(x.shape[1])
    k = y2.shape[1]
    return SpectralDataset(
        x,
        Axis(np.arange(1.0, p + 1.0), unit),  # type: ignore[arg-type]
        signal_unit="absorbance",
        sample_ids=[f"s{i}" for i in range(n)],
        row_index=np.arange(n),
        source_id="ds_test",
        y=y2,
        y_columns=[f"c{j}" for j in range(k)],
        y_units=["%"] * k,
    )


def params(**values: Any) -> PLSParams:
    return parse_params(PLSParams, values)


def predicted(table: dict[str, Any]) -> np.ndarray[Any, Any]:
    return np.column_stack([v for name, v in table.items() if name.startswith("y_pred_")])


def random_data(n: int, p: int, k: int, seed: int) -> tuple[np.ndarray[Any, Any], ...]:
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, p))
    Y = X[:, :3] @ rng.normal(size=(3, k)) + 0.1 * rng.normal(size=(n, k))
    return X, Y


@pytest.fixture(scope="module")
def gasoline() -> tuple[SpectralDataset, SpectralDataset]:
    data = load_reference_dataset("gasoline_nir")
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
    return full.subset(np.arange(50)), full.subset(np.arange(50, 60))


@pytest.mark.parametrize("algorithm", ["nipals", "simpls"])
def test_gasoline_matches_published_results(
    gasoline: tuple[SpectralDataset, SpectralDataset], algorithm: str
) -> None:
    train, test = gasoline
    values = load_expected("gasoline_nir_pls")["values"]
    rtol = load_expected("gasoline_nir_pls")["tolerance"]["rtol"]  # T-pub
    state = PLS().fit(train, params(n_components=10, algorithm=algorithm))
    pls = "PLS" if algorithm == "nipals" else "PLS (SIMPLS)"

    sweep = predict_sweep(state, test)
    y = test.y
    assert y is not None
    for a in range(1, 11):
        rmsep = float(np.sqrt(((sweep[a] - y) ** 2).mean()))
        assert_reference(method=f"{pls} RMSEP (test)", dataset=f"gasoline_nir, {a} LV",
                         actual=rmsep, expected=values["rmsep_test"][a], rtol=rtol, atol=0.0,
                         source=SOURCE)  # fmt: skip
        assert_reference(method=f"{pls} explained X variance", dataset=f"gasoline_nir, LV {a}",
                         actual=100 * float(state.arrays["x_explained"][a - 1]),
                         expected=values["x_variance_explained_per_component_pct"][a - 1],
                         rtol=rtol, atol=0.0, source=SOURCE)  # fmt: skip
        assert_reference(method=f"{pls} explained Y variance", dataset=f"gasoline_nir, {a} LV",
                         actual=100 * float(state.arrays["y_explained"][:a].sum()),
                         expected=values["y_variance_explained_cumulative_pct"][a - 1],
                         rtol=rtol, atol=0.0, source=SOURCE)  # fmt: skip

    two = PLS().fit(train, params(n_components=2, algorithm=algorithm))
    expected = values["test_predictions_2_components"]["octane"]
    for sample, actual, value in zip(test.sample_ids, predicted(PLS().apply(test, params(), two)),
                                     expected, strict=True):  # fmt: skip
        assert_reference(method=f"{pls} prediction", dataset=f"gasoline_nir, sample {sample}, 2 LV",
                         actual=float(actual[0]), expected=value, rtol=rtol, atol=0.0,
                         source=SOURCE)  # fmt: skip


def test_one_component_matches_hand_calculation() -> None:
    X, y = random_data(12, 6, 1, seed=1)
    X_new = X[:3] + 0.5
    # PLS1, A = 1: w = X0'y / |X0'y|, t = X0 w, q = y0't / t't, y = y_mean + (x - x_mean) w q
    x_mean, y_mean = X.mean(axis=0), y.mean(axis=0)
    w = (X - x_mean).T @ (y - y_mean)
    w /= np.linalg.norm(w)
    t = (X - x_mean) @ w
    q = (y - y_mean).T @ t / (t.T @ t)
    expected = y_mean + (X_new - x_mean) @ w @ q.T

    state = PLS().fit(make_dataset(X, y), params(n_components=1))
    actual = predicted(PLS().apply(make_dataset(X_new, y[:3]), params(), state))
    assert_close(actual, expected, rtol=1e-10, atol=1e-12, name="A = 1")  # T-exact


@pytest.mark.parametrize("scale", [False, True])
@pytest.mark.parametrize("k", [1, 3])
def test_matches_scikit_learn(scale: bool, k: int) -> None:
    X, Y = random_data(30, 8, k, seed=2)
    state = PLS().fit(make_dataset(X, Y), params(n_components=4, scale=scale))
    table = PLS().apply(make_dataset(X[:7], Y[:7]), params(), state)
    sk: Any = PLSRegression(n_components=4, scale=scale)
    reference = np.asarray(sk.fit(X, Y).predict(X[:7])).reshape(7, k)
    lib(predicted(table), reference, "predictions")
    assert list(table) == ["row_index", "sample_id", *(f"y_pred_c{j}" for j in range(k))]
    np.testing.assert_array_equal(table["row_index"], np.arange(7))


@pytest.mark.parametrize("algorithm", ["nipals", "simpls"])
@pytest.mark.parametrize(("k", "check"), [(1, lib), (3, iterative)])
@pytest.mark.parametrize("scale", [False, True])
def test_lv_sweep_equals_separate_fits(k: int, check: Any, scale: bool, algorithm: str) -> None:
    X, Y = random_data(25, 10, k, seed=3)
    train, new = make_dataset(X, Y), make_dataset(X[:6] * 1.1, Y[:6])
    fitted = PLS().fit(train, params(n_components=8, scale=scale, algorithm=algorithm))
    sweep = predict_sweep(fitted, new)
    assert sweep.shape == (9, 6, k)
    check(sweep[0], np.broadcast_to(Y.mean(axis=0), (6, k)), "a = 0 (training mean)")
    for a in range(1, 9):
        separate = PLS().fit(train, params(n_components=a, scale=scale, algorithm=algorithm))
        check(sweep[a], predicted(PLS().apply(new, params(), separate)), f"a = {a}")


@pytest.mark.parametrize("algorithm", ["nipals", "simpls"])
def test_pls2_with_all_components_is_least_squares(algorithm: str) -> None:
    # Full-rank X0 and A = p: PLS spans the same space as ordinary least squares.
    X, Y = random_data(30, 5, 3, seed=4)
    with pytest.warns(VibeChemWarning) as caution:
        state = PLS().fit(make_dataset(X, Y), params(n_components=5, algorithm=algorithm))
    assert [w.message.code for w in caution] == [BLOCK_PLS_EQUIVALENT_MLR]  # type: ignore[union-attr]
    design = np.column_stack([np.ones(30), X])
    beta = np.linalg.lstsq(design, Y, rcond=None)[0]
    X_new = X[:4] - 0.3
    actual = predicted(PLS().apply(make_dataset(X_new, Y[:4]), params(), state))
    iterative(actual, np.column_stack([np.ones(4), X_new]) @ beta, "PLS2 = OLS")


@pytest.mark.parametrize("algorithm", ["nipals", "simpls"])
def test_sign_rule_largest_weight_positive(algorithm: str) -> None:
    X, Y = random_data(20, 7, 2, seed=5)
    state = PLS().fit(make_dataset(X, Y), params(n_components=4, algorithm=algorithm))
    W = state.arrays["weights"]
    columns = np.arange(int(W.shape[1]))
    assert (W[np.abs(W).argmax(axis=0), columns] > 0).all()


def test_y_transform_gives_original_units() -> None:
    X, y = random_data(20, 6, 1, seed=6)
    raw = make_dataset(X, y)
    y_state = Autoscale().fit(raw, parse_params(ScalingParams, {"target": "y"}))
    scaled = Autoscale().apply(raw, parse_params(ScalingParams, {"target": "y"}), y_state)

    plain = PLS().fit(raw, params(n_components=3))
    with_transform = PLS().fit(scaled, params(n_components=3), y_transform=y_state)
    # PLS1 is scale-equivariant in y (METHODS.md#y-scaling), so both are in original units.
    lib(predicted(PLS().apply(raw, params(), with_transform)),
        predicted(PLS().apply(raw, params(), plain)), "apply")  # fmt: skip
    lib(predict_sweep(with_transform, raw), predict_sweep(plain, raw), "sweep")

    # Wrong wirings: an X scaling, raw y with the y scaling (double inversion), and a
    # y scaling fitted on all rows while PLS sees only some (leakage).
    x_state = Autoscale().fit(raw, ScalingParams())
    wrong = [(scaled, x_state), (raw, y_state), (scaled.subset(np.arange(15)), y_state)]
    for spectra, transform in wrong:
        with pytest.raises(BlockInputError) as error:
            PLS().fit(spectra, params(n_components=3), y_transform=transform)
        assert error.value.code == BLOCK_INPUT_REQUIREMENT_MISSING
        assert error.value.params["port_id"] == "y_transform"


def test_state_round_trip(tmp_path: Path) -> None:
    X, Y = random_data(15, 5, 2, seed=7)
    data = make_dataset(X, Y)
    state = PLS().fit(data, params(n_components=3))
    save_state(state, tmp_path / "pls")
    loaded = load_state(tmp_path / "pls")
    np.testing.assert_array_equal(
        predicted(PLS().apply(data, params(), loaded)),
        predicted(PLS().apply(data, params(), state)),
    )


@pytest.mark.parametrize("algorithm", ["nipals", "simpls"])
def test_searched_maximum_is_capped_at_n_min(algorithm: str) -> None:
    # Quan 2026-11-26: a searched maximum above n_min = min(n - 1, p) is capped, with a
    # warning, and n_min components warn that the fit equals MLR (both algorithms).
    X, y = random_data(6, 4, 1, seed=9)
    data = make_dataset(X, y)
    with pytest.warns(VibeChemWarning) as caught:
        state = PLS().fit(data, params(n_components=20, algorithm=algorithm))
    found = [(w.message.code, w.message.params) for w in caught]  # type: ignore[union-attr]
    assert found == [
        (BLOCK_PLS_COMPONENTS_CAPPED, {"from": 20, "to": 4}),
        (BLOCK_PLS_EQUIVALENT_MLR, {"n_components": 4}),
    ]
    assert state.values["n_components"] == 4
    assert predict_sweep(state, data).shape == (5, 6, 1)

    with pytest.warns(VibeChemWarning) as fixed:
        PLS().fit(data, params(n_components=4, n_components_mode="fixed", algorithm=algorithm))
    assert [w.message.code for w in fixed] == [BLOCK_PLS_EQUIVALENT_MLR]  # type: ignore[union-attr]
    for mode in ("search_max", "fixed"):  # one training row: no LV possible
        with pytest.raises(ParamError) as one_row:
            PLS().fit(make_dataset(X[:1], y[:1]),
                      params(n_components=2, n_components_mode=mode, algorithm=algorithm))  # fmt: skip
        assert one_row.value.params["constraint"] == "n_train >= 2"


@pytest.mark.parametrize("algorithm", ["nipals", "simpls"])
def test_errors(algorithm: str) -> None:
    X, y = random_data(6, 4, 1, seed=8)
    data = make_dataset(X, y)
    with pytest.raises(ParamError) as too_many:  # n_min = 4
        PLS().fit(data, params(n_components=5, n_components_mode="fixed", algorithm=algorithm))
    assert too_many.value.code == BLOCK_PARAM_INVALID
    assert too_many.value.params["constraint"] == "1 <= n_components <= 4"

    with pytest.raises(BlockInputError) as constant:
        PLS().fit(make_dataset(X, np.ones(6)), params(n_components=2, algorithm=algorithm))
    assert constant.value.code == BLOCK_CONSTANT_RESPONSE

    no_y = SpectralDataset(X, data.axis, signal_unit="absorbance", sample_ids=data.sample_ids,
                           row_index=data.row_index, source_id="ds_test")  # fmt: skip
    with pytest.raises(BlockInputError) as missing:
        PLS().fit(no_y, params(n_components=2))
    assert missing.value.code == BLOCK_INPUT_REQUIREMENT_MISSING

    state = PLS().fit(data, params(n_components=2))
    with pytest.raises(BlockInputError) as axis:
        PLS().apply(make_dataset(X, y, unit="cm-1"), params(), state)
    assert axis.value.code == BLOCK_INPUT_AXIS_MISMATCH

    X_nan = X.copy()
    X_nan[0, 0] = np.nan
    for call in (lambda: PLS().apply(make_dataset(X_nan, y), params(), state),
                 lambda: PLS().fit(make_dataset(X, np.where(y > y.min(), y, np.nan)),
                                   params(n_components=2))):  # fmt: skip
        with pytest.raises(BlockInputError) as nan:
            call()
        assert nan.value.code == BLOCK_MISSING_VALUES
    PLS.metadata()  # the block definition is valid


@pytest.mark.parametrize("scale", [False, True])
def test_simpls_pls1_matches_nipals(scale: bool) -> None:
    # de Jong (1993): for one y column SIMPLS and NIPALS give the same model.
    X, y = random_data(30, 12, 1, seed=10)
    train, new = make_dataset(X, y), make_dataset(X[:8] - 0.2, y[:8])
    nipals = PLS().fit(train, params(n_components=6, scale=scale))
    simpls = PLS().fit(train, params(n_components=6, scale=scale, algorithm="simpls"))
    iterative(predict_sweep(simpls, new), predict_sweep(nipals, new), "sweep")
    iterative(simpls.arrays["coefficients"], nipals.arrays["coefficients"], "B")
    for name in ("x_explained", "y_explained"):
        iterative(simpls.arrays[name], nipals.arrays[name], name)


def test_simpls_pls2_matches_de_jong_criterion() -> None:
    # Independent value: de Jong's criterion solved directly. r_a maximises
    # ||Y0' X0 r|| with ||r|| = 1 and X0 r orthogonal to the earlier scores, i.e. the top
    # eigenvector of N' X0' Y0 Y0' X0 N on the null space N of (X0' X0 R_(a-1))'.
    X, Y = random_data(30, 9, 3, seed=11)
    x0, y0 = X - X.mean(axis=0), Y - Y.mean(axis=0)
    X_new = X[:5] + 0.3
    state = PLS().fit(make_dataset(X, Y), params(n_components=6, algorithm="simpls"))
    sweep = predict_sweep(state, make_dataset(X_new, Y[:5]))
    rs: list[np.ndarray[Any, Any]] = []
    for a in range(1, 7):
        # Rows a-1 ... p-1 of V' from the full SVD span the null space of the constraints.
        constraints = (x0.T @ x0 @ np.column_stack(rs)).T if rs else np.zeros((0, 9))
        null = np.linalg.svd(constraints)[2][a - 1 :].T if rs else np.eye(9)
        rs.append(null @ np.linalg.eigh(null.T @ x0.T @ y0 @ y0.T @ x0 @ null)[1][:, -1])
        scores = x0 @ np.column_stack(rs)
        B = np.column_stack(rs) @ np.linalg.solve(scores.T @ scores, scores.T @ y0)
        expected = Y.mean(axis=0) + (X_new - X.mean(axis=0)) @ B
        iterative(sweep[a], expected, f"a = {a}")
    T = state.arrays["scores"]
    lib(T.T @ T, np.eye(6), "unit-length, orthogonal scores")


@pytest.mark.parametrize("algorithm", ["nipals", "simpls"])
@pytest.mark.parametrize("k", [1, 3])
def test_vip_squares_sum_to_p(k: int, algorithm: str) -> None:
    X, Y = random_data(25, 10, k, seed=12)
    state = PLS().fit(make_dataset(X, Y), params(n_components=5, algorithm=algorithm))
    for n_lv in (1, 3, None):
        assert_close((vip(state, n_lv) ** 2).sum(), 10.0, rtol=1e-10, atol=1e-12, name="sum")
    with pytest.raises(ValueError, match="n_lv"):
        vip(state, 0)


def test_vip_matches_hand_calculation() -> None:
    # NIPALS PLS1 by hand, A = 1 and A = 2: VIP_j = sqrt(p sum_a SS_a w_ja^2 / sum_a SS_a),
    # SS_a = (t_a't_a) q_a^2 (METHODS.md#vip); A = 1 reduces to sqrt(p) |w_j|.
    X, y = random_data(15, 6, 1, seed=13)
    x0, y0 = X - X.mean(axis=0), (y - y.mean(axis=0))[:, 0]
    ws: list[np.ndarray[Any, Any]] = []
    ss: list[float] = []
    for _ in range(2):
        w = x0.T @ y0 / np.linalg.norm(x0.T @ y0)
        t = x0 @ w
        q = y0 @ t / (t @ t)
        ws.append(w)
        ss.append(float((t @ t) * q**2))
        x0, y0 = x0 - np.outer(t, x0.T @ t / (t @ t)), y0 - t * q
    W, SS = np.column_stack(ws), np.array(ss)
    state = PLS().fit(make_dataset(X, y), params(n_components=2))
    lib(vip(state, 1), np.sqrt(6) * np.abs(W[:, 0]), "A = 1")
    for j, (actual, value) in enumerate(zip(vip(state), np.sqrt(6 * (W**2 @ SS) / SS.sum()),
                                            strict=True)):  # fmt: skip
        assert_reference(method="PLS VIP", dataset=f"random PLS1, variable {j}, 2 LV",
                         actual=float(actual), expected=float(value), rtol=1e-10, atol=1e-12,
                         source="hand calculation (NIPALS by hand)")  # fmt: skip


def test_vip_pls2_sums_over_y_columns() -> None:
    # Two identical y columns: the same components as PLS1, every SS_a doubled, same VIP.
    X, y = random_data(20, 8, 1, seed=14)
    one = vip(PLS().fit(make_dataset(X, y), params(n_components=4)))
    two = vip(PLS().fit(make_dataset(X, np.column_stack([y, y])), params(n_components=4)))
    iterative(two, one, "PLS2 [y, y] = PLS1 y")


def test_simpls_stops_when_no_covariance_is_left() -> None:
    # Rank-2 X: after 2 components S = 0; later components stay 0, as in scikit-learn.
    rng = np.random.default_rng(15)
    base = rng.normal(size=(10, 2))
    X = np.column_stack([base, base.sum(axis=1), base[:, 0] - base[:, 1], 2 * base[:, 0]])
    y = base @ np.array([1.0, -2.0]) + 0.1 * rng.normal(size=10)
    data = make_dataset(X, y)
    with pytest.warns(UserWarning, match="y residual is constant at iteration 2"):
        state = PLS().fit(data, params(n_components=4, algorithm="simpls"))
    sweep = predict_sweep(state, data)
    iterative(sweep[4], sweep[2], "components 3, 4 add nothing")
    assert np.isfinite(vip(state)).all()


def test_simpls_warns_when_scores_lose_orthogonality(
    gasoline: tuple[SpectralDataset, SpectralDataset],
) -> None:
    # Gasoline (50 x 401) at n_min = 49: S = X0'y keeps about 1e-14 of its norm, too few
    # digits for orthogonal scores; NIPALS (deflating X) stays orthogonal. 10 LV warn
    # nothing (the published-results test runs with warnings as errors).
    with warnings.catch_warnings(record=True) as caught:  # also MLR and rank-stop warnings
        warnings.simplefilter("always")
        PLS().fit(gasoline[0], params(n_components=49, algorithm="simpls"))
    lost = [
        w.message for w in caught if getattr(w.message, "code", None) == BLOCK_PLS_PRECISION_LOST
    ]
    assert len(lost) == 1
    assert 10 < lost[0].params["n_components"] <= 49  # type: ignore[union-attr]

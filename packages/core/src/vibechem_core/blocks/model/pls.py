# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/blocks/model/pls.py
"""
Block:          PLS regression, NIPALS or SIMPLS (PLS1 and PLS2), with VIP
Class:          model
Ports:          in  -> spectra     : Spectra   (requires y)
                in  -> y_transform : Transform (optional; y scaling to invert)
                out -> predictions : Table
                out -> model       : Model
Reference:      Wold, Ruhe, Wold & Dunn (1984); Geladi & Kowalski (1986);
                Mevik & Wehrens (2007), J. Stat. Softw. 18(2); de Jong (1993), Chemom.
                Intell. Lab. Syst. 18, 251-263 (SIMPLS); Wold, Johansson & Cocchi (1993) (VIP)
METHODS:        docs/METHODS.md#pls, #pls-lv-sweep, #simpls, #vip
Implementation: scikit-learn ``PLSRegression`` (NIPALS), wrapped; SIMPLS, LV sweep and
                VIP own NumPy (VIP ported from pengoo ``calculate_vip``)
Fitted:         Yes (means, weights, loadings and rotations learned in ``fit``)
Reviewer:       Quan

``n_components_mode`` says what ``n_components`` is (Quan, 2026-11-26): ``search_max``
(default) is the upper end of the LV sweep, capped at n_min = min(n_train - 1, p) with
warning ``BLOCK_PLS_COMPONENTS_CAPPED``; ``fixed`` is the chosen model size, and above
n_min the block does not run. A fit with exactly n_min components warns
``BLOCK_PLS_EQUIVALENT_MLR``. ``apply`` predicts with all fitted latent variables; :func:`predict_sweep`
gives the predictions for every LV count 0 ... A from the same fit. When the
``y_transform`` input (a scaling block fitted with ``target = y``) is connected, the
state keeps its mean and scale and every prediction is mapped back to original Y
units (METHODS.md §1, #y-scaling). ``algorithm = simpls`` fits de Jong's SIMPLS with the
same parameters and rules (same predictions as NIPALS for PLS1); :func:`vip` gives the
VIP of every variable from the state. The predictions table has the columns
``row_index``, ``sample_id`` and ``y_pred_<column>`` (DATA_MODEL.md §4.2 ``Results``).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray
from sklearn.cross_decomposition import PLSRegression  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]

from vibechem_core.block import (
    BLOCK_INPUT_REQUIREMENT_MISSING,
    BLOCK_PARAM_INVALID,
    Block,
    Param,
    State,
    port,
)
from vibechem_core.blocks.preprocess import check_axis
from vibechem_core.blocks.split import BLOCK_CONSTANT_RESPONSE, BLOCK_MISSING_VALUES
from vibechem_core.data import Axis, AxisUnit, SpectralDataset
from vibechem_core.errors import BlockInputError, ErrorParam, ParamError, VibeChemWarning

# Warning: the searched maximum LV count was above n_min and was capped (``from``, ``to``).
BLOCK_PLS_COMPONENTS_CAPPED = "BLOCK_PLS_COMPONENTS_CAPPED"
# Warning: fitted with n_min components, which equals multiple linear regression.
BLOCK_PLS_EQUIVALENT_MLR = "BLOCK_PLS_EQUIVALENT_MLR"
# Warning: SIMPLS scores lost orthogonality from LV ``n_components`` on (``max_deviation``).
BLOCK_PLS_PRECISION_LOST = "BLOCK_PLS_PRECISION_LOST"

# State array name -> PLSRegression attribute (the means and SDs are private in 1.9.1).
_FITTED_ATTRIBUTES = {
    "x_mean": "_x_mean",
    "y_mean": "_y_mean",
    "x_std": "_x_std",
    "y_std": "_y_std",
    "weights": "x_weights_",
    "loadings": "x_loadings_",
    "y_loadings": "y_loadings_",
    "rotations": "x_rotations_",
    "scores": "x_scores_",
    "coefficients": "coef_",  # (k, p); stored transposed as B (p, k)
}


@dataclass(frozen=True)
class PLSParams:
    n_components: int = Param(20, min=1)
    n_components_mode: str = Param("search_max", choices=("search_max", "fixed"))
    scale: bool = Param(False, advanced=True)
    algorithm: str = Param("nipals", choices=("nipals", "simpls"), advanced=True)


class PLS(Block):
    block_id = "model.pls"
    version = "1.1.0"
    icon = "glyph-pls"
    references = (
        "wold1984collinearity",
        "geladi1986pls",
        "hoskuldsson1988",
        "wold2001pls",
        "mevik2007pls",
        "dejong1993simpls",
        "wold1993vip",
        "pedregosa2011sklearn",
    )
    fitted = True
    inputs = (
        port("spectra", "Spectra", requires=("y",)),
        port("y_transform", "Transform", required=False),
    )
    outputs = (port("predictions", "Table"), port("model", "Model"))
    params_type = PLSParams
    implementation = ("scikit-learn", "sklearn.cross_decomposition.PLSRegression")

    def fit(
        self, spectra: SpectralDataset, params: PLSParams, y_transform: State | None = None
    ) -> State:
        y = _response(spectra)
        X = _no_nan(spectra.X, y)
        n_lv = params.n_components
        bound = min(spectra.n_samples - 1, spectra.n_variables)
        capped = bound < n_lv and params.n_components_mode == "search_max" and bound >= 1
        if bound < n_lv and not capped:  # fixed size above n_min, or one training row
            constraint = "n_train >= 2" if bound < 1 else f"1 <= n_components <= {bound}"
            raise ParamError(
                BLOCK_PARAM_INVALID,
                {"param_id": "n_components", "reason": "constraint", "constraint": constraint},
            )
        if bool((np.ptp(y, axis=0) == 0).all()):
            raise BlockInputError(BLOCK_CONSTANT_RESPONSE, {"port_id": "spectra"})
        inverse = _inverse_arrays(y_transform, spectra.y_columns, y)
        if capped:
            warnings.warn(
                VibeChemWarning(BLOCK_PLS_COMPONENTS_CAPPED, {"from": n_lv, "to": bound}),
                stacklevel=2,
            )
            n_lv = bound
        if bound == n_lv:
            warnings.warn(
                VibeChemWarning(BLOCK_PLS_EQUIVALENT_MLR, {"n_components": n_lv}), stacklevel=2
            )

        # Step 1: Centre X and Y with the training means (scale = true also divides by
        # the training SDs, ddof 1; Q4). Step 2: NIPALS loop (scikit-learn) or SIMPLS
        # (own code, #simpls); the largest-|w| element of each weight vector is positive (N16)
        if params.algorithm == "simpls":
            fit = _simpls(X, y, n_lv, params.scale)
        else:
            # tol bounds the squared change of w: 1e-20 is |dw| < 1e-10 (1e-06 stopped PLS2 early, #60)
            pls: Any = PLSRegression(
                n_components=n_lv, scale=params.scale, max_iter=10_000, tol=1e-20
            )
            pls.fit(X, y)
            fit = {
                name: np.asarray(getattr(pls, attribute), dtype=np.float64)
                for name, attribute in _FITTED_ATTRIBUTES.items()
            }
            fit["coefficients"] = fit["coefficients"].T
        x_mean, y_mean, x_std, y_std = (fit[k] for k in ("x_mean", "y_mean", "x_std", "y_std"))

        # Step 3: Store means, W, P, Q, R, T, B and the explained X/Y variance per
        # component (ss(t_a p_a') / ss(X0), ss(t_a q_a') / ss(Y0), in the fitted space)
        T, P, Q = fit["scores"], fit["loadings"], fit["y_loadings"]
        tt = (T**2).sum(axis=0)
        x0 = (X - x_mean) / x_std
        y0 = (y - y_mean) / y_std
        arrays: dict[str, NDArray[np.float64]] = {
            **fit,
            "x_explained": tt * (P**2).sum(axis=0) / (x0**2).sum(),
            "y_explained": tt * (Q**2).sum(axis=0) / (y0**2).sum(),
            "axis": spectra.axis.values,
            **inverse,
        }
        return State(
            {
                "n_components": n_lv,
                "scale": params.scale,
                "algorithm": params.algorithm,
                "y_columns": list(spectra.y_columns),
                "axis_unit": spectra.axis.unit,
                "y_transform": bool(inverse),
            },
            arrays,
        )

    def apply(
        self,
        spectra: SpectralDataset,
        params: PLSParams,  # noqa: ARG002  (everything needed is in the state)
        state: State,
        y_transform: State | None = None,  # noqa: ARG002  (its arrays are in the state)
    ) -> dict[str, NDArray[Any]]:
        X = _checked_X(spectra, state)
        a = state.arrays

        # Step 4: y = y_mean + (x - x_mean) B, then back to original Y units
        y_pred = _to_original_units(state, a["y_mean"] + (X - a["x_mean"]) @ a["coefficients"])
        return _table(spectra, state, y_pred)


def predict_sweep(state: State, spectra: SpectralDataset) -> NDArray[np.float64]:
    """Predictions for every LV count 0 ... A from one fit, shape (A + 1, n, k).

    Index ``a`` holds y_a = y_mean + (x - x_mean) R[:, :a] Q[:, :a]' (METHODS.md
    #pls-lv-sweep); ``a = 0`` is the training mean. Original Y units, as ``apply``.
    """
    X = _checked_X(spectra, state)
    a = state.arrays
    t = ((X - a["x_mean"]) / a["x_std"]) @ a["rotations"]  # (n, A) scores of the new rows
    steps = t[:, :, None] * a["y_loadings"].T[None, :, :] * a["y_std"]  # (n, A, k)
    cumulative = np.concatenate([np.zeros_like(steps[:, :1]), steps.cumsum(axis=1)], axis=1)
    return _to_original_units(state, a["y_mean"] + cumulative.transpose(1, 0, 2))


_COMPONENT_ARRAYS = (
    "weights",
    "loadings",
    "y_loadings",
    "rotations",
    "scores",
    "x_explained",
    "y_explained",
)


def truncate(state: State, n_lv: int) -> State:
    """The state with its first ``n_lv`` components, B = R Q' rebuilt from them.

    Components are fitted one after another, so this equals a refit with
    ``n_components = n_lv`` on the same rows (METHODS.md#pls-lv-sweep).
    """
    n_fitted = cast(int, state.values["n_components"])
    if not 1 <= n_lv <= n_fitted:
        raise ValueError(f"n_lv must be in 1 ... {n_fitted}, got {n_lv}")
    a = dict(state.arrays)
    for name in _COMPONENT_ARRAYS:
        a[name] = a[name][..., :n_lv]
    a["coefficients"] = (a["rotations"] @ a["y_loadings"].T) * a["y_std"] / a["x_std"][:, None]
    return State({**state.values, "n_components": n_lv}, a)


def vip(state: State, n_lv: int | None = None) -> NDArray[np.float64]:
    """VIP of every X variable from the first ``n_lv`` components (default all), shape (p,).

    METHODS.md#vip; PLS2 sums over the Y columns, so it depends on their scaling (Q9).
    """
    n_fitted = cast(int, state.values["n_components"])
    n_lv = n_fitted if n_lv is None else n_lv
    if not 1 <= n_lv <= n_fitted:
        raise ValueError(f"n_lv must be in 1 ... {n_fitted}, got {n_lv}")
    a = state.arrays
    W, T, Q = (a[name][:, :n_lv] for name in ("weights", "scores", "y_loadings"))

    # Step 1: SS_a = (t_a' t_a) sum_m q_ma^2
    ss = (T**2).sum(axis=0) * (Q**2).sum(axis=0)
    # Step 2: Weights normalised to unit length (a zero column only follows a rank stop)
    norms = np.linalg.norm(W, axis=0)
    w = W / np.where(norms > 0, norms, 1.0)
    # Step 3: Sum of the squared weights, each component weighted by SS_a
    weighted = (w**2) @ ss
    # Step 4: Scale by p / sum SS_a and take the square root
    return np.sqrt(W.shape[0] * weighted / ss.sum())


def _simpls(
    X: NDArray[np.float64], y: NDArray[np.float64], n_lv: int, scale: bool
) -> dict[str, NDArray[np.float64]]:
    """de Jong (1993) SIMPLS; ``# Step`` comments follow METHODS.md#simpls.

    Same arrays as the NIPALS wrap: R maps the centred X to unit-length scores T,
    P = X0'T, Q = Y0'T, B = R Q' in original X/Y units; ``weights`` is R with unit
    columns (the direction VIP uses).
    """
    x_mean, y_mean = X.mean(axis=0), y.mean(axis=0)
    x_std, y_std = np.ones(X.shape[1]), np.ones(y.shape[1])
    if scale:  # as scikit-learn: ddof 1, a constant column keeps scale 1
        x_std, y_std = X.std(axis=0, ddof=1), y.std(axis=0, ddof=1)
        x_std[x_std == 0], y_std[y_std == 0] = 1.0, 1.0
    x0, y0 = (X - x_mean) / x_std, (y - y_mean) / y_std
    (n, p), k = x0.shape, y0.shape[1]
    R, P, V = np.zeros((p, n_lv)), np.zeros((p, n_lv)), np.zeros((p, n_lv))
    T, Q = np.zeros((n, n_lv)), np.zeros((k, n_lv))

    # Step 1: Cross-product S = X0' Y0 (``cross``)
    cross = x0.T @ y0
    first = np.linalg.norm(cross, 2)
    for a in range(n_lv):
        # Step 2: r_a = first left singular vector of S
        u, singular, _ = np.linalg.svd(cross, full_matrices=False)
        if singular[0] <= np.finfo(np.float64).eps * max(n, p) * first:
            # Same as scikit-learn's NIPALS: no covariance left, later components stay 0.
            warnings.warn(f"y residual is constant at iteration {a}", stacklevel=3)
            break
        r = u[:, 0]
        # Step 3: t_a = X0 r_a, centred, ||t_a|| = 1; r_a divided by the same norm
        t = x0 @ r
        t -= t.mean()
        norm = np.linalg.norm(t)
        t, r = t / norm, r / norm
        # Step 4: p_a = X0' t_a, q_a = Y0' t_a
        p_a, q_a = x0.T @ t, y0.T @ t
        # Step 5: v_a = p_a orthogonalised against v_1 ... v_(a-1), normalised
        v = p_a - V[:, :a] @ (V[:, :a].T @ p_a)
        v /= np.linalg.norm(v)
        # Step 6: Deflate S <- S - v_a (v_a' S)
        cross -= np.outer(v, v @ cross)
        R[:, a], T[:, a], P[:, a], Q[:, a], V[:, a] = r, t, p_a, q_a, v

    # Sign rule N16: largest-|r| element of each component positive
    sign = np.sign(R[np.abs(R).argmax(axis=0), np.arange(n_lv)])
    sign[sign == 0] = 1.0
    for matrix in (R, T, P, Q):
        np.multiply(matrix, sign, out=matrix)
    # B = R Q' needs orthonormal scores; S = X0'Y0 loses digits once little covariance is left,
    # so components from the first non-orthonormal one on are dropped (set to 0, as a rank stop).
    used = int((np.linalg.norm(T, axis=0) > 0).sum())
    deviation = np.triu(np.abs(T[:, :used].T @ T[:, :used] - np.eye(used))).max(axis=0, initial=0)
    lost = np.flatnonzero(deviation > 1e-6)  # T-iter rtol (METHODS.md §1)
    if lost.size:
        warnings.warn(
            VibeChemWarning(
                BLOCK_PLS_PRECISION_LOST,
                {"n_components": int(lost[0]) + 1, "max_deviation": float(deviation.max())},
            ),
            stacklevel=3,
        )
        for matrix in (R, T, P, Q):
            matrix[:, lost[0] :] = 0.0
    norms = np.linalg.norm(R, axis=0)
    # Step 7: B = R Q' (back in original X and Y units, as scikit-learn's coef_)
    return {
        "x_mean": x_mean,
        "y_mean": y_mean,
        "x_std": x_std,
        "y_std": y_std,
        "weights": R / np.where(norms > 0, norms, 1.0),
        "loadings": P,
        "y_loadings": Q,
        "rotations": R,
        "scores": T,
        "coefficients": (R @ Q.T) * y_std / x_std[:, None],
    }


def _response(spectra: SpectralDataset) -> NDArray[np.float64]:
    if spectra.y is None:
        raise BlockInputError(
            BLOCK_INPUT_REQUIREMENT_MISSING, {"port_id": "spectra", "requirement": "y"}
        )
    return spectra.y


def _inverse_arrays(
    y_transform: State | None, y_columns: tuple[str, ...], y: NDArray[np.float64]
) -> dict[str, NDArray[np.float64]]:
    """Mean and scale of a ``target = y`` scaling state fitted on these rows' y."""
    if y_transform is None:
        return {}
    params: dict[str, ErrorParam] = {
        "port_id": "y_transform",
        "requirement": "y",
        "expected": ", ".join(y_columns),
    }
    if y_transform.values.get("target") != "y" or y_transform.values.get("y_columns") != list(
        y_columns
    ):
        raise BlockInputError(BLOCK_INPUT_REQUIREMENT_MISSING, params)
    mean, scale = y_transform.arrays["mean"], y_transform.arrays["scale"]
    # Every y scaling centres with its training mean: a y that is not centred here was
    # not scaled by this transform on these rows (raw y, or a scaler fitted on other rows).
    if (np.abs(y.mean(axis=0)) * scale > 1e-9 * (np.abs(mean) + scale)).any():
        raise BlockInputError(BLOCK_INPUT_REQUIREMENT_MISSING, params)
    return {"y_inverse_mean": mean, "y_inverse_scale": scale}


def _to_original_units(state: State, y: NDArray[np.float64]) -> NDArray[np.float64]:
    if not state.values["y_transform"]:
        return y
    return y * state.arrays["y_inverse_scale"] + state.arrays["y_inverse_mean"]


def _checked_X(spectra: SpectralDataset, state: State) -> NDArray[np.float64]:
    fitted_axis = Axis(state.arrays["axis"], cast(AxisUnit, state.values["axis_unit"]))
    check_axis("spectra", spectra.axis, fitted_axis)
    return _no_nan(spectra.X)


def _no_nan(X: NDArray[np.float64], y: NDArray[np.float64] | None = None) -> NDArray[np.float64]:
    """``BLOCK_MISSING_VALUES`` for NaN (only direct API calls; the engine drops such rows, N1)."""
    if np.isnan(X).any() or (y is not None and np.isnan(y).any()):
        raise BlockInputError(BLOCK_MISSING_VALUES, {"port_id": "spectra"})
    return X


def _table(
    spectra: SpectralDataset, state: State, y_pred: NDArray[np.float64]
) -> dict[str, NDArray[Any]]:
    table: dict[str, NDArray[Any]] = {
        "row_index": spectra.row_index,
        "sample_id": np.array(spectra.sample_ids, dtype=np.str_),
    }
    for j, column in enumerate(cast(list[str], state.values["y_columns"])):
        table[f"y_pred_{column}"] = y_pred[:, j]
    return table

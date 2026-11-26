# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/blocks/model/pls.py
"""
Block:          PLS regression, NIPALS (PLS1 and PLS2)
Class:          model
Ports:          in  -> spectra     : Spectra   (requires y)
                in  -> y_transform : Transform (optional; y scaling to invert)
                out -> predictions : Table
                out -> model       : Model
Reference:      Wold, Ruhe, Wold & Dunn (1984); Geladi & Kowalski (1986);
                Mevik & Wehrens (2007), J. Stat. Softw. 18(2)
METHODS:        docs/METHODS.md#pls, #pls-lv-sweep
Implementation: scikit-learn ``PLSRegression`` (NIPALS), wrapped; LV sweep own NumPy
Fitted:         Yes (means, weights, loadings and rotations learned in ``fit``)
Reviewer:       Quan

``apply`` predicts with all ``n_components`` latent variables; :func:`predict_sweep`
gives the predictions for every LV count 0 ... A from the same fit. When the
``y_transform`` input (a scaling block fitted with ``target = y``) is connected, the
state keeps its mean and scale and every prediction is mapped back to original Y
units (METHODS.md §1, #y-scaling). The predictions table has the columns
``row_index``, ``sample_id`` and ``y_pred_<column>`` (DATA_MODEL.md §4.2 ``Results``).
"""

from __future__ import annotations

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
from vibechem_core.blocks.split import BLOCK_CONSTANT_RESPONSE
from vibechem_core.data import Axis, AxisUnit, SpectralDataset
from vibechem_core.errors import BlockInputError, ErrorParam, ParamError

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
    scale: bool = Param(False, advanced=True)


class PLS(Block):
    block_id = "model.pls"
    version = "1.0.0"
    icon = "glyph-pls"
    references = (
        "wold1984collinearity",
        "geladi1986pls",
        "hoskuldsson1988",
        "wold2001pls",
        "mevik2007pls",
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
        X = spectra.X
        A = params.n_components
        bound = min(spectra.n_samples - 1, spectra.n_variables)
        if bound < A:
            raise ParamError(
                BLOCK_PARAM_INVALID,
                {
                    "param_id": "n_components",
                    "reason": "constraint",
                    "constraint": f"1 <= n_components <= {bound}",
                },
            )
        if bool((np.ptp(y, axis=0) == 0).all()):
            raise BlockInputError(BLOCK_CONSTANT_RESPONSE, {"port_id": "spectra"})
        inverse = _inverse_arrays(y_transform, spectra.y_columns)

        # Step 1: Centre X and Y with the training means (scale = true also divides by
        # the training SDs, ddof 1; Q4). Step 2: NIPALS loop; scikit-learn makes the
        # largest-|w| element of each weight vector positive (sign rule N16)
        pls: Any = PLSRegression(n_components=A, scale=params.scale, max_iter=500, tol=1e-06)
        pls.fit(X, y)
        fit = {
            name: np.asarray(getattr(pls, attribute), dtype=np.float64)
            for name, attribute in _FITTED_ATTRIBUTES.items()
        }
        x_mean, y_mean, x_std, y_std = (fit[k] for k in ("x_mean", "y_mean", "x_std", "y_std"))

        # Step 3: Store means, W, P, Q, R, T, B and the explained X/Y variance per
        # component (ss(t_a p_a') / ss(X0), ss(t_a q_a') / ss(Y0), in the fitted space)
        T, P, Q = fit["scores"], fit["loadings"], fit["y_loadings"]
        tt = (T**2).sum(axis=0)
        x0 = (X - x_mean) / x_std
        y0 = (y - y_mean) / y_std
        arrays: dict[str, NDArray[np.float64]] = {
            **fit,
            "coefficients": fit["coefficients"].T,
            "x_explained": tt * (P**2).sum(axis=0) / (x0**2).sum(),
            "y_explained": tt * (Q**2).sum(axis=0) / (y0**2).sum(),
            "axis": spectra.axis.values,
            **inverse,
        }
        return State(
            {
                "n_components": A,
                "scale": params.scale,
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


def _response(spectra: SpectralDataset) -> NDArray[np.float64]:
    if spectra.y is None:
        raise BlockInputError(
            BLOCK_INPUT_REQUIREMENT_MISSING, {"port_id": "spectra", "requirement": "y"}
        )
    return spectra.y


def _inverse_arrays(
    y_transform: State | None, y_columns: tuple[str, ...]
) -> dict[str, NDArray[np.float64]]:
    """Mean and scale of a ``target = y`` scaling state for the same Y columns."""
    if y_transform is None:
        return {}
    if y_transform.values.get("target") != "y" or y_transform.values.get("y_columns") != list(
        y_columns
    ):
        params: dict[str, ErrorParam] = {
            "port_id": "y_transform",
            "requirement": "y",
            "expected": ", ".join(y_columns),
        }
        raise BlockInputError(BLOCK_INPUT_REQUIREMENT_MISSING, params)
    return {
        "y_inverse_mean": y_transform.arrays["mean"],
        "y_inverse_scale": y_transform.arrays["scale"],
    }


def _to_original_units(state: State, y: NDArray[np.float64]) -> NDArray[np.float64]:
    if not state.values["y_transform"]:
        return y
    return y * state.arrays["y_inverse_scale"] + state.arrays["y_inverse_mean"]


def _checked_X(spectra: SpectralDataset, state: State) -> NDArray[np.float64]:
    fitted_axis = Axis(state.arrays["axis"], cast(AxisUnit, state.values["axis_unit"]))
    check_axis("spectra", spectra.axis, fitted_axis)
    return spectra.X


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

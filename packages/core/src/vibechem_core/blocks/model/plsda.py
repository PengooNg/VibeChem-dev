# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/blocks/model/plsda.py
"""
Block:          PLS discriminant analysis (PLS-DA), binary and multi-class
Class:          model
Ports:          in  -> spectra     : Spectra (requires classes)
                out -> predictions : Table
                out -> model       : Model
Reference:      Barker & Rayens (2003), J. Chemom. 17(3), 166-173; Ballabio & Consonni
                (2013), Anal. Methods 5, 3790-3798
METHODS:        docs/METHODS.md#plsda
Implementation: our ``model.pls`` block (NIPALS, scikit-learn ``PLSRegression``) on a
                NumPy indicator matrix
Fitted:         Yes (class list and the PLS2 state learned in ``fit``)
Reviewer:       Quan

Decision rule: max rule only. A sample goes to the class with the largest predicted
indicator value; ties go to the lowest class index (classes sorted by label). With two
classes the rows of the predicted indicator matrix sum to 1, so the rule equals
"score of the second class > 0.5". ``n_components`` and ``n_components_mode`` follow
``model.pls`` (same caps, warnings and errors); X and the indicator matrix are
mean-centred only. The predictions table has the columns ``row_index``, ``sample_id``,
``class_pred`` and ``score_<class>`` (DATA_MODEL.md §4.2 ``Results``). ``apply`` uses all fitted latent
variables; the state is a ``model.pls`` state plus ``classes``, so
:func:`vibechem_core.blocks.model.pls.predict_sweep` gives the scores for every LV count
(argmax over the last axis = predicted class index) for choosing the LV count in CV.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray

from vibechem_core.block import BLOCK_INPUT_REQUIREMENT_MISSING, Block, Param, State, port
from vibechem_core.blocks.model.pls import PLS, PLSParams
from vibechem_core.data import SpectralDataset
from vibechem_core.errors import BlockInputError


@dataclass(frozen=True)
class PLSDAParams:
    n_components: int = Param(20, min=1)
    n_components_mode: str = Param("search_max", choices=("search_max", "fixed"))


class PLSDA(Block):
    block_id = "model.plsda"
    version = "1.0.0"
    icon = "glyph-plsda"
    references = ("barker2003plsda", "ballabio2013plsda", "pedregosa2011sklearn")
    fitted = True
    inputs = (port("spectra", "Spectra", requires=("classes",)),)
    outputs = (port("predictions", "Table"), port("model", "Model"))
    params_type = PLSDAParams
    implementation = ("scikit-learn", "sklearn.cross_decomposition.PLSRegression")

    def fit(self, spectra: SpectralDataset, params: PLSDAParams) -> State:
        if spectra.classes is None:
            raise BlockInputError(
                BLOCK_INPUT_REQUIREMENT_MISSING, {"port_id": "spectra", "requirement": "classes"}
            )

        # Step 1: Sorted class list c_1 ... c_G of the training rows
        classes, codes = np.unique(np.asarray(spectra.classes), return_inverse=True)

        # Step 2: n x G indicator matrix (y_ig = 1 if sample i is in class g)
        indicator = np.eye(classes.size)[codes]

        # Step 3: PLS2 fit, X and Y mean-centred only; one class = constant Y ->
        # BLOCK_CONSTANT_RESPONSE from the PLS block
        names = [str(c) for c in classes]
        dummy = replace(
            spectra,
            y=indicator,
            y_columns=names,
            y_units=["indicator"] * len(names),
            classes=None,
            class_column=None,
            metadata=None,  # its column names could clash with the class names
        )
        pls = PLS().fit(
            dummy,
            PLSParams(
                params.n_components, params.n_components_mode, scale=False, algorithm="nipals"
            ),
        )
        return State({**pls.values, "classes": names}, pls.arrays)

    def apply(
        self,
        spectra: SpectralDataset,
        params: PLSDAParams,  # noqa: ARG002  (everything needed is in the state)
        state: State,
    ) -> dict[str, NDArray[Any]]:
        classes = cast(list[str], state.values["classes"])

        # Step 4: Predicted indicator values y = y_mean + (x - x_mean) B (PLS block)
        table = PLS().apply(spectra, PLSParams(), state)
        scores = np.column_stack([table[f"y_pred_{c}"] for c in classes])

        # Step 5: Max rule; argmax returns the first maximum, so ties -> lowest class index
        predicted = np.asarray(classes, dtype=np.str_)[scores.argmax(axis=1)]
        return {
            "row_index": table["row_index"],
            "sample_id": table["sample_id"],
            "class_pred": predicted,
            **{f"score_{c}": scores[:, g] for g, c in enumerate(classes)},
        }

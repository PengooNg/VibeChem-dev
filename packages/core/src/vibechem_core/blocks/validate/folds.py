# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/blocks/validate/folds.py
"""
Block:          Cross-validation fold generators: k-fold, venetian blinds, contiguous
                blocks, leave-one-out, repeated k-fold, group k-fold
Class:          validate
Ports:          in  -> spectra : Spectra (group k-fold: requires groups)
                out -> folds   : Folds
Reference:      Stone (1974), J. R. Stat. Soc. B 36, 111-147;
                Eigenvector Research, cross-validation documentation;
                Esbensen & Geladi (2010), J. Chemometrics 24, 168-187
METHODS:        docs/METHODS.md#k-fold, #venetian-blinds, #contiguous-blocks, #loo,
                #repeated-k-fold, #group-k-fold
Implementation: wraps sklearn.model_selection KFold, LeaveOneOut, LeaveOneGroupOut,
                RepeatedKFold, GroupKFold; venetian blinds and contiguous blocks are
                one line of NumPy each. Group-leak assertion ported from pengoo
                ``get_cv_splits`` (TECH_STACK.md §11.2).
Fitted:         No (folds are made once from the row order and the Generator)
Reviewer:       Quan

Each block returns one ``FoldSet`` whose indices are ``row_index`` values. Shuffled
schemes take the Generator ``rng`` when given, else ``numpy.random.default_rng(seed)``,
and pass one integer drawn from it to scikit-learn; ``FoldSet.seed`` is the ``seed``
parameter, or with an explicit ``rng`` the drawn integer (``None`` when unshuffled).
Schemes that ignore groups set ``groups_respected`` false when the input has
``group_ids`` (the engine logs ``VALIDATION_GROUPS_IGNORED``, METHODS.md N10).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from sklearn.model_selection import GroupKFold as SkGroupKFold  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]
from sklearn.model_selection import KFold as SkKFold  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]
from sklearn.model_selection import LeaveOneGroupOut  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]
from sklearn.model_selection import LeaveOneOut as SkLeaveOneOut  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]
from sklearn.model_selection import RepeatedKFold as SkRepeatedKFold  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]

from vibechem_core.block import (
    BLOCK_INPUT_REQUIREMENT_MISSING,
    BLOCK_PARAM_INVALID,
    Block,
    NoParams,
    Param,
    port,
)
from vibechem_core.data import Fold, FoldSet, SpectralDataset
from vibechem_core.errors import BlockInputError, ParamError

FOLDS_OUTPUT = (port("folds", "Folds"),)


@dataclass(frozen=True)
class FoldParams:
    k: int = Param(5, min=2)


@dataclass(frozen=True)
class ShuffledFoldParams(FoldParams):
    shuffle: bool = Param(True)
    seed: int = Param(0, min=0, visible_if=("shuffle", (True,)))


@dataclass(frozen=True)
class RepeatedKFoldParams(FoldParams):
    repeats: int = Param(5, min=1)
    seed: int = Param(0, min=0)


def _check_k(k: int, n_units: int) -> None:
    """``BLOCK_PARAM_INVALID`` unless 2 <= k <= n_units (no silent switch to LOO, Q8)."""
    if not 2 <= k <= n_units:  # k < 2 only through direct calls (parse_params checks min)
        raise ParamError(
            BLOCK_PARAM_INVALID,
            {"param_id": "k", "reason": "constraint", "constraint": f"2 <= k <= {n_units}"},
        )


def _groups(spectra: SpectralDataset) -> NDArray[np.intp]:
    """Group number of each row (groups in sorted label order).

    Absent groups or an empty group label raise ``BLOCK_INPUT_REQUIREMENT_MISSING``.
    """
    labels = spectra.group_ids
    if labels is None or "" in labels:
        raise BlockInputError(
            BLOCK_INPUT_REQUIREMENT_MISSING, {"port_id": "spectra", "requirement": "groups"}
        )
    return np.unique(np.asarray(labels), return_inverse=True)[1]


def _seeds(seed: int, rng: np.random.Generator | None) -> tuple[int, int]:
    """(integer for scikit-learn, value recorded in ``FoldSet.seed``)."""
    drawn = int((np.random.default_rng(seed) if rng is None else rng).integers(2**32))
    return drawn, seed if rng is None else drawn


def _sk_validation(splitter: Any, n: int, groups: NDArray[np.intp] | None = None) -> Iterator[Any]:
    """Validation positions of each scikit-learn split, in scikit-learn's order."""
    return (va for _, va in splitter.split(np.zeros((n, 1)), groups=groups))


def _fold_set(
    spectra: SpectralDataset,
    scheme: str,
    validation: Iterable[NDArray[np.intp]],
    k: int,
    groups: NDArray[np.intp] | None,
    seed: int | None,
) -> FoldSet:
    """Build the ``FoldSet``: split i is fold ``i mod k`` of repeat ``i // k``.

    With ``groups`` (grouped schemes) a group found in both training and validation
    raises ``RuntimeError`` (group-leak assertion, ported from pengoo).
    """
    folds: list[Fold] = []
    for i, positions in enumerate(validation):
        is_val = np.zeros(spectra.n_samples, dtype=bool)
        is_val[positions] = True
        if groups is not None and np.intersect1d(groups[is_val], groups[~is_val]).size:
            raise RuntimeError(f"{scheme} fold {i}: a group is in training and validation")
        rows = spectra.row_index
        folds.append(Fold(i % k, i // k, rows[~is_val], rows[is_val]))
    return FoldSet(
        scheme,
        spectra.source_id,
        spectra.n_samples,
        tuple(folds),
        groups_respected=groups is not None or spectra.group_ids is None,
        seed=seed,
    )


class KFold(Block):
    """k-fold CV (METHODS.md#k-fold)."""

    block_id = "validate.kfold"
    version = "1.0.0"
    icon = "glyph-kfold"
    references = ("stone1974cv", "pedregosa2011sklearn")
    fitted = False
    inputs = (port("spectra", "Spectra"),)
    outputs = FOLDS_OUTPUT
    params_type = ShuffledFoldParams
    implementation = ("scikit-learn", "sklearn.model_selection.KFold")

    def apply(
        self,
        spectra: SpectralDataset,
        params: ShuffledFoldParams,
        rng: np.random.Generator | None = None,
    ) -> FoldSet:
        n = spectra.n_samples
        _check_k(params.k, n)

        # Step 1: Optionally shuffle the rows with the Generator, then cut them into k
        # near-equal folds (the first n mod k folds one row larger)
        if params.shuffle:
            drawn, seed = _seeds(params.seed, rng)
            splitter = SkKFold(n_splits=params.k, shuffle=True, random_state=drawn)
        else:
            seed, splitter = None, SkKFold(n_splits=params.k)
        return _fold_set(spectra, "kfold", _sk_validation(splitter, n), params.k, None, seed)


class VenetianBlinds(Block):
    """Venetian blinds CV (METHODS.md#venetian-blinds)."""

    block_id = "validate.venetian_blinds"
    version = "1.0.0"
    icon = "glyph-venetian-blinds"
    references = ("eigenvector_cv",)
    fitted = False
    inputs = (port("spectra", "Spectra"),)
    outputs = FOLDS_OUTPUT
    params_type = FoldParams

    def apply(self, spectra: SpectralDataset, params: FoldParams) -> FoldSet:
        n, k = spectra.n_samples, params.k
        _check_k(k, n)

        # Step 1: Row i (0-based, input order) goes to fold i mod k
        fold_of = np.arange(n) % k
        validation = (np.flatnonzero(fold_of == f) for f in range(k))
        return _fold_set(spectra, "venetian", validation, k, None, None)


class ContiguousBlocks(Block):
    """Contiguous-blocks CV (METHODS.md#contiguous-blocks)."""

    block_id = "validate.contiguous_blocks"
    version = "1.0.0"
    icon = "glyph-contiguous-blocks"
    references = ("eigenvector_cv",)
    fitted = False
    inputs = (port("spectra", "Spectra"),)
    outputs = FOLDS_OUTPUT
    params_type = FoldParams

    def apply(self, spectra: SpectralDataset, params: FoldParams) -> FoldSet:
        n, k = spectra.n_samples, params.k
        _check_k(k, n)

        # Step 1: Rows in input order are cut into k consecutive blocks (the first
        # n mod k blocks one row larger)
        validation = np.array_split(np.arange(n), k)
        return _fold_set(spectra, "contiguous", validation, k, None, None)


class LeaveOneOut(Block):
    """Leave-one-out CV; with groups leave-one-group-out (METHODS.md#loo)."""

    block_id = "validate.loo"
    version = "1.0.0"
    icon = "glyph-loo"
    references = ("stone1974cv", "pedregosa2011sklearn")
    fitted = False
    inputs = (port("spectra", "Spectra"),)
    outputs = FOLDS_OUTPUT
    implementation = (
        "scikit-learn",
        "sklearn.model_selection.LeaveOneOut, sklearn.model_selection.LeaveOneGroupOut",
    )

    def apply(self, spectra: SpectralDataset, params: NoParams) -> FoldSet:  # noqa: ARG002
        n = spectra.n_samples
        groups = None if spectra.group_ids is None else _groups(spectra)

        # Step 1: One fold per row, or with groups one fold per group (groups in
        # sorted label order)
        if groups is None:
            validation, k = _sk_validation(SkLeaveOneOut(), n), n
        else:
            validation, k = _sk_validation(LeaveOneGroupOut(), n, groups), int(groups.max()) + 1
        return _fold_set(spectra, "loo", validation, k, groups, None)


class RepeatedKFold(Block):
    """Repeated k-fold CV (METHODS.md#repeated-k-fold)."""

    block_id = "validate.repeated_kfold"
    version = "1.0.0"
    icon = "glyph-repeated-kfold"
    references = ("pedregosa2011sklearn",)
    fitted = False
    inputs = (port("spectra", "Spectra"),)
    outputs = FOLDS_OUTPUT
    params_type = RepeatedKFoldParams
    implementation = ("scikit-learn", "sklearn.model_selection.RepeatedKFold")

    def apply(
        self,
        spectra: SpectralDataset,
        params: RepeatedKFoldParams,
        rng: np.random.Generator | None = None,
    ) -> FoldSet:
        n = spectra.n_samples
        _check_k(params.k, n)

        # Step 1: k-fold on a new shuffle of the rows, repeated r times (each repeat a
        # full partition; scikit-learn yields repeat after repeat)
        drawn, seed = _seeds(params.seed, rng)
        splitter = SkRepeatedKFold(n_splits=params.k, n_repeats=params.repeats, random_state=drawn)
        validation = _sk_validation(splitter, n)
        return _fold_set(spectra, "repeated_kfold", validation, params.k, None, seed)


class GroupKFold(Block):
    """Group k-fold CV (METHODS.md#group-k-fold)."""

    block_id = "validate.group_kfold"
    version = "1.0.0"
    icon = "glyph-group-kfold"
    references = ("esbensen2010validation", "pedregosa2011sklearn")
    fitted = False
    inputs = (port("spectra", "Spectra", requires=("groups",)),)
    outputs = FOLDS_OUTPUT
    params_type = ShuffledFoldParams
    implementation = ("scikit-learn", "sklearn.model_selection.GroupKFold")

    def apply(
        self,
        spectra: SpectralDataset,
        params: ShuffledFoldParams,
        rng: np.random.Generator | None = None,
    ) -> FoldSet:
        groups = _groups(spectra)
        _check_k(params.k, int(groups.max()) + 1)

        # Step 1: Assign whole groups to k folds: shuffled groups cut into k near-equal
        # sets of groups, or unshuffled the largest group to the lightest fold first
        if params.shuffle:
            drawn, seed = _seeds(params.seed, rng)
            splitter = SkGroupKFold(n_splits=params.k, shuffle=True, random_state=drawn)
        else:
            seed, splitter = None, SkGroupKFold(n_splits=params.k)
        validation = _sk_validation(splitter, spectra.n_samples, groups)
        return _fold_set(spectra, "group_kfold", validation, params.k, groups, seed)

---
name: block-template
description: "VibeChem block template and comment style (docs/rules/CODING.md#block-template-and-comment-style): header docstring, typed Params, numbered '# Step N:' comments matching METHODS.md. Load before writing, changing or reviewing any block."
---

Read first: docs/rules/CODING.md#block-template-and-comment-style; docs/METHODS.md (the method's entry).

# Block template and comment style (docs/rules/CODING.md#block-template-and-comment-style)

Every block is one file. Header docstring, typed parameters, numbered `# Step N:` comments that match `docs/METHODS.md`, so a reviewer can check each line against the paper. When a block wraps an external library, the `# Step` comments describe what the library call does and the header names the library (the `Implementation:` line). Keep blocks as simple as the method allows (ponytail).

Comment rule (docs/rules/PRECEDENCE.md, D6): the header docstring and the numbered `# Step N:` comments are mandatory, even though ponytail limits comments. Beyond them, follow ponytail: no other line comments except a one-line "why" the code cannot show, and `shortcut: <limit>, <when to upgrade>` for a known limit. Every block has a **reference test against an independent value**; other tests only for non-trivial logic.

```python
# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/blocks/preprocess/snv.py
"""
Block:          Standard Normal Variate (SNV)
Class:          preprocess
Ports:          in  -> spectra : Spectra
                out -> spectra : Spectra
Reference:      Barnes, Dhanoa & Lister (1989), Appl. Spectrosc. 43(5), 772-777
METHODS:        docs/METHODS.md#snv
Implementation: own NumPy code (simpler than wrapping; see TECH_STACK.md §11)
Fitted:         No (row-wise transform; safe inside CV without refitting)
Reviewer:       Quan
"""
from dataclasses import dataclass

import numpy as np

from vibechem_core.block import Block, Param, port
from vibechem_core.data import SpectralDataset
from vibechem_core.errors import BlockInputError


@dataclass(frozen=True)
class SNVParams:
    ddof: int = Param(1, choices=(0, 1), tooltip_key="blocks.preprocess.snv.params.ddof.tip")


class SNV(Block):
    block_id = "preprocess.snv"
    version = "1.0.0"
    icon = "glyph-snv"
    references = ("barnes1989snv",)
    fitted = False
    inputs = (port("spectra", "Spectra"),)
    outputs = (port("spectra", "Spectra"),)
    params_type = SNVParams

    def apply(self, spectra: SpectralDataset, params: SNVParams) -> SpectralDataset:
        X = spectra.X

        # Step 1: Mean of each spectrum over all wavelengths (one value per row)
        row_mean = X.mean(axis=1, keepdims=True)

        # Step 2: Standard deviation of each spectrum
        row_std = X.std(axis=1, ddof=params.ddof, keepdims=True)

        # Step 3: Reject flat spectra (std = 0 would divide by zero)
        flat_rows = np.flatnonzero(row_std.ravel() == 0)
        if flat_rows.size > 0:
            raise BlockInputError(
                code="BLOCK_CONSTANT_SPECTRA",
                params={"rows": flat_rows.tolist()},
            )

        # Step 4: Centre and scale each spectrum individually
        X_snv = (X - row_mean) / row_std

        return spectra.with_X(X_snv, history=f"SNV(ddof={params.ddof})")
```
Other conventions (typing, docstrings, C++, TypeScript, SPDX headers): `docs/TECH_STACK.md` §4–6.

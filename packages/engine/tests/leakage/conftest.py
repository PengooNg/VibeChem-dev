# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/leakage/conftest.py
"""Blocks and the edge-list pipeline builder shared by the leakage suite (QA.md §3)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import pytest

from vibechem_core.block import Block, port
from vibechem_core.blocks.model.pls import PLS
from vibechem_core.blocks.preprocess.msc import MSC
from vibechem_core.blocks.preprocess.scaling import MeanCentre
from vibechem_core.blocks.preprocess.snv import SNV
from vibechem_core.blocks.split.random_split import RandomSplit
from vibechem_core.blocks.validate.folds import KFold
from vibechem_core.registry import Registry
from vibechem_engine.compiler import CompiledPipeline, compile_pipeline


class Source(Block):
    """A data node; the test supplies its output."""

    block_id = "test.source"
    version = "1.0.0"
    icon = "glyph-dummy"
    fitted = False
    inputs = ()
    outputs = (port("spectra", "Spectra"),)

    def apply(self, **kwargs: Any) -> Any:  # noqa: ARG002
        return None


class Predict(Block):
    block_id = "test.predict"
    version = "1.0.0"
    icon = "glyph-dummy"
    fitted = False
    inputs = (port("model", "Model"), port("spectra", "Spectra"))
    outputs = (port("predictions", "Table"),)

    def apply(self, **kwargs: Any) -> Any:  # noqa: ARG002
        return None


class CV(Block):
    block_id = "test.cv"
    version = "1.0.0"
    icon = "glyph-dummy"
    fitted = False
    inputs = (port("model", "Model", refit_per_fold=True), port("folds", "Folds"))
    outputs = (port("results", "Results"),)

    def apply(self, **kwargs: Any) -> Any:  # noqa: ARG002
        return None


REGISTRY = Registry()
for _block in (Source, Predict, CV, SNV, MSC, MeanCentre, PLS, RandomSplit, KFold):
    REGISTRY.register(_block)

BLOCKS = {
    "src": "test.source",
    "src2": "test.source",
    "pred": "test.predict",
    "cv": "test.cv",
    "snv": "preprocess.snv",
    "msc": "preprocess.msc",
    "centre": "preprocess.mean_centre",
    "pls": "model.pls",
    "split": "split.random",
    "split2": "split.random",
    "kfold": "validate.kfold",
    "sel": "test.select_top_k",  # registered by test_noise.py
}

type CompileEdges = Callable[..., CompiledPipeline]


def pipeline_of(
    edges: list[str], params: Mapping[str, Mapping[str, Any]] | None = None
) -> dict[str, Any]:
    """Edges as ``"a.port -> b.port"``; nodes are named after ``BLOCKS``."""
    pairs = [tuple(x.strip().split(".") for x in e.split("->")) for e in edges]
    names = list(dict.fromkeys(n for (a, _), (b, _) in pairs for n in (a, b)))
    return {
        "nodes": [
            {"node_id": n, "block_id": BLOCKS[n], "params": dict((params or {}).get(n, {}))}
            for n in names
        ],
        "edges": [
            {"edge_id": f"eg_{i}", "from_node": a, "from_port": ap, "to_node": b, "to_port": bp}
            for i, ((a, ap), (b, bp)) in enumerate(pairs)
        ],
    }


@pytest.fixture
def build_pipeline() -> Callable[..., dict[str, Any]]:
    return pipeline_of


@pytest.fixture
def registry() -> Registry:
    return REGISTRY


@pytest.fixture
def compile_edges() -> CompileEdges:
    def run(
        edges: list[str], params: Mapping[str, Mapping[str, Any]] | None = None
    ) -> CompiledPipeline:
        return compile_pipeline(pipeline_of(edges, params), REGISTRY)

    return run

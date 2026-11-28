# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/golden/test_golden_pipeline.py
"""Golden pipeline (QA.md §3, §5): one end-to-end run whose every node output is pinned.

Gasoline NIR (60 samples) -> SNV -> Savitzky-Golay (1st derivative) -> PLS with 6 LV,
cross-validated with seeded shuffled 5-fold; a seeded random split hangs off the data node
to pin the scikit-learn shuffle (R27). Each node's output is stored as a hash
(``check_golden``) and the final CV metrics with a tolerance. A change to any block shows
up as the first node whose hash differs. ``pytest --force-regen`` rewrites both golden
files; doing that in a PR is a red flag (QA.md §4).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml
from numpy.typing import NDArray
from pytest_regressions.data_regression import DataRegressionFixture

from vibechem import Pipeline, results_of
from vibechem_core.block import State
from vibechem_core.data import FoldSet, Results, SpectralDataset
from vibechem_core.testing import assert_close, check_golden, node_hash
from vibechem_engine.cli.data import dataset_from_file
from vibechem_engine.runners import PipelineRun

TESTDATA = Path(__file__).parents[4] / "testdata"
HASHES = TESTDATA / "expected" / "golden_pipeline_hashes.yml"
METRICS = TESTDATA / "expected" / "golden_pipeline_metrics.yml"
SEED = 3
METRICS_RTOL = (
    1e-9  # same machine class differs only by BLAS last bits; METHODS.md has no looser need
)
METRICS_ATOL = 1e-12


def _node(node_id: str, block_id: str, params: dict[str, Any]) -> dict[str, Any]:
    return {"node_id": node_id, "block_id": block_id, "block_version": "1.0.0", "params": params,
            "position": {"x": 0, "y": 0}, "label": None}  # fmt: skip


def _document(savgol_window: int = 15) -> dict[str, Any]:
    nodes = [
        _node("nd_src", "data.dataset", {"dataset_id": "gasoline"}),
        _node("nd_snv", "preprocess.snv", {}),
        _node("nd_sg", "preprocess.savgol", {"window": savgol_window, "polyorder": 2, "deriv": 1}),
        _node("nd_kf", "validate.kfold", {"k": 5, "seed": 7}),
        _node("nd_pls", "model.pls", {"n_components": 6}),
        _node("nd_cv", "validate.cv", {}),
        _node("nd_split", "split.random", {"seed": 11}),
    ]
    wires = [("nd_src", "spectra", "nd_snv", "spectra"), ("nd_snv", "spectra", "nd_sg", "spectra"),
             ("nd_sg", "spectra", "nd_kf", "spectra"), ("nd_sg", "spectra", "nd_pls", "spectra"),
             ("nd_pls", "model", "nd_cv", "model"), ("nd_kf", "folds", "nd_cv", "folds"),
             ("nd_src", "spectra", "nd_split", "spectra")]  # fmt: skip
    return {
        "format_version": 1, "pipeline_id": "ppl_golden", "name": "golden", "revision": 0,
        "nodes": nodes,
        "edges": [{"edge_id": f"eg_{i}", "from_node": a, "from_port": b, "to_node": c, "to_port": d}
                  for i, (a, b, c, d) in enumerate(wires)],
        "created_at": "2026-11-28T00:00:00Z", "updated_at": "2026-11-28T00:00:00Z",
    }  # fmt: skip


def _numbers(value: object) -> Iterator[NDArray[np.float64]]:
    """Every numeric array inside a node output, in a fixed order (text columns are skipped)."""
    if isinstance(value, SpectralDataset):
        yield np.asarray(value.X, dtype=np.float64).ravel()
    elif isinstance(value, FoldSet):
        for fold in value.folds:
            yield fold.train.astype(np.float64)
            yield fold.validation.astype(np.float64)
    elif isinstance(value, State):
        yield from _numbers(dict(value.arrays))
    elif isinstance(value, Results):
        yield np.array(list(value.metrics.values()), dtype=np.float64)
        yield from _numbers(value.predictions or {})
    elif isinstance(value, Mapping):
        for key in sorted(value):  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
            yield from _numbers(value[key])  # pyright: ignore[reportUnknownArgumentType]
    elif isinstance(value, np.ndarray) and np.issubdtype(value.dtype, np.number):  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        yield value.astype(np.float64).ravel()  # pyright: ignore[reportUnknownMemberType]


def _node_hashes(run: PipelineRun, pipeline: Pipeline) -> dict[str, str]:
    """``node_hash`` of every node's top-level outputs, in the pipeline's node order."""
    hashes: dict[str, str] = {}
    for node in pipeline.document["nodes"]:
        node_id = node["node_id"]
        parts = [
            arr
            for task_id, out in sorted(run.outputs.items())  # completion order varies
            if task_id.rsplit(":", 1)[0] == node_id  # skips the per-fold ``@`` tasks
            for name in sorted(out.values)
            for arr in _numbers(out.values[name])
        ]
        hashes[node_id] = node_hash(np.concatenate(parts) if parts else np.empty(0))
    return hashes


@pytest.fixture(scope="module")
def dataset() -> SpectralDataset:
    return dataset_from_file(TESTDATA / "datasets" / "gasoline_nir.csv", "gasoline")


def _run(
    dataset: SpectralDataset, savgol_window: int = 15
) -> tuple[dict[str, str], dict[str, float]]:
    pipeline = Pipeline(_document(savgol_window))
    run = pipeline.run({"gasoline": dataset}, seed=SEED, max_workers=2)
    assert run.status == "succeeded", dict(run.errors)
    return _node_hashes(run, pipeline), dict(results_of(run, pipeline)["nd_cv"].metrics)


@pytest.fixture(scope="module")
def golden_run(dataset: SpectralDataset) -> tuple[dict[str, str], dict[str, float]]:
    return _run(dataset)


def test_every_node_output_and_the_metrics_are_unchanged(
    golden_run: tuple[dict[str, str], dict[str, float]],
    data_regression: DataRegressionFixture,
    request: pytest.FixtureRequest,
) -> None:
    hashes, metrics = golden_run
    check_golden(data_regression, hashes, HASHES)
    regenerate = bool(request.config.getoption("force_regen"))
    if regenerate or not METRICS.exists():
        created = not METRICS.exists()
        text = yaml.safe_dump(metrics, sort_keys=False)
        METRICS.write_text(text, encoding="utf-8", newline="\n")
        if created and not regenerate:
            pytest.fail(f"created {METRICS.name}; run again")
    expected: dict[str, float] = yaml.safe_load(METRICS.read_text(encoding="utf-8"))
    assert list(metrics) == list(expected)
    assert_close(list(metrics.values()), list(expected.values()),
                 rtol=METRICS_RTOL, atol=METRICS_ATOL, name="golden CV metrics")  # fmt: skip


def test_a_deliberate_change_names_the_first_divergent_node(
    dataset: SpectralDataset, data_regression: DataRegressionFixture
) -> None:
    hashes, _ = _run(dataset, savgol_window=17)  # one parameter of the third node
    with pytest.raises(AssertionError, match=r"first node whose output changed: nd_sg "):
        check_golden(data_regression, hashes, HASHES)

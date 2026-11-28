# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/pipeline.py
"""The Python API of a pipeline: load a ``.vcp.json`` file, validate it, run it (T2.11).

``Pipeline`` is also exported as ``vibechem.Pipeline``. It ties the pieces together:
``formats.load_pipeline`` (file), ``compiler.compile_pipeline`` (graph + leakage issues),
``blocks`` parameter check, ``runners.run_pipeline`` (execution on a ``ProcessExecutor``).
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from vibechem_core.block import parse_params
from vibechem_core.blocks import default_registry
from vibechem_core.data import Results, SpectralDataset
from vibechem_core.errors import VibeChemError
from vibechem_core.registry import Registry
from vibechem_engine.compiler import compile_pipeline
from vibechem_engine.executor import Executor, ProcessExecutor
from vibechem_engine.formats import PipelineFile, load_pipeline
from vibechem_engine.graph import GraphIssue
from vibechem_engine.runners import PipelineRun, run_pipeline

__all__ = ["DATASET_BLOCK", "DataMismatch", "Pipeline", "PipelineInvalid", "results_of"]

DATASET_BLOCK = "data.dataset"
"""``block_id`` of the data source block (DATA_MODEL.md §2.3)."""


class PipelineInvalid(ValueError):
    """The pipeline has an error issue or names an unknown block; nothing ran."""


class DataMismatch(ValueError):
    """``run`` got data for a ``dataset_id`` no node uses, or none for one a node needs."""


class Pipeline:
    """A pipeline document (DATA_MODEL.md §2.6) with its block registry.

    Parameters
    ----------
    document : PipelineFile or mapping
        The pipeline; a mapping must have the shape of the file (``nodes``, ``edges``).
    registry : Registry, optional
        Blocks the nodes refer to; default: all built-in blocks.
    """

    def __init__(
        self, document: PipelineFile | Mapping[str, Any], registry: Registry | None = None
    ) -> None:
        doc = document.model_dump(mode="json") if isinstance(document, PipelineFile) else document
        self.document: Mapping[str, Any] = doc
        self.registry = registry if registry is not None else default_registry()

    @classmethod
    def load(cls, path: str | os.PathLike[str], registry: Registry | None = None) -> Pipeline:
        """Read a pipeline file; ``FormatError`` (``PIPELINE_FILE_INVALID``) if it is invalid."""
        return cls(load_pipeline(path), registry)

    @property
    def dataset_ids(self) -> tuple[str, ...]:
        """``dataset_id`` of every ``data.dataset`` node, sorted, without repeats."""
        return tuple(
            sorted({str(n.get("params", {}).get("dataset_id", "dataset")) for n in self._sources()})
        )

    def validate(self) -> list[GraphIssue]:
        """Every problem found without running: parameters, ports, cycles, leakage.

        Raises ``PipelineInvalid`` when a node names an unknown block and ``ValueError`` when
        the document is malformed (as ``compile_pipeline`` does).
        """
        issues: list[GraphIssue] = []
        for node in self.document["nodes"]:
            if node["block_id"] not in self.registry:
                raise PipelineInvalid(f"unknown block_id {node['block_id']!r}")
            params_type = self.registry.get(node["block_id"]).params_type
            try:
                parse_params(params_type, node.get("params", {}))
            except VibeChemError as error:
                issues.append(GraphIssue(error.code, node["node_id"], params=error.params))
        return issues + list(compile_pipeline(self.document, self.registry).issues)

    def run(
        self,
        data: Mapping[str, SpectralDataset] | None = None,
        *,
        seed: int = 0,
        max_workers: int | None = None,
        executor: Executor | None = None,
    ) -> PipelineRun:
        """Run the pipeline; ``data`` maps each ``dataset_id`` to its dataset.

        Raises ``DataMismatch`` for a ``dataset_id`` without data or data no node uses, and
        ``PipelineInvalid`` for a pipeline with error issues (``validate``); both are ``ValueError``. A failed node does not raise: see
        ``PipelineRun.status`` and ``PipelineRun.errors``. Without ``executor`` a process
        pool of ``max_workers`` (default: the CPU count) runs the tasks.
        """
        data = data or {}
        missing = sorted(set(self.dataset_ids) - set(data))
        unused = sorted(set(data) - set(self.dataset_ids))
        if missing or unused:
            raise DataMismatch(f"data missing for {missing}, not used by any node: {unused}")
        errors = [i for i in self.validate() if i.severity == "error"]
        if errors:
            codes = ", ".join(sorted({i.code for i in errors}))
            raise PipelineInvalid(f"pipeline is invalid: {codes}")
        compiled = compile_pipeline(self.document, self.registry)
        sources = {
            n["node_id"]: {"spectra": data[str(n.get("params", {}).get("dataset_id", "dataset"))]}
            for n in self._sources()
        }
        if executor is not None:
            return run_pipeline(
                compiled, self.document, self.registry, sources, executor, root_seed=seed
            )
        with tempfile.TemporaryDirectory(prefix="vibechem_") as spill:
            workers = max_workers or os.cpu_count() or 1
            with ProcessExecutor(workers, Path(spill)) as pool:
                return run_pipeline(
                    compiled, self.document, self.registry, sources, pool, root_seed=seed
                )

    def _sources(self) -> list[Mapping[str, Any]]:
        return [n for n in self.document["nodes"] if n["block_id"] == DATASET_BLOCK]


def results_of(run: PipelineRun, pipeline: Pipeline) -> dict[str, Results]:
    """``Results`` output of each node of ``pipeline`` that has one, by ``node_id``."""
    node_ids = {n["node_id"] for n in pipeline.document["nodes"]}
    found: dict[str, Results] = {}
    for task_id, output in run.outputs.items():
        node_id = task_id.rsplit(":", 1)[0]
        if node_id not in node_ids:
            continue
        for value in output.values.values():
            if isinstance(value, Results):
                found[node_id] = value
    return found

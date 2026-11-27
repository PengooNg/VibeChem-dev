# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/runners/__init__.py
"""Runners: execute a compiled pipeline on the scheduler (ARCHITECTURE.md §2.2 steps 3-5).

:func:`run_pipeline` runs the tasks of a :class:`~vibechem_engine.compiler.CompiledPipeline`
in stages, because a validation node's fold tasks exist only once its ``Folds`` are known:

1. every top-level task that does not need a validation node (source nodes take their
   outputs from ``sources``);
2. per validation node, :meth:`FoldPlan.expand` for each fold of its ``Folds``; ``select``
   tasks take the fold's rows by ``row_index`` (:func:`~vibechem_engine.compiler.fold_rows`,
   R40);
3. each validation node in this process, with the keyword ``fold_runs``: per fold, the
   state feeding its ``refit_per_fold`` port and that model's first input on the fold's
   validation rows (METHODS.md#cv);
4. the tasks downstream of validation nodes.

A task runs in a worker as :func:`execute_task`; it returns a :class:`TaskOutput` with its
outputs by port id and the warnings the block raised (ADR-010 node log). Every stage gets
its own root seed from ``root_seed``. A stage with a failure ends the run.
"""

from __future__ import annotations

import inspect
import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from vibechem_core.block import Block, State, parse_params
from vibechem_core.blocks.validate.cv import FoldRun
from vibechem_core.data import Fold, FoldSet, SpectralDataset
from vibechem_core.errors import VibeChemError
from vibechem_core.registry import Registry
from vibechem_engine.compiler import (
    STATE,
    CompiledPipeline,
    FoldTasks,
    Task,
    TaskInput,
    fold_rows,
)
from vibechem_engine.executor import Executor, task_seeds
from vibechem_engine.scheduler import Job, RunStatus, run_jobs

__all__ = ["PipelineRun", "TaskOutput", "execute_task", "run_pipeline"]

_STATE_TYPES = frozenset({"Model", "Transform"})


@dataclass(frozen=True, slots=True)
class TaskOutput:
    """Outputs of one task by output name, and the warnings its block raised."""

    values: Mapping[str, object]
    warnings: tuple[Warning, ...] = ()


@dataclass(frozen=True, slots=True)
class _Spec:
    """What a worker needs to run one task; ``inputs`` maps a port to a dependency
    position and output name, ``values`` holds inputs computed in an earlier stage."""

    block: type[Block] | None  # None for select tasks, which run no block
    kind: str
    params: Mapping[str, Any]
    inputs: tuple[tuple[str, int, str], ...]
    values: Mapping[str, object]
    fold: tuple[int, int] | None
    part: str | None


@dataclass(frozen=True, slots=True)
class PipelineRun:
    """Result of :func:`run_pipeline`: task outputs by task id, errors by task id."""

    status: RunStatus
    outputs: Mapping[str, TaskOutput]
    errors: Mapping[str, BaseException]

    def output(self, node_id: str, port_id: str) -> object:
        """Top-level output ``port_id`` of node ``node_id``."""
        for task_id in (f"{node_id}:run", f"{node_id}:apply"):
            values = self.outputs.get(task_id)
            if values is not None and port_id in values.values:
                return values.values[port_id]
        return self.outputs[f"{node_id}:fit"].values[STATE]


def execute_task(seed: int, spec: _Spec, *deps: TaskOutput) -> TaskOutput:
    """Run one task (module-level, so loky workers can import it)."""
    kwargs: dict[str, Any] = dict(spec.values)
    for port_id, position, output in spec.inputs:
        kwargs[port_id] = deps[position].values[output]
    if spec.kind == "select":
        assert spec.fold is not None
        assert spec.part in ("train", "validation")
        folds: FoldSet = kwargs["folds"]
        fold = next(f for f in folds.folds if (f.fold, f.repeat) == spec.fold)
        return TaskOutput({"rows": fold_rows(kwargs["data"], fold, spec.part)})  # pyright: ignore[reportArgumentType]

    assert spec.block is not None
    block = spec.block()
    params: object = parse_params(block.params_type, spec.params)  # pyright: ignore[reportUnknownVariableType]
    method = block.fit if spec.kind == "fit" else block.apply
    if "rng" in inspect.signature(method).parameters:
        kwargs["rng"] = np.random.default_rng(seed)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result: Any = method(**kwargs, params=params)
    raised = tuple(w.message for w in caught if isinstance(w.message, Warning))
    if spec.kind == "fit":
        return TaskOutput({STATE: result}, raised)
    meta = spec.block.metadata()
    data_ports = [
        p.port_id for p in meta.outputs if not (meta.fitted and p.port_type in _STATE_TYPES)
    ]
    if len(data_ports) > 1:  # a block with several data outputs returns a dict by port_id
        values: dict[str, object] = dict(result)
    else:
        values = {data_ports[0]: result} if data_ports else {}
    return TaskOutput(values, raised)


def run_pipeline(
    compiled: CompiledPipeline,
    pipeline: Mapping[str, Any],
    registry: Registry,
    sources: Mapping[str, Mapping[str, object]],
    executor: Executor,
    *,
    root_seed: int,
) -> PipelineRun:
    """Run ``compiled`` (from ``pipeline``); ``sources`` gives the outputs of data nodes.

    Raises ``ValueError`` when ``compiled`` has error issues (it has no tasks then).
    """
    if any(i.severity == "error" for i in compiled.issues):
        raise ValueError(f"pipeline has errors: {sorted({i.code for i in compiled.issues})}")
    nodes = {n["node_id"]: n for n in pipeline["nodes"]}
    done: dict[str, TaskOutput] = {
        f"{node_id}:run": TaskOutput(dict(values)) for node_id, values in sources.items()
    }
    errors: dict[str, BaseException] = {}
    seeds = task_seeds(root_seed, 4)  # one root per stage

    def spec(task: Task, stage: dict[str, Task]) -> tuple[_Spec, tuple[str, ...]]:
        deps: list[str] = []
        inputs: list[tuple[str, int, str]] = []
        values: dict[str, object] = {}
        for i in task.inputs:
            if i.rule is not None:
                # shortcut: implicit port views (DATA_MODEL §4.4) are not executed yet; T2.11 adds them.
                raise NotImplementedError(f"implicit conversion {i.rule} on {task.task_id}")
            if i.task_id in stage:
                if i.task_id not in deps:
                    deps.append(i.task_id)
                inputs.append((i.port_id, deps.index(i.task_id), i.output))
            else:
                values[i.port_id] = done[i.task_id].values[i.output]
        node = nodes[task.node_id]
        block = None if task.kind == "select" else registry.get(node["block_id"])
        return (
            _Spec(
                block,
                task.kind,
                node.get("params", {}),
                tuple(inputs),
                values,
                task.fold,
                task.part,
            ),
            tuple(deps),
        )

    def run(tasks: list[Task], seed: int) -> bool:
        if not tasks:
            return True
        stage = {t.task_id: t for t in tasks}
        jobs: list[Job] = []
        for t in tasks:
            s, deps = spec(t, stage)
            jobs.append(Job(t.task_id, t.node_id, execute_task, (s,), deps))
        result = run_jobs(jobs, executor, root_seed=seed)
        done.update({k: v for k, v in result.results.items() if isinstance(v, TaskOutput)})
        errors.update(result.errors)
        return result.status == "succeeded"

    # Stage 1: top-level tasks that do not need a validation node
    held = {f"{node_id}:run" for node_id in compiled.fold_plans}
    for task in compiled.tasks:
        if any(i.task_id in held for i in task.inputs):
            held.add(task.task_id)
    first = [t for t in compiled.tasks if t.task_id not in held and t.task_id not in done]
    if not run(first, seeds[0]):
        return PipelineRun("failed", done, errors)

    # Stage 2: fold tasks of every validation node
    expanded: dict[str, list[tuple[Fold, FoldTasks]]] = {}
    fold_tasks: list[Task] = []
    for node_id, plan in compiled.fold_plans.items():
        folds: FoldSet = done[plan.folds.task_id].values[plan.folds.output]  # pyright: ignore[reportAssignmentType]
        expanded[node_id] = []
        for fold in folds.folds:
            ft = plan.expand(fold.fold, fold.repeat)
            expanded[node_id].append((fold, ft))
            fold_tasks += ft.tasks
    if not run(fold_tasks, seeds[1]):
        return PipelineRun("failed", done, errors)

    # Stage 3: validation nodes, here, with their fold runs
    for node_id in compiled.fold_plans:
        task = next(t for t in compiled.tasks if t.task_id == f"{node_id}:run")
        s, _ = spec(task, {})
        fold_runs = [_fold_run(fold, ft, done, registry, nodes) for fold, ft in expanded[node_id]]
        try:
            out = execute_task(seeds[2], _with(s, fold_runs=fold_runs))
        except VibeChemError as exc:
            errors[task.task_id] = exc
            return PipelineRun("failed", done, errors)
        done[task.task_id] = out

    # Stage 4: what depends on validation nodes
    rest = [t for t in compiled.tasks if t.task_id in held and t.task_id not in done]
    if not run(rest, seeds[3]):
        return PipelineRun("failed", done, errors)
    return PipelineRun("succeeded", done, errors)


def _with(spec: _Spec, **values: object) -> _Spec:
    return _Spec(
        spec.block,
        spec.kind,
        spec.params,
        spec.inputs,
        {**spec.values, **values},
        spec.fold,
        spec.part,
    )


def _fold_run(
    fold: Fold,
    ft: FoldTasks,
    done: Mapping[str, TaskOutput],
    registry: Registry,
    nodes: Mapping[str, Mapping[str, Any]],
) -> FoldRun:
    """The fold's state and the refit source's first input on the validation rows."""
    state: State = done[ft.state.task_id].values[ft.state.output]  # pyright: ignore[reportAssignmentType]
    validation_task = next(t for t in ft.tasks if t.task_id == ft.validation)
    first = registry.meta(nodes[validation_task.node_id]["block_id"]).inputs[0].port_id
    wired: TaskInput = next(i for i in validation_task.inputs if i.port_id == first)
    spectra: SpectralDataset = done[wired.task_id].values[wired.output]  # pyright: ignore[reportAssignmentType]
    return FoldRun(fold, state, spectra)

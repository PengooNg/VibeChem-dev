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

A ``validate.grid_search`` node (T2.10c) is first expanded into one ``validate.cv``
branch per candidate chain (:func:`~vibechem_engine.runners.search.expand_search`) and
the expanded pipeline is compiled again; in stage 3 the search node gets ``candidates``
(each chain with its branch's ``Results``) instead of ``fold_runs``, and the warnings of
its branches. An error in a branch is also reported on the search node. A stage that
holds branch tasks runs on the search's workers as its core budget (the smallest, with
several searches; METHODS.md N31, decision by Quan: option A).

A ``validate.nested_cv`` node (T2.10d) is expanded the same way, one branch per
candidate on the outer folds. After stage 1, a sub-run of
:func:`~vibechem_engine.runners.nested.inner_pipeline` on each outer fold's training rows
tunes the chain and LV count (an inner grid search on the ``inner_folds``); stage 2
expands, per outer fold, only the chosen branch, for that fold; stage 3 gives the node
``fold_runs`` and ``choices``. Its branches' other tasks never run.

A task runs in a worker as :func:`execute_task`; it returns a :class:`TaskOutput` with its
outputs by port id and the warnings the block raised (ADR-010 node log). Every stage gets
its own root seed from ``root_seed``. A stage with a failure ends the run.
"""

from __future__ import annotations

import inspect
import logging
import os
import warnings
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, cast

import numpy as np

from vibechem_core.block import Block, State, parse_params
from vibechem_core.blocks.validate.cv import FoldRun
from vibechem_core.blocks.validate.nested_cv import InnerChoice
from vibechem_core.data import Fold, FoldSet, Results, SpectralDataset
from vibechem_core.errors import ParamError
from vibechem_core.registry import Registry
from vibechem_engine.compiler import (
    STATE,
    CompiledPipeline,
    FoldTasks,
    Task,
    TaskInput,
    compile_pipeline,
    fold_rows,
)
from vibechem_engine.executor import Executor, task_seeds
from vibechem_engine.runners.nested import (
    NESTED_CV,
    check_nested,
    inner_choice,
    inner_pipeline,
    inner_search_id,
)
from vibechem_engine.runners.search import GRID_SEARCH, Search, expand_search
from vibechem_engine.scheduler import Job, RunStatus, run_jobs

__all__ = ["PipelineRun", "TaskOutput", "execute_task", "run_pipeline"]

_STATE_TYPES = frozenset({"Model", "Transform"})
_log = logging.getLogger(__name__)


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
        """Top-level data output ``port_id`` of node ``node_id``; ``KeyError`` if absent."""
        for task_id in (f"{node_id}:run", f"{node_id}:apply"):
            values = self.outputs.get(task_id)
            if values is not None and port_id in values.values:
                return values.values[port_id]
        raise KeyError(f"{node_id}.{port_id}")

    def state(self, node_id: str) -> State:
        """State (``Model``/``Transform`` output) of fitted node ``node_id``."""
        return cast(State, self.outputs[f"{node_id}:fit"].values[STATE])


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

    Raises ``ValueError`` when ``compiled`` (or the pipeline with its grid-search
    candidates) has error issues (it has no tasks then).
    """
    if any(i.severity == "error" for i in compiled.issues):
        raise ValueError(f"pipeline has errors: {sorted({i.code for i in compiled.issues})}")
    searches: dict[str, Search] = {}
    nested: list[str] = []
    for node in [n for n in pipeline["nodes"] if n["block_id"] in (GRID_SEARCH, NESTED_CV)]:
        search_id = node["node_id"]
        try:
            if node["block_id"] == NESTED_CV:
                check_nested(node.get("params", {}), registry)
                nested.append(search_id)
            pipeline, searches[search_id] = expand_search(
                pipeline,
                search_id,
                registry,
                max_workers=executor.max_workers,
                cpu_count=os.cpu_count() or 1,
            )
        except ParamError as exc:  # a node error of the search (bad params, too large)
            return PipelineRun("failed", {}, {f"{search_id}:run": exc})
    if searches:
        compiled = compile_pipeline(pipeline, registry)
        if any(i.severity == "error" for i in compiled.issues):
            raise ValueError(f"candidates have errors: {sorted({i.code for i in compiled.issues})}")
    nodes = {n["node_id"]: n for n in pipeline["nodes"]}
    done: dict[str, TaskOutput] = {
        f"{node_id}:run": TaskOutput(dict(values)) for node_id, values in sources.items()
    }
    errors: dict[str, BaseException] = {}
    seeds = task_seeds(root_seed, 5)  # one root per stage, the last for the inner sub-runs
    # a nested node's branches run only through the folds stage 2 expands for it
    skip = {
        t.task_id
        for t in compiled.tasks
        if any(_in_branch(t.task_id, _ids(searches[n])) for n in nested)
    }

    def failed(status: RunStatus) -> PipelineRun:
        for search_id, search in searches.items():  # a branch error is the search's too
            ids = [cv for _, cv in search.branches]  # generated node ids: <cv> and <cv>.<part>
            branch = next((e for t, e in errors.items() if _in_branch(t, ids)), None)
            if branch is not None:
                errors.setdefault(f"{search_id}:run", branch)
        return PipelineRun(status, done, errors)

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

    def run(tasks: list[Task], seed: int) -> RunStatus:
        if not tasks:
            return "succeeded"
        stage = {t.task_id: t for t in tasks}
        jobs: list[Job] = []
        for t in tasks:
            s, deps = spec(t, stage)
            jobs.append(Job(t.task_id, t.node_id, execute_task, (s,), deps))
        # option A: the search's workers budget the whole stage, other nodes included
        budgets = [
            search.workers
            for search in searches.values()
            if any(_in_branch(t, [cv for _, cv in search.branches]) for t in stage)
        ]
        result = run_jobs(jobs, executor, root_seed=seed, cores=min(budgets, default=None))
        done.update({k: cast(TaskOutput, v) for k, v in result.results.items()})
        errors.update(result.errors)
        return result.status

    # Stage 1: top-level tasks that do not need a validation node
    held = {f"{node_id}:run" for node_id in compiled.fold_plans}
    for task in compiled.tasks:
        if any(i.task_id in held for i in task.inputs):
            held.add(task.task_id)
    first = [t for t in compiled.tasks if t.task_id not in held | skip and t.task_id not in done]
    if (status := run(first, seeds[0])) != "succeeded":
        return failed(status)

    # Stage 1b: the inner search of every nested node on each outer training set
    choices: dict[str, list[InnerChoice]] = {}
    inner_warnings: dict[str, list[Warning]] = {}
    for node_id, seed in zip(nested, task_seeds(seeds[4], len(nested)), strict=True):
        try:
            choices[node_id], inner_warnings[node_id] = _inner_runs(
                node_id, compiled, pipeline, registry, done, executor, seed
            )
        except Exception as exc:  # noqa: BLE001  (a node error of the nested node)
            _log.exception("inner search of nested node %s failed", node_id)
            errors[f"{node_id}:run"] = exc
            return failed("failed")

    # Stage 2: fold tasks of every validation node (a search's work is in its branches)
    expanded: dict[str, list[tuple[Fold, FoldTasks]]] = {}
    fold_tasks: list[Task] = []
    for node_id, plan in compiled.fold_plans.items():
        if node_id in searches or f"{node_id}:run" in skip:
            continue
        folds: FoldSet = done[plan.folds.task_id].values[plan.folds.output]  # pyright: ignore[reportAssignmentType]
        expanded[node_id] = []
        for fold in folds.folds:
            ft = plan.expand(fold.fold, fold.repeat)
            expanded[node_id].append((fold, ft))
            fold_tasks += ft.tasks
    for node_id in nested:  # per outer fold only the branch its inner search chose
        plan = compiled.fold_plans[node_id]
        folds = done[plan.folds.task_id].values[plan.folds.output]  # pyright: ignore[reportAssignmentType]
        expanded[node_id] = []
        for fold, choice in zip(folds.folds, choices[node_id], strict=True):
            branch = searches[node_id].branches[choice.candidate][1]
            ft = compiled.fold_plans[branch].expand(fold.fold, fold.repeat)
            expanded[node_id].append((fold, ft))
            fold_tasks += ft.tasks
    if (status := run(fold_tasks, seeds[1])) != "succeeded":
        return failed(status)

    # Stage 3: validation nodes, here, with their fold runs; searches after their branches
    validation = [n for n in compiled.fold_plans if n not in searches and f"{n}:run" not in skip]
    for node_id in validation + list(searches):
        task = next(t for t in compiled.tasks if t.task_id == f"{node_id}:run")
        try:
            s, _ = spec(task, {})
            if node_id in nested:
                runs = [
                    _fold_run(fold, ft, done, registry, nodes) for fold, ft in expanded[node_id]
                ]
                values = {**s.values, "fold_runs": runs, "choices": choices[node_id]}
                out = execute_task(seeds[2], replace(s, values=values))
                search = searches[node_id]
                found = (*_first(search), *inner_warnings[node_id], *out.warnings)
                unique = tuple({str(w): w for w in found}.values())
                done[task.task_id] = TaskOutput(out.values, unique)
                continue
            if node_id in searches:
                done[task.task_id] = _search_output(seeds[2], s, searches[node_id], done)
                continue
            runs = [_fold_run(fold, ft, done, registry, nodes) for fold, ft in expanded[node_id]]
            done[task.task_id] = execute_task(
                seeds[2], replace(s, values={**s.values, "fold_runs": runs})
            )
        except Exception as exc:  # noqa: BLE001  (a node error, as the scheduler records worker failures)
            _log.exception("validation node %s failed", node_id)
            errors[task.task_id] = exc
            return failed("failed")

    # Stage 4: what depends on validation nodes
    rest = [t for t in compiled.tasks if t.task_id in held - skip and t.task_id not in done]
    if (status := run(rest, seeds[3])) != "succeeded":
        return failed(status)
    return PipelineRun(status, done, errors)


def _ids(search: Search) -> list[str]:
    return [cv for _, cv in search.branches]


def _first(search: Search) -> tuple[Warning, ...]:
    return () if search.warning is None else (search.warning,)


def _inner_runs(
    node_id: str,
    compiled: CompiledPipeline,
    pipeline: Mapping[str, Any],
    registry: Registry,
    done: Mapping[str, TaskOutput],
    executor: Executor,
    seed: int,
) -> tuple[list[InnerChoice], list[Warning]]:
    """Per outer fold: the inner search's choice, from a sub-run on the fold's training
    rows of the fold source stream (METHODS.md#nested-cv steps 1-2); and the inner
    searches' warnings. Raises the first error of a failed sub-run."""
    plan = compiled.fold_plans[node_id]
    source = (plan.source.task_id.split(":", 1)[0], plan.source.output)
    data: SpectralDataset = done[plan.source.task_id].values[plan.source.output]  # pyright: ignore[reportAssignmentType]
    folds: FoldSet = done[plan.folds.task_id].values[plan.folds.output]  # pyright: ignore[reportAssignmentType]
    doc = inner_pipeline(pipeline, node_id, source, registry)
    inner = compile_pipeline(doc, registry)
    # upstream outputs are reused; the refit subgraph is re-fitted on the inner rows
    ids = [n["node_id"] for n in doc["nodes"]]
    reused = {n: done[f"{n}:run"].values for n in ids if f"{n}:run" in done and n not in plan.nodes}
    found: list[Warning] = []
    picked: list[InnerChoice] = []
    for fold, fold_seed in zip(folds.folds, task_seeds(seed, len(folds.folds)), strict=True):
        rows = fold_rows(data, fold, "train")
        sources = {**reused, source[0]: {**reused[source[0]], source[1]: rows}}
        sub = run_pipeline(inner, doc, registry, sources, executor, root_seed=fold_seed)
        if sub.status != "succeeded":
            raise next(iter(sub.errors.values()), RuntimeError(f"inner run {sub.status}"))
        out = sub.outputs[f"{inner_search_id(node_id)}:run"]
        picked.append(inner_choice(cast(Results, out.values["results"])))
        found += out.warnings
    return picked, found


def _in_branch(task_id: str, branches: list[str]) -> bool:
    node = task_id.split(":", 1)[0]
    return any(node == cv or node.startswith(f"{cv}.") for cv in branches)


def _search_output(
    seed: int, spec: _Spec, search: Search, done: Mapping[str, TaskOutput]
) -> TaskOutput:
    """Run a search node on its branches' results; its warnings (serial limit first)
    plus theirs, once each."""
    outs = [done[f"{cv}:run"] for _, cv in search.branches]
    results = [cast(Results, o.values["results"]) for o in outs]
    candidates = [(chain, r) for (chain, _), r in zip(search.branches, results, strict=True)]
    out = execute_task(seed, replace(spec, values={**spec.values, "candidates": candidates}))
    first = () if search.warning is None else (search.warning,)
    unique = {str(w): w for w in (*first, *(w for o in (out, *outs) for w in o.warnings))}
    return TaskOutput(out.values, tuple(unique.values()))


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

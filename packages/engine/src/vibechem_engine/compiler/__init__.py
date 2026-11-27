# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/compiler/__init__.py
"""Graph compiler: user graph -> task graph (ARCHITECTURE.md §2.2 step 3, §3.2).

:func:`compile_pipeline` turns a pipeline document (DATA_MODEL.md §2.6) into
:class:`Task` items. It never runs a block.

- A stateless block becomes one ``run`` task. A fitted block becomes a ``fit`` task and
  an ``apply`` task that receives the fit task's state as input ``state``. The fit task
  has one output, ``state``; it is also what the block's ``Model``/``Transform`` output
  ports carry. Every other output port comes from the apply task.
- An implicit conversion of §4.4 is recorded on the task input (``rule``).
- Validation (DATA_MODEL.md §4.6, §4.7.2 decided: option 1): a node with a connected
  ``refit_per_fold`` input gets a :class:`FoldPlan`. The fold source is the ``Spectra``
  stream feeding the node that produced its ``folds`` input; the refit subgraph is every
  node downstream of that stream that feeds the ``refit_per_fold`` port. The number of
  folds is only known at run time, so the runner calls :meth:`FoldPlan.expand` per
  fold: two ``select`` tasks take the fold's ``train`` and ``validation`` rows by
  ``row_index`` (:func:`fold_rows`), each subgraph node is fitted on the ``train``
  stream only and applied (or run) on both streams. Inputs from outside the subgraph
  stay wired to the full-row tasks; rejecting the leaky ones is the leakage rules' job
  (T2.05). A ``refit_per_fold`` source that is not downstream of the fold source is
  ``PIPELINE_FOLDS_SOURCE_MISMATCH``.
- Outside a fold every task sees all rows of its inputs, so the validation node's own
  ``run`` task gets the model refitted on all training rows (§4.6).
"""

from __future__ import annotations

import graphlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from vibechem_core.block import BlockMeta
from vibechem_core.data import Fold, SpectralDataset
from vibechem_core.registry import Registry
from vibechem_engine.graph import GraphIssue, validate_graph
from vibechem_engine.ports import RuleName, edge_rule

__all__ = [
    "PIPELINE_FOLDS_SOURCE_MISMATCH",
    "STATE",
    "CompiledPipeline",
    "FoldPlan",
    "FoldTasks",
    "Task",
    "TaskInput",
    "compile_pipeline",
    "fold_rows",
]

PIPELINE_FOLDS_SOURCE_MISMATCH = "PIPELINE_FOLDS_SOURCE_MISMATCH"
STATE = "state"
ROWS = "rows"  # the one output of a select task

type TaskKind = Literal["run", "fit", "apply", "select"]
type Part = Literal["train", "validation"]
type Edge = Mapping[str, Any]
type Producer = Callable[[str, str], tuple[str, str]]

_PARTS: tuple[Part, Part] = ("train", "validation")
_STATE_TYPES = frozenset({"Model", "Transform"})


@dataclass(frozen=True, slots=True)
class TaskInput:
    """Input ``port_id`` of a task is output ``output`` of task ``task_id``."""

    port_id: str
    task_id: str
    output: str
    rule: RuleName | None = None


@dataclass(frozen=True, slots=True)
class Task:
    """One unit of work. ``fold``/``part`` are set only inside a fold expansion."""

    task_id: str
    node_id: str
    kind: TaskKind
    inputs: tuple[TaskInput, ...]
    fold: tuple[int, int] | None = None  # (fold, repeat)
    part: Part | None = None


@dataclass(frozen=True, slots=True)
class _Graph:
    metas: Mapping[str, BlockMeta]
    edges: tuple[Edge, ...]
    order: tuple[str, ...]  # topological

    def port_type(self, node_id: str, port_id: str, direction: Literal["inputs", "outputs"]) -> str:
        return next(
            p.port_type for p in getattr(self.metas[node_id], direction) if p.port_id == port_id
        )

    def into(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e["to_node"] == node_id]

    def wire(self, edge: Edge, producer: Producer, port_id: str | None = None) -> TaskInput:
        src, port = edge["from_node"], edge["from_port"]
        to_type = self.port_type(edge["to_node"], edge["to_port"], "inputs")
        rule = edge_rule(self.port_type(src, port, "outputs"), to_type)
        return TaskInput(port_id or edge["to_port"], *producer(src, port), rule)

    def node_tasks(
        self,
        node_id: str,
        inputs: Callable[[Part | None], tuple[TaskInput, ...]],
        task_id: Callable[[TaskKind, Part | None], str],
        parts: Sequence[Part | None],
        fold: tuple[int, int] | None,
    ) -> list[Task]:
        if not self.metas[node_id].fitted:
            return [Task(task_id("run", p), node_id, "run", inputs(p), fold, p) for p in parts]
        fit_part: Part | None = None if fold is None else "train"
        fit = Task(task_id("fit", None), node_id, "fit", inputs(fit_part), fold, fit_part)
        state = TaskInput(STATE, fit.task_id, STATE)
        return [fit] + [
            Task(task_id("apply", p), node_id, "apply", (*inputs(p), state), fold, p) for p in parts
        ]

    def top(self, node_id: str, port_id: str) -> tuple[str, str]:
        """Producer outside any fold: task id and output of ``node_id.port_id``."""
        meta = self.metas[node_id]
        if not meta.fitted:
            return f"{node_id}:run", port_id
        if self.port_type(node_id, port_id, "outputs") in _STATE_TYPES:
            return f"{node_id}:fit", STATE
        return f"{node_id}:apply", port_id


@dataclass(frozen=True, slots=True)
class FoldTasks:
    """Tasks of one fold; ``state`` feeds the ``refit_per_fold`` port, ``validation``
    is the task that applies the refit source to the fold's validation rows."""

    tasks: tuple[Task, ...]
    state: TaskInput
    validation: str


@dataclass(frozen=True, slots=True)
class FoldPlan:
    """Per-fold expansion hook of one validation node (see the module docstring)."""

    node_id: str
    port_id: str
    source: TaskInput  # the Spectra stream the folds index, as select input "data"
    folds: TaskInput  # the validation node's folds, as select input "folds"
    nodes: tuple[str, ...]  # refit subgraph, topological order
    refit_edge: Edge
    _graph: _Graph = field(repr=False)
    _source_key: tuple[str, str] = field(repr=False)

    def expand(self, fold: int, repeat: int) -> FoldTasks:
        """The tasks of fold ``fold`` of repeat ``repeat`` (task ids carry both)."""
        g, inside, at = self._graph, set(self.nodes), (fold, repeat)
        tag = f"@{self.node_id}/f{fold}r{repeat}"

        def task_id(node_id: str, kind: TaskKind, part: Part | None) -> str:
            return f"{node_id}:{kind}{tag}" + ("" if part is None else f"/{part}")

        def producer(part: Part) -> Producer:
            def produce(src: str, port: str) -> tuple[str, str]:
                if (src, port) == self._source_key:
                    return task_id(src, "select", part), ROWS
                if src not in inside:
                    return g.top(src, port)
                if g.metas[src].fitted and g.port_type(src, port, "outputs") in _STATE_TYPES:
                    return task_id(src, "fit", None), STATE
                return task_id(src, "apply" if g.metas[src].fitted else "run", part), port

            return produce

        src_node = self._source_key[0]
        tasks = [
            Task(
                task_id(src_node, "select", p), src_node, "select", (self.source, self.folds), at, p
            )
            for p in _PARTS
        ]
        for node_id in self.nodes:
            edges = g.into(node_id)

            def inputs(part: Part | None, edges: list[Edge] = edges) -> tuple[TaskInput, ...]:
                assert part is not None  # every fold task sees one part
                return tuple(g.wire(e, producer(part)) for e in edges)

            tasks += g.node_tasks(
                node_id, inputs, lambda k, p, n=node_id: task_id(n, k, p), _PARTS, at
            )
        refit = self.refit_edge
        state = g.wire(refit, producer("train"))
        src = refit["from_node"]
        validation = task_id(src, "apply" if g.metas[src].fitted else "run", "validation")
        return FoldTasks(tuple(tasks), state, validation)


@dataclass(frozen=True, slots=True)
class CompiledPipeline:
    """Tasks in topological order, fold plans by validation ``node_id``, and issues.

    With an ``error`` issue there are no tasks and no plans.
    """

    tasks: tuple[Task, ...]
    fold_plans: Mapping[str, FoldPlan]
    issues: tuple[GraphIssue, ...]


def fold_rows(data: SpectralDataset, fold: Fold, part: Part) -> SpectralDataset:
    """What a ``select`` task does: the fold's ``part`` rows, by ``row_index`` (R40)."""
    return data.rows(fold.train if part == "train" else fold.validation)


def compile_pipeline(pipeline: Mapping[str, Any], registry: Registry) -> CompiledPipeline:
    """Validate ``pipeline`` (``validate_graph`` + the fold-source rule) and compile it.

    Raises ``ValueError`` for a malformed pipeline, as ``validate_graph`` does.
    """
    issues = validate_graph(pipeline, registry)
    if any(i.severity == "error" for i in issues):
        return CompiledPipeline((), {}, tuple(issues))
    metas = {n["node_id"]: registry.meta(n["block_id"]) for n in pipeline["nodes"]}
    edges = tuple(pipeline["edges"])
    predecessors: dict[str, set[str]] = {node_id: set() for node_id in metas}
    for e in edges:
        predecessors[e["to_node"]].add(e["from_node"])
    g = _Graph(metas, edges, tuple(graphlib.TopologicalSorter(predecessors).static_order()))

    tasks: list[Task] = []
    for node_id in g.order:
        wired = tuple(g.wire(e, g.top) for e in g.into(node_id))
        tasks += g.node_tasks(
            node_id, lambda _p, w=wired: w, lambda k, _p, n=node_id: f"{n}:{k}", (None,), None
        )

    plans: dict[str, FoldPlan] = {}
    for node_id, meta in metas.items():
        for port in meta.inputs:
            refit = next((e for e in g.into(node_id) if e["to_port"] == port.port_id), None)
            if not port.refit_per_fold or refit is None:
                continue
            plan = _fold_plan(g, node_id, refit)
            if plan is None:
                issues.append(GraphIssue(PIPELINE_FOLDS_SOURCE_MISMATCH, node_id, port.port_id))
            else:
                plans[node_id] = plan
    if any(i.severity == "error" for i in issues):
        return CompiledPipeline((), {}, tuple(issues))
    return CompiledPipeline(tuple(tasks), plans, tuple(issues))


def _fold_plan(g: _Graph, node_id: str, refit: Edge) -> FoldPlan | None:
    """The plan of validation node ``node_id``; ``None`` on a fold-source mismatch."""
    folds_edge = next((e for e in g.into(node_id) if e["to_port"] == "folds"), None)
    if folds_edge is None:
        raise ValueError(f"validation node {node_id!r} has refit_per_fold but no folds edge")
    producer = folds_edge["from_node"]
    spectra = [
        e for e in g.into(producer) if g.port_type(producer, e["to_port"], "inputs") == "Spectra"
    ]
    if len(spectra) != 1:
        raise ValueError(f"folds producer {producer!r} must have exactly one Spectra input edge")
    source_key = (spectra[0]["from_node"], spectra[0]["from_port"])

    downstream: set[str] = set()
    frontier = [e["to_node"] for e in g.edges if (e["from_node"], e["from_port"]) == source_key]
    while frontier:
        n = frontier.pop()
        if n not in downstream:
            downstream.add(n)
            frontier += [e["to_node"] for e in g.edges if e["from_node"] == n]

    upstream: set[str] = set()
    frontier = [refit["from_node"]]
    while frontier:
        n = frontier.pop()
        if n not in upstream:
            upstream.add(n)
            frontier += [e["from_node"] for e in g.into(n)]
    if refit["from_node"] not in downstream:
        return None
    return FoldPlan(
        node_id=node_id,
        port_id=refit["to_port"],
        source=g.wire(spectra[0], g.top, "data"),
        folds=g.wire(folds_edge, g.top, "folds"),
        nodes=tuple(n for n in g.order if n in downstream and n in upstream),
        refit_edge=refit,
        _graph=g,
        _source_key=source_key,
    )

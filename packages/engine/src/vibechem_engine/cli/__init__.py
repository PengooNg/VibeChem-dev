# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/cli/__init__.py
"""The ``vibechem`` command line (T2.11).

``vibechem run FILE --data DATASET_ID=path.csv`` runs a pipeline file and prints the metrics of
every node that produces ``Results``; ``vibechem validate FILE`` prints the issues found without
running; ``vibechem blocks list`` prints the registered blocks. Exit code 0 = success,
1 = invalid pipeline or failed run, 2 = usage error (bad arguments, unreadable file, missing data).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from vibechem_core.blocks import default_registry
from vibechem_core.data import SpectralDataset
from vibechem_core.errors import VibeChemError
from vibechem_engine.cli.data import dataset_from_file
from vibechem_engine.pipeline import Pipeline, results_of

__all__ = ["main"]

OK, FAILED, USAGE = 0, 1, 2


class _Usage(Exception):
    """A mistake in the command line or a file it names; exit code 2."""


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line; returns the exit code."""
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as stop:  # argparse exits on --help (0) and on a usage error (2)
        return int(stop.code or 0) if isinstance(stop.code, int) else USAGE
    try:
        return int(args.handler(args))
    except _Usage as error:
        print(f"vibechem: {error}", file=sys.stderr)
        return USAGE


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vibechem", description="VibeChem command line")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run a pipeline file and print its metrics")
    run.add_argument("file", type=Path)
    run.add_argument(
        "--data", action="append", default=[], metavar="DATASET_ID=PATH",
        help="table file for a data.dataset node (repeatable)",
    )  # fmt: skip
    run.add_argument("--seed", type=int, default=0, help="root random seed (default 0)")
    run.add_argument("--workers", type=int, default=None, help="worker processes (default: CPUs)")
    run.add_argument("--json", action="store_true", help="print the metrics as JSON")
    run.set_defaults(handler=_run)

    validate = sub.add_parser("validate", help="check a pipeline file without running it")
    validate.add_argument("file", type=Path)
    validate.set_defaults(handler=_validate)

    blocks = sub.add_parser("blocks", help="list the available blocks")
    blocks_sub = blocks.add_subparsers(dest="blocks_command", required=True)
    blocks_sub.add_parser("list", help="one line per block").set_defaults(handler=_blocks_list)
    return parser


def _load(path: Path) -> Pipeline:
    try:
        return Pipeline.load(path)
    except OSError as error:
        raise _Usage(f"cannot read {path}: {error.strerror or error}") from None
    except VibeChemError as error:
        raise _Usage(f"{path} is not a valid pipeline file: {error}") from None


def _issues(pipeline: Pipeline) -> list[dict[str, Any]]:
    try:
        return [i.to_dict() for i in pipeline.validate()]
    except ValueError as error:
        raise _Usage(f"invalid pipeline: {error}") from None


def _validate(args: argparse.Namespace) -> int:
    issues = _issues(_load(args.file))
    for i in issues:
        where = f" at {i['node_id']}" + (f".{i['port_id']}" if i["port_id"] else "")
        print(
            f"{i['severity']}: {i['code']}{where if i['node_id'] else ''} {i['params'] or ''}".rstrip()
        )
    errors = sum(i["severity"] == "error" for i in issues)
    print("valid" if not errors else f"invalid: {errors} error(s)")
    return OK if not errors else FAILED


def _data(specs: list[str]) -> dict[str, SpectralDataset]:
    data: dict[str, SpectralDataset] = {}
    for spec in specs:
        dataset_id, sep, path = spec.partition("=")
        if not sep or not dataset_id or not path:
            raise _Usage(f"--data expects DATASET_ID=PATH, got {spec!r}")
        if dataset_id in data:
            raise _Usage(f"--data given twice for {dataset_id!r}")
        try:
            data[dataset_id] = dataset_from_file(path, dataset_id)
        except OSError as error:
            raise _Usage(f"cannot read {path}: {error.strerror or error}") from None
        except (VibeChemError, ValueError) as error:
            raise _Usage(f"cannot use {path} as dataset {dataset_id!r}: {error}") from None
    return data


def _run(args: argparse.Namespace) -> int:
    pipeline = _load(args.file)
    data = _data(args.data)
    try:
        run = pipeline.run(data, seed=args.seed, max_workers=args.workers)
    except ValueError as error:
        raise _Usage(str(error)) from None
    if run.status != "succeeded":
        for task_id, error in run.errors.items():
            print(f"error in {task_id}: {error}", file=sys.stderr)
        print(f"run {run.status}", file=sys.stderr)
        return FAILED
    metrics = {
        node_id: {k: (v if math.isfinite(v) else None) for k, v in r.metrics.items()}
        for node_id, r in results_of(run, pipeline).items()
    }
    if args.json:
        print(json.dumps(metrics, indent=1))
    else:
        for node_id, values in metrics.items():
            for name, value in values.items():
                print(f"{node_id}\t{name}\t{value}")
        if not metrics:
            print("run succeeded; the pipeline has no node with metrics")
    return OK


def _blocks_list(_args: argparse.Namespace) -> int:
    for meta in default_registry().metadata():
        print(f"{meta.block_id}\t{meta.version}\t{meta.block_class}")
    return OK

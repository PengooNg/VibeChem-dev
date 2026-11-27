# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/formats/test_no_pickle.py
"""ADR-007 scan: no shipped Python module can write or read pickle.

Scans every module under ``packages/*/src``: no import of a pickle-based module, no
``allow_pickle=True``, and every ``np.load`` / ``numpy.load`` passes
``allow_pickle=False`` explicitly. In-memory pickling to loky workers happens inside
loky, not in our code, so it does not show up here.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
FORBIDDEN_MODULES = {"pickle", "_pickle", "cPickle", "cloudpickle", "dill", "shelve", "joblib"}


def problems(source: str, name: str) -> list[str]:
    found: list[str] = []
    for node in ast.walk(ast.parse(source, name)):
        if isinstance(node, ast.Import | ast.ImportFrom):
            modules = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
            found += [
                f"{name}:{node.lineno} imports {m}"
                for m in modules
                if m.split(".")[0] in FORBIDDEN_MODULES
            ]
        if not isinstance(node, ast.Call):
            continue
        flags = {k.arg: k.value for k in node.keywords}
        allow = flags.get("allow_pickle")
        if isinstance(allow, ast.Constant) and allow.value is True:
            found.append(f"{name}:{node.lineno} allow_pickle=True")
        func = node.func
        is_np_load = (
            isinstance(func, ast.Attribute)
            and func.attr == "load"
            and isinstance(func.value, ast.Name)
            and func.value.id in {"np", "numpy"}
        )
        if is_np_load and not (isinstance(allow, ast.Constant) and allow.value is False):
            found.append(f"{name}:{node.lineno} np.load without allow_pickle=False")
    return found


def test_scanner_finds_each_pattern() -> None:
    source = (
        "import pickle\nfrom joblib import dump\nnp.load(f)\nnp.save(f, a, allow_pickle=True)\n"
    )
    assert len(problems(source, "x.py")) == 4
    assert problems("np.load(f, allow_pickle=False)\n", "x.py") == []


def test_no_pickle_in_shipped_code() -> None:
    files = sorted(REPO.glob("packages/*/src/**/*.py"))
    assert len(files) > 20  # the scan really ran over the packages
    found = [
        p for f in files for p in problems(f.read_text(encoding="utf-8"), str(f.relative_to(REPO)))
    ]
    assert found == []

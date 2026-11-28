# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/cli/test_cli.py
"""``vibechem`` command line and ``vibechem.Pipeline`` (T2.11 "Done when").

Gasoline rows 1-50, leave-one-out PLS with 3 LV: the CLI's RMSECV must equal the published
value (Mevik & Wehrens 2007, testdata/expected/gasoline_nir_pls.json).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from vibechem import Pipeline, results_of
from vibechem_core.reference_datasets import load_expected
from vibechem_core.testing import assert_reference
from vibechem_engine.cli import main
from vibechem_engine.cli.data import dataset_from_file
from vibechem_engine.formats import load_pipeline

CSV = Path(__file__).parents[4] / "testdata" / "datasets" / "gasoline_nir.csv"
SOURCE = "Mevik & Wehrens 2007, testdata/expected/gasoline_nir_pls.json"


def _node(node_id: str, block_id: str, params: dict[str, Any]) -> dict[str, Any]:
    return {"node_id": node_id, "block_id": block_id, "block_version": "1.0.0", "params": params,
            "position": {"x": 0, "y": 0}, "label": None}  # fmt: skip


def _document(
    pls: dict[str, Any] | None = None, *, edges: list[tuple[str, ...]] | None = None
) -> dict[str, Any]:
    wires = edges or [("nd_a", "spectra", "nd_f", "spectra"), ("nd_a", "spectra", "nd_p", "spectra"),
                      ("nd_p", "model", "nd_c", "model"), ("nd_f", "folds", "nd_c", "folds")]  # fmt: skip
    return {
        "format_version": 1, "pipeline_id": "ppl_1", "name": "gasoline", "revision": 0,
        "nodes": [_node("nd_a", "data.dataset", {"dataset_id": "gas"}),
                  _node("nd_f", "validate.loo", {}),
                  _node("nd_p", "model.pls", pls if pls is not None else {"n_components": 3}),
                  _node("nd_c", "validate.cv", {})],
        "edges": [{"edge_id": f"eg_{i}", "from_node": a, "from_port": b, "to_node": c, "to_port": d}
                  for i, (a, b, c, d) in enumerate(wires)],
        "created_at": "2026-11-28T00:00:00Z", "updated_at": "2026-11-28T00:00:00Z",
    }  # fmt: skip


@pytest.fixture(scope="module")
def table(tmp_path_factory: pytest.TempPathFactory) -> Path:
    lines = CSV.read_text(encoding="utf-8").splitlines()[:51]  # header + samples 1-50
    path = tmp_path_factory.mktemp("data") / "gas50.csv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write(tmp_path: Path, doc: dict[str, Any]) -> Path:
    path = tmp_path / "p.vcp.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def test_run_prints_the_published_rmsecv(
    tmp_path: Path, table: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["run", str(_write(tmp_path, _document())), "--data", f"gas={table}",
                 "--workers", "2", "--json"])  # fmt: skip
    assert code == 0
    metrics = json.loads(capsys.readouterr().out)["nd_c"]
    name = next(k for k in metrics if k.lower() == "rmsecv")
    expected = load_expected("gasoline_nir_pls")
    assert_reference(method="CLI run, LOO PLS 3 LV RMSECV", dataset="gasoline_nir rows 1-50",
                     actual=metrics[name], expected=expected["values"]["rmsep_cv"][3],
                     rtol=expected["tolerance"]["rtol"], atol=0.0, source=SOURCE)  # fmt: skip


def test_python_api_matches_the_cli_and_is_deterministic(tmp_path: Path, table: Path) -> None:
    path = _write(tmp_path, _document())
    pipeline = Pipeline.load(path)
    assert pipeline.dataset_ids == ("gas",)
    assert pipeline.validate() == []
    data = {"gas": dataset_from_file(table, "gas")}
    first = results_of(pipeline.run(data, max_workers=1), pipeline)["nd_c"].metrics
    second = results_of(pipeline.run(data, max_workers=1), pipeline)["nd_c"].metrics
    assert first == second
    assert load_pipeline(path).name == "gasoline"


def test_run_rejects_missing_and_unused_data(table: Path) -> None:
    pipeline = Pipeline(_document())
    gas = dataset_from_file(table, "gas")
    with pytest.raises(ValueError, match=r"missing for \['gas'\]"):
        pipeline.run({})
    with pytest.raises(ValueError, match=r"not used by any node: \['other'\]"):
        pipeline.run({"gas": gas, "other": gas})


def test_validate_reports_a_bad_parameter_and_a_bad_graph(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["validate", str(_write(tmp_path, _document()))]) == 0
    assert capsys.readouterr().out.strip() == "valid"
    assert main(["validate", str(_write(tmp_path, _document({"n_components": 0})))]) == 1
    assert "BLOCK_PARAM_INVALID at nd_p" in capsys.readouterr().out
    cut = _document(edges=[("nd_a", "spectra", "nd_f", "spectra"), ("nd_f", "folds", "nd_c", "folds"),
                           ("nd_a", "spectra", "nd_p", "spectra")])  # fmt: skip
    assert main(["validate", str(_write(tmp_path, cut))]) == 1
    assert "PIPELINE_REQUIRED_INPUT_MISSING" in capsys.readouterr().out


def test_blocks_list_names_every_block(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["blocks", "list"]) == 0
    ids = [line.split("\t")[0] for line in capsys.readouterr().out.splitlines()]
    assert ids == sorted(ids)
    assert {"data.dataset", "preprocess.snv", "model.pls", "validate.cv"} <= set(ids)


@pytest.mark.parametrize(
    "argv",
    [["run", "{p}"], ["run", "{p}", "--data", "gas"], ["run", "{p}", "--data", "gas={t}", "--data", "gas={t}"],
     ["run", "{p}", "--data", "gas={nofile}"], ["run", "{nofile}"], ["validate", "{nofile}"]],
)  # fmt: skip
def test_usage_errors_exit_2_and_run_nothing(
    argv: list[str], tmp_path: Path, table: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = _write(tmp_path, _document())
    nofile = tmp_path / "missing"
    args = [a.format(p=p, t=table, nofile=nofile) for a in argv]
    assert main(args) == 2
    assert "vibechem:" in capsys.readouterr().err


def test_invalid_pipelines_exit_1_and_bad_workers_exit_2(
    tmp_path: Path, table: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cut = _document(edges=[("nd_a", "spectra", "nd_f", "spectra"), ("nd_f", "folds", "nd_c", "folds"),
                           ("nd_a", "spectra", "nd_p", "spectra")])  # fmt: skip
    unknown = _document()
    unknown["nodes"][2]["block_id"] = "model.nope"
    for doc in (cut, unknown):
        assert main(["run", str(_write(tmp_path, doc)), "--data", f"gas={table}"]) == 1
        assert main(["validate", str(_write(tmp_path, doc))]) == 1
    broken = tmp_path / "broken.vcp.json"
    broken.write_text("{}", encoding="utf-8")
    assert main(["validate", str(broken)]) == 1
    assert main(["run", str(_write(tmp_path, _document())), "--workers", "0"]) == 2
    assert capsys.readouterr().err.count("vibechem:") == 5


def test_empty_spectral_cells_are_refused(tmp_path: Path) -> None:
    lines = CSV.read_text(encoding="utf-8").splitlines()[:51]
    cells = lines[2].split(",")
    cells[10] = ""  # one empty spectral cell
    lines[2] = ",".join(cells)
    path = tmp_path / "gap.csv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="empty or non-numeric"):
        dataset_from_file(path, "gas")


def test_bad_arguments_exit_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["nonsense"]) == 2
    assert main([]) == 2
    capsys.readouterr()
    assert main(["--help"]) == 0

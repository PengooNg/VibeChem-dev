# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/api/test_main.py
"""Engine start-up (``python -m vibechem_engine.api``): loopback socket and handshake line."""

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from fastapi.testclient import TestClient

from vibechem_core.reference_datasets import find_testdata_dir
from vibechem_engine.api.__main__ import main


class _Captured:
    app: Any = None
    sockets: list[socket.socket] | None = None


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> _Captured:
    """Replace ``uvicorn.Server.run`` so ``main`` returns instead of serving."""
    result = _Captured()

    def fake_run(self: uvicorn.Server, sockets: list[socket.socket] | None = None) -> None:
        result.app = self.config.app
        result.sockets = sockets

    monkeypatch.setattr(uvicorn.Server, "run", fake_run)
    return result


def test_main_announces_port_and_token_of_a_loopback_socket(
    captured: _Captured, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([]) == 0
    line = capsys.readouterr().out
    assert line.endswith("\n")
    assert line.count("\n") == 1
    announced = json.loads(line)
    assert set(announced) == {"event", "port", "token"}
    assert announced["event"] == "engine.listening"

    assert captured.sockets is not None
    (sock,) = captured.sockets
    try:
        assert sock.getsockname() == ("127.0.0.1", announced["port"])
        assert announced["port"] > 0
    finally:
        sock.close()

    with TestClient(captured.app) as client:
        assert client.get("/api/v1/health").status_code == 401
        auth = {"Authorization": f"Bearer {announced['token']}"}
        assert client.get("/api/v1/health", headers=auth).status_code == 200


def test_each_launch_gets_a_new_token(
    captured: _Captured, capsys: pytest.CaptureFixture[str]
) -> None:
    tokens: list[str] = []
    for _ in range(2):
        main([])
        tokens.append(json.loads(capsys.readouterr().out)["token"])
        assert captured.sockets is not None
        captured.sockets[0].close()
    assert tokens[0] != tokens[1]


@pytest.mark.parametrize(("env", "allowed"), [("1", True), (None, False), ("0", False)])
def test_dev_mode_follows_vibechem_dev(
    captured: _Captured,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    env: str | None,
    *,
    allowed: bool,
) -> None:
    if env is None:
        monkeypatch.delenv("VIBECHEM_DEV", raising=False)
    else:
        monkeypatch.setenv("VIBECHEM_DEV", env)
    main(["--testdata-dir", str(find_testdata_dir())])
    token = json.loads(capsys.readouterr().out)["token"]
    assert captured.sockets is not None
    captured.sockets[0].close()
    headers = {"Authorization": f"Bearer {token}", "Origin": "http://localhost:5173"}
    with TestClient(captured.app) as client:
        status = client.get("/api/v1/health", headers=headers).status_code
    assert status == (200 if allowed else 403)


def test_bad_testdata_dir_exits_with_usage_error(
    captured: _Captured, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--testdata-dir", str(tmp_path)])
    assert exc.value.code == 2
    assert "PROVENANCE.md" in capsys.readouterr().err
    assert captured.sockets is None


def test_missing_testdata_exits_with_usage_error(
    captured: _Captured, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def not_found() -> Path:
        raise FileNotFoundError("testdata not found")

    monkeypatch.setattr("vibechem_engine.api.__main__.find_testdata_dir", not_found)
    with pytest.raises(SystemExit):
        main([])
    assert "testdata not found" in capsys.readouterr().err
    assert captured.sockets is None

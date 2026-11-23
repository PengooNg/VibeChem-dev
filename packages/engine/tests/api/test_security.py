# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/api/test_security.py
"""Token and Origin checks (DATA_MODEL.md §1): 401, 403, CORS preflight."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from vibechem_engine.api.security import APP_ORIGIN, new_session_token

HEALTH = "/api/v1/health"
DEV_ORIGIN = "http://localhost:5173"


def assert_problem(body: dict[str, Any], status: int, code: str) -> None:
    assert body["status"] == status
    assert body["code"] == code
    assert body["message_key"] == f"errors.api.{code.lower()}"
    assert body["params"] == {}


@pytest.mark.parametrize(
    "authorization",
    [None, "Bearer wrong", "{token}", "Basic {token}", "Bearer {token}x", "bearer {token}"],
)
def test_missing_or_wrong_token_is_401(
    client: TestClient, token: str, authorization: str | None
) -> None:
    headers = {} if authorization is None else {"Authorization": authorization.format(token=token)}
    response = client.get(HEALTH, headers=headers)
    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    assert_problem(response.json(), 401, "AUTH_TOKEN_INVALID")


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/api/v1/blocks"), ("POST", "/api/v1/skeleton/run"), ("GET", "/api/v1/nope")],
)
def test_token_checked_on_every_path(client: TestClient, method: str, path: str) -> None:
    assert client.request(method, path, json={}).status_code == 401


def test_correct_token_without_origin_is_allowed(client: TestClient, auth: dict[str, str]) -> None:
    assert client.get(HEALTH, headers=auth).status_code == 200


def test_app_origin_is_allowed_and_gets_cors_headers(
    client: TestClient, auth: dict[str, str]
) -> None:
    response = client.get(HEALTH, headers={**auth, "Origin": APP_ORIGIN})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == APP_ORIGIN
    assert "x-vibechem-preview-mode" in response.headers["access-control-expose-headers"].lower()


@pytest.mark.parametrize(
    "origin", ["http://evil.example", "null", DEV_ORIGIN, "app://vibechem.evil"]
)
def test_foreign_origin_is_403_even_with_token(
    client: TestClient, auth: dict[str, str], origin: str
) -> None:
    response = client.get(HEALTH, headers={**auth, "Origin": origin})
    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"
    assert "access-control-allow-origin" not in response.headers
    assert_problem(response.json(), 403, "ORIGIN_FORBIDDEN")


def test_origin_is_checked_before_token(client: TestClient) -> None:
    assert client.get(HEALTH, headers={"Origin": "http://evil.example"}).status_code == 403


def test_dev_mode_allows_vite_dev_server_origin(
    dev_client: TestClient, auth: dict[str, str]
) -> None:
    response = dev_client.get(HEALTH, headers={**auth, "Origin": DEV_ORIGIN})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == DEV_ORIGIN


def test_dev_mode_still_needs_the_token(dev_client: TestClient) -> None:
    assert dev_client.get(HEALTH, headers={"Origin": DEV_ORIGIN}).status_code == 401


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:5173.evil.example",
        "http://localhost",
        "https://localhost:5173",
        "http://127.0.0.1:5173",
        "http://evil.example/http://localhost:5173",
    ],
)
def test_dev_mode_still_rejects_other_origins(
    dev_client: TestClient, auth: dict[str, str], origin: str
) -> None:
    assert dev_client.get(HEALTH, headers={**auth, "Origin": origin}).status_code == 403


def test_cors_preflight_from_allowed_origin_needs_no_token(dev_client: TestClient) -> None:
    response = dev_client.options(
        "/api/v1/skeleton/run",
        headers={
            "Origin": DEV_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization, content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == DEV_ORIGIN


def test_cors_preflight_from_foreign_origin_is_403(client: TestClient) -> None:
    response = client.options(
        HEALTH, headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"}
    )
    assert response.status_code == 403


def test_session_tokens_are_random_and_long() -> None:
    tokens = {new_session_token() for _ in range(10)}
    assert len(tokens) == 10
    assert all(len(t) >= 40 for t in tokens)

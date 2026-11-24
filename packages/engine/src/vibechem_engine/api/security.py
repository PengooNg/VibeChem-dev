# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/api/security.py
"""Session token and Origin checks for the local engine API (DATA_MODEL.md §1).

The engine listens on 127.0.0.1 only. Every HTTP request must

1. come from an allowed Origin, or carry no Origin header (else ``403 ORIGIN_FORBIDDEN``);
2. carry ``Authorization: Bearer <session_token>`` (else ``401 AUTH_TOKEN_INVALID``).

CORS preflight requests (which never carry the token) are answered by Starlette's
``CORSMiddleware``, placed between the two checks by :func:`install_security`.
"""

from __future__ import annotations

import re
import secrets
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.websockets import WebSocketClose

__all__ = [
    "APP_ORIGIN",
    "DEV_ORIGIN_REGEX",
    "PREVIEW_MODE_HEADER",
    "install_security",
    "new_session_token",
    "problem",
]

APP_ORIGIN = "app://vibechem"
"""Origin of the built renderer, served by Electron main from a custom scheme (T0.11).

Must equal ``APP_ORIGIN`` in ``app/main/appOrigin.ts``.
"""

DEV_ORIGIN_REGEX = r"http://localhost:\d+"
"""Vite dev server origin, allowed only in dev mode (``VIBECHEM_DEV=1``)."""

PREVIEW_MODE_HEADER = "X-VibeChem-Preview-Mode"


def new_session_token() -> str:
    """Return a fresh random session token (per launch; never written to disk)."""
    return secrets.token_urlsafe(32)


def problem(status: int, code: str, title: str) -> JSONResponse:
    """RFC 9457 problem details for an engine API error (DATA_MODEL.md §1 "Error body").

    ``message_key`` follows the §1 example: the code's first word is the namespace
    (``AUTH_TOKEN_INVALID`` → ``errors.auth.token_invalid``).
    """
    namespace, _, rest = code.lower().partition("_")
    body: dict[str, Any] = {
        "type": f"https://vibechem.org/errors/{code.lower().replace('_', '-')}",
        "title": title,
        "status": status,
        "code": code,
        "message_key": f"errors.{namespace}.{rest}",
        "params": {},
    }
    return JSONResponse(body, status_code=status, media_type="application/problem+json")


class _OriginCheck:
    """Reject HTTP requests and WebSocket handshakes from a present, not allowed Origin.

    HTTP gets ``403 ORIGIN_FORBIDDEN``; a WebSocket handshake is closed before accept
    (the server answers it with 403).
    """

    def __init__(self, app: ASGIApp, allowed: frozenset[str], allowed_regex: str | None) -> None:
        self.app = app
        self.allowed = allowed
        self.allowed_regex = None if allowed_regex is None else re.compile(allowed_regex)

    def is_allowed(self, origin: str | None) -> bool:
        if origin is None or origin in self.allowed:
            return True
        return self.allowed_regex is not None and self.allowed_regex.fullmatch(origin) is not None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in {"http", "websocket"} and not self.is_allowed(
            Headers(scope=scope).get("origin")
        ):
            if scope["type"] == "websocket":
                await WebSocketClose(code=1008)(scope, receive, send)  # policy violation
            else:
                response = problem(403, "ORIGIN_FORBIDDEN", "Request not from the app")
                await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


class _TokenCheck:
    """Reject HTTP requests without the session bearer token (401).

    The scheme ``Bearer`` is case-insensitive (RFC 9110 §11.1). WebSockets authenticate
    with their first message (DATA_MODEL.md §3), not here.
    """

    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app = app
        self.expected = token.encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            scheme, _, given = Headers(scope=scope).get("authorization", "").partition(" ")
            if scheme.lower() != "bearer" or not secrets.compare_digest(
                given.encode(), self.expected
            ):
                response = problem(401, "AUTH_TOKEN_INVALID", "Missing or wrong session token")
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def install_security(app: FastAPI, token: str, *, dev: bool) -> None:
    """Add Origin check → CORS → token check to ``app`` (outermost first).

    ``dev`` additionally allows the Vite dev server origin (DATA_MODEL.md §1).
    """
    allowed = frozenset({APP_ORIGIN})
    allowed_regex = DEV_ORIGIN_REGEX if dev else None
    # add_middleware wraps the app: the last one added runs first.
    app.add_middleware(_TokenCheck, token=token)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(allowed),
        allow_origin_regex=allowed_regex,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "If-Match"],
        expose_headers=[PREVIEW_MODE_HEADER],
    )
    app.add_middleware(_OriginCheck, allowed=allowed, allowed_regex=allowed_regex)

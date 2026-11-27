# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/errors.py
"""Error and warning classes with codes (DATA_MODEL.md §1 error body, §7 catalogue).

Every user-facing error raised by VibeChem code is a ``VibeChemError`` subclass that
carries a ``code`` from DATA_MODEL.md §7, the translation ``message_key`` derived from
it and the ``params`` the UI fills into the translated text. The codes themselves are
defined as constants in the module listed for them in §7 (e.g. ``block.py``), so
searching for a code finds its origin.

Non-fatal conditions found while a block runs are reported as a ``VibeChemWarning``
with ``warnings.warn``; the block still returns its outputs, and the engine records the
warning for the node (ARCHITECTURE.md ADR-010). Its ``message_key`` starts with
``warnings.`` instead of ``errors.``.

Mistakes in block definitions (an invalid ``block_id``, an unknown port type) are
programming errors and raise ``TypeError``/``ValueError`` instead.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal

_CODE = re.compile(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+")

type ErrorParam = str | int | float | bool | list[ErrorParam] | None
"""A JSON-compatible value that can be filled into a translated message."""


def message_key(code: str, kind: Literal["errors", "warnings"] = "errors") -> str:
    """Translation key for an error or warning code (DATA_MODEL.md §1).

    The first word of the code is the area, the rest the message name:
    ``PIPELINE_PORT_TYPE_MISMATCH`` -> ``errors.pipeline.port_type_mismatch``;
    with ``kind="warnings"``, ``VALIDATION_GROUPS_IGNORED`` ->
    ``warnings.validation.groups_ignored``.
    """
    if not _CODE.fullmatch(code):
        raise ValueError(
            f"invalid error code {code!r}: expected UPPER_SNAKE_CASE with an area prefix"
        )
    area, _, name = code.partition("_")
    return f"{kind}.{area.lower()}.{name.lower()}"


class VibeChemError(Exception):
    """Base class of every coded VibeChem error.

    Parameters
    ----------
    code : str
        Error code from DATA_MODEL.md §7.
    params : mapping, optional
        Values for the translated message (``params`` of the error body).
    """

    def __init__(self, code: str, params: Mapping[str, ErrorParam] | None = None) -> None:
        self.code: str = code
        self.message_key: str = message_key(code)
        self.params: Mapping[str, ErrorParam] = MappingProxyType(dict(params or {}))
        super().__init__(f"{code} {dict(self.params)}" if self.params else code)

    def __reduce__(self) -> tuple[type[VibeChemError], tuple[str, dict[str, ErrorParam]]]:
        # Errors raised in a worker process are pickled back to the scheduler (in memory).
        return (type(self), (self.code, dict(self.params)))


class BlockError(VibeChemError):
    """A block failed while running; the node is set to ``error`` (DATA_MODEL.md §1, §3)."""


class BlockInputError(BlockError):
    """A block's input data cannot be processed (e.g. ``BLOCK_CONSTANT_SPECTRA``)."""


class ParamError(VibeChemError):
    """A parameter value breaks the block's schema (``BLOCK_PARAM_INVALID``, DATA_MODEL.md §5.3).

    Reported as a pipeline validation issue, or as a node error when found during a run.
    """


class VibeChemWarning(UserWarning):
    """A coded, non-fatal condition (ARCHITECTURE.md ADR-010).

    Raised with ``warnings.warn(VibeChemWarning(code, params), stacklevel=2)``; the
    engine collects it with ``warnings.catch_warnings(record=True)`` and reports it as a
    ``severity: "warning"`` issue of the node.

    Parameters
    ----------
    code : str
        Warning code from DATA_MODEL.md §7.
    params : mapping, optional
        Values for the translated message.
    """

    def __init__(self, code: str, params: Mapping[str, ErrorParam] | None = None) -> None:
        self.code: str = code
        self.message_key: str = message_key(code, "warnings")
        self.params: Mapping[str, ErrorParam] = MappingProxyType(dict(params or {}))
        super().__init__(f"{code} {dict(self.params)}" if self.params else code)

    def __reduce__(self) -> tuple[type[VibeChemWarning], tuple[str, dict[str, ErrorParam]]]:
        # Warnings recorded in a worker process are pickled back to the scheduler.
        return (type(self), (self.code, dict(self.params)))

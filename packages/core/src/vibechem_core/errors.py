# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/errors.py
"""Error classes with codes (DATA_MODEL.md §1 error body, §7 catalogue).

Every user-facing error raised by VibeChem code is a ``VibeChemError`` subclass that
carries a ``code`` from DATA_MODEL.md §7, the translation ``message_key`` derived from
it and the ``params`` the UI fills into the translated text. The codes themselves are
defined as constants in the module listed for them in §7 (e.g. ``block.py``), so
searching for a code finds its origin.

Mistakes in block definitions (an invalid ``block_id``, an unknown port type) are
programming errors and raise ``TypeError``/``ValueError`` instead.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType

_CODE = re.compile(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+")

type ErrorParam = str | int | float | bool | list[ErrorParam] | None
"""A JSON-compatible value that can be filled into a translated message."""


def message_key(code: str) -> str:
    """Translation key for an error code (DATA_MODEL.md §1).

    The first word of the code is the area, the rest the message name:
    ``PIPELINE_PORT_TYPE_MISMATCH`` -> ``errors.pipeline.port_type_mismatch``.
    """
    if not _CODE.fullmatch(code):
        raise ValueError(
            f"invalid error code {code!r}: expected UPPER_SNAKE_CASE with an area prefix"
        )
    area, _, name = code.partition("_")
    return f"errors.{area.lower()}.{name.lower()}"


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

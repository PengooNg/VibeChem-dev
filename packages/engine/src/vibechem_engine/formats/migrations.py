# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/formats/migrations.py
"""Format versions and migrations of the file formats (DATA_MODEL.md §6.5).

A migration upgrades the parsed JSON document of one format by exactly one version,
before the document is validated against the current model:

    @migration("pipeline", 1)
    def _pipeline_1_to_2(doc: dict[str, Any]) -> dict[str, Any]:
        doc["format_version"] = 2
        ...
        return doc

and :data:`CURRENT_VERSIONS` is raised to 2 in the same change. A file newer than the
current version, or one with no migration path, is rejected with reason ``version``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from vibechem_engine.formats._files import fail

type Migration = Callable[[dict[str, Any]], dict[str, Any]]

CURRENT_VERSIONS: dict[str, int] = {"pipeline": 1, "project": 1, "model": 1}
MIGRATIONS: dict[tuple[str, int], Migration] = {}


def migration(kind: str, from_version: int) -> Callable[[Migration], Migration]:
    """Register ``fn`` as the migration of ``kind`` from ``from_version`` to the next."""

    def register(fn: Migration) -> Migration:
        if (kind, from_version) in MIGRATIONS:
            raise ValueError(f"{kind} migration from version {from_version} already exists")
        MIGRATIONS[(kind, from_version)] = fn
        return fn

    return register


def migrate(kind: str, doc: dict[str, Any], code: str) -> dict[str, Any]:
    """``doc`` upgraded to ``CURRENT_VERSIONS[kind]``; ``FormatError`` reason ``version``."""
    current = CURRENT_VERSIONS[kind]
    version = doc.get("format_version")
    while type(version) is int and version < current and (kind, version) in MIGRATIONS:
        doc = MIGRATIONS[(kind, version)](doc)
        if doc.get("format_version") != version + 1:
            raise RuntimeError(f"{kind} migration from {version} did not set format_version")
        version += 1
    if version != current or type(version) is not int:
        found = version if type(version) is int else None
        raise fail(code, "version", found=found, supported=current)
    return doc

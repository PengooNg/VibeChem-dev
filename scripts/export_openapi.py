# SPDX-License-Identifier: GPL-3.0-or-later
# scripts/export_openapi.py
"""Write the engine API's OpenAPI document to a JSON file (no server is started).

Used by ``pnpm --dir app gen:api``, which turns it into ``app/renderer/src/api/schema.d.ts``
with openapi-typescript (TECH_STACK.md §6: API types only from the generated file).

    uv run python scripts/export_openapi.py OUT.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from vibechem_engine.api import create_app


def export_openapi(out: Path) -> None:
    """Build the app with a throw-away token and write its OpenAPI schema to ``out``."""
    # The token and the testdata folder are not part of the schema; any value works.
    app = create_app("unused", testdata_dir=Path())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python scripts/export_openapi.py OUT.json", file=sys.stderr)
        return 2
    export_openapi(Path(argv[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

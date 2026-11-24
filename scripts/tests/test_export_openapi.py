# SPDX-License-Identifier: GPL-3.0-or-later
# scripts/tests/test_export_openapi.py
"""Unit tests for scripts/export_openapi.py."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import export_openapi


class ExportOpenapiTest(unittest.TestCase):
    def test_writes_the_skeleton_endpoints_and_request_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "sub" / "openapi.json"
            self.assertEqual(export_openapi.main([str(out)]), 0)
            doc = json.loads(out.read_text(encoding="utf-8"))
        self.assertIn("/api/v1/health", doc["paths"])
        self.assertIn("/api/v1/skeleton/run", doc["paths"])
        request = doc["components"]["schemas"]["SkeletonRunRequest"]
        self.assertEqual(set(request["properties"]), {"dataset", "apply_snv", "width"})

    def test_usage_error_without_exactly_one_argument(self) -> None:
        self.assertEqual(export_openapi.main([]), 2)

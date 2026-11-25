# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/io/__init__.py
"""File readers (DATA_MODEL.md §2.5 imports).

File-format libraries (openpyxl, later jcamp) are imported only inside this package
(TECH_STACK.md §3.1).
"""

from vibechem_core.io.table import (
    IMPORT_DUPLICATE_SAMPLE_IDS,
    IMPORT_FILE_INVALID,
    IMPORT_FORMAT_UNKNOWN,
    IMPORT_NON_NUMERIC_VALUES,
    ImportWarning,
    SpectralColumns,
    SuggestedRoles,
    TableImport,
    read_table,
)

__all__ = [
    "IMPORT_DUPLICATE_SAMPLE_IDS",
    "IMPORT_FILE_INVALID",
    "IMPORT_FORMAT_UNKNOWN",
    "IMPORT_NON_NUMERIC_VALUES",
    "ImportWarning",
    "SpectralColumns",
    "SuggestedRoles",
    "TableImport",
    "read_table",
]

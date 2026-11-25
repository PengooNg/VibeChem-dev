# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/io/__init__.py
"""File readers (DATA_MODEL.md §2.5 imports).

File-format libraries (openpyxl, jcamp, brukeropus) are imported only inside this package
(TECH_STACK.md §3.1).
"""

from vibechem_core.io.jcamp import read_jcamp
from vibechem_core.io.multifile import SOURCE_FILE, read_file, read_files
from vibechem_core.io.perkinelmer import read_perkinelmer
from vibechem_core.io.spa import read_spa
from vibechem_core.io.spc import read_spc
from vibechem_core.io.table import (
    IMPORT_AXIS_MISMATCH,
    IMPORT_DUPLICATE_SAMPLE_IDS,
    IMPORT_FILE_INVALID,
    IMPORT_FORMAT_UNKNOWN,
    IMPORT_NON_NUMERIC_VALUES,
    ImportWarning,
    SpectralColumns,
    SuggestedRoles,
    TableImport,
    read_table,
    spectra_import,
)
from vibechem_core.io.wdf import read_wdf

__all__ = [
    "IMPORT_AXIS_MISMATCH",
    "IMPORT_DUPLICATE_SAMPLE_IDS",
    "IMPORT_FILE_INVALID",
    "IMPORT_FORMAT_UNKNOWN",
    "IMPORT_NON_NUMERIC_VALUES",
    "SOURCE_FILE",
    "ImportWarning",
    "SpectralColumns",
    "SuggestedRoles",
    "TableImport",
    "read_file",
    "read_files",
    "read_jcamp",
    "read_perkinelmer",
    "read_spa",
    "read_spc",
    "read_table",
    "read_wdf",
    "spectra_import",
]

# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/test_errors.py
"""Tests for ``vibechem_core.errors``."""

import copy
import pickle
import warnings
from pathlib import Path

import pytest

from vibechem_core.errors import (
    BlockError,
    BlockInputError,
    VibeChemError,
    VibeChemWarning,
    message_key,
)


@pytest.mark.parametrize(
    ("code", "key"),
    [
        (
            "PIPELINE_PORT_TYPE_MISMATCH",
            "errors.pipeline.port_type_mismatch",
        ),  # DATA_MODEL §1 example
        ("BLOCK_CONSTANT_SPECTRA", "errors.block.constant_spectra"),
        ("AUTH_TOKEN_INVALID", "errors.auth.token_invalid"),
    ],
)
def test_message_key_follows_the_documented_pattern(code: str, key: str) -> None:
    assert message_key(code) == key


@pytest.mark.parametrize(
    "code", ["", "BLOCK", "block_constant_spectra", "BLOCK__X", "_BLOCK_X", "BLOCK-X"]
)
def test_message_key_rejects_malformed_codes(code: str) -> None:
    with pytest.raises(ValueError, match="invalid error code"):
        message_key(code)


def test_error_carries_code_key_and_params() -> None:
    error = BlockInputError(code="BLOCK_CONSTANT_SPECTRA", params={"rows": [0, 3]})
    assert error.code == "BLOCK_CONSTANT_SPECTRA"
    assert error.message_key == "errors.block.constant_spectra"
    assert dict(error.params) == {"rows": [0, 3]}
    assert "BLOCK_CONSTANT_SPECTRA" in str(error)


def test_params_are_read_only_and_default_to_empty() -> None:
    error = VibeChemError("BLOCK_CONSTANT_SPECTRA")
    assert dict(error.params) == {}
    assert str(error) == "BLOCK_CONSTANT_SPECTRA"
    with pytest.raises(TypeError):
        error.params["x"] = 1  # type: ignore[index]


def test_params_are_copied() -> None:
    source = {"n": 1}
    error = VibeChemError("BLOCK_CONSTANT_SPECTRA", source)
    source["n"] = 2
    assert error.params["n"] == 1


def test_hierarchy() -> None:
    assert issubclass(BlockInputError, BlockError)
    assert issubclass(BlockError, VibeChemError)
    assert issubclass(VibeChemError, Exception)


def test_malformed_code_is_rejected_at_construction() -> None:
    with pytest.raises(ValueError, match="invalid error code"):
        BlockError("constant spectra")


def test_every_catalogued_code_has_a_message_key() -> None:
    data_model = Path(__file__).resolve().parents[3] / "docs" / "DATA_MODEL.md"
    section = data_model.read_text(encoding="utf-8").split("## 7. Error codes catalogue")[1]
    codes = [
        line.split("|")[1].strip(" `") for line in section.splitlines() if line.startswith("| `")
    ]
    assert len(codes) > 20
    for code in codes:
        assert message_key(code).startswith("errors.")


def test_errors_survive_pickle_and_copy() -> None:
    error = BlockInputError("BLOCK_CONSTANT_SPECTRA", {"rows": [1]})
    for clone in (pickle.loads(pickle.dumps(error)), copy.copy(error)):
        assert type(clone) is BlockInputError
        assert clone.code == error.code
        assert dict(clone.params) == {"rows": [1]}
        assert str(clone) == str(error)


def test_warning_carries_code_warnings_key_and_params() -> None:
    warning = VibeChemWarning("BLOCK_AXIS_NOT_UNIFORM", {"max_deviation": 0.05})
    assert isinstance(warning, UserWarning)
    assert warning.code == "BLOCK_AXIS_NOT_UNIFORM"
    assert warning.message_key == "warnings.block.axis_not_uniform"
    assert dict(warning.params) == {"max_deviation": 0.05}
    assert str(warning) == "BLOCK_AXIS_NOT_UNIFORM {'max_deviation': 0.05}"
    assert message_key("VALIDATION_GROUPS_IGNORED", "warnings") == (
        "warnings.validation.groups_ignored"  # DATA_MODEL §2.6 example
    )
    with pytest.raises(ValueError, match="invalid error code"):
        VibeChemWarning("axis not uniform")


def test_warning_is_recorded_by_catch_warnings_and_survives_pickle() -> None:
    # The engine's collection route (ARCHITECTURE.md ADR-010).
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        warnings.warn(
            VibeChemWarning("BLOCK_AXIS_NOT_UNIFORM", {"max_deviation": 0.5}), stacklevel=1
        )
    (record,) = caught
    assert isinstance(record.message, VibeChemWarning)
    clone = pickle.loads(pickle.dumps(record.message))
    assert type(clone) is VibeChemWarning
    assert clone.code == "BLOCK_AXIS_NOT_UNIFORM"
    assert dict(clone.params) == {"max_deviation": 0.5}

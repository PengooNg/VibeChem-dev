# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/test_registry.py
"""Tests for ``vibechem_core.registry``."""

import pytest

from vibechem_core.block import Block
from vibechem_core.registry import Registry
from vibechem_core.testing import DummyCenter, DummyOffset


def make_registry() -> Registry:
    registry = Registry()
    registry.register(DummyOffset)
    registry.register(DummyCenter)
    return registry


def test_registry_lists_dummy_blocks_with_their_metadata() -> None:
    registry = make_registry()
    assert registry.block_ids() == ("testing.center", "testing.offset")
    assert len(registry) == 2
    assert list(registry) == [DummyCenter, DummyOffset]
    listed = [m.to_dict() for m in registry.metadata()]
    assert listed == [DummyCenter.metadata().to_dict(), DummyOffset.metadata().to_dict()]
    assert [(m["block_id"], m["fitted"], m["tier"]) for m in listed] == [
        ("testing.center", True, "P1"),
        ("testing.offset", False, "P0"),
    ]


def test_get_and_meta_by_id() -> None:
    registry = make_registry()
    assert registry.get("testing.offset") is DummyOffset
    assert registry.meta("testing.center").fitted is True
    assert "testing.offset" in registry
    assert "preprocess.snv" not in registry


def test_unknown_block_id() -> None:
    registry = make_registry()
    with pytest.raises(KeyError, match=r"unknown block_id 'preprocess\.snv'"):
        registry.get("preprocess.snv")
    with pytest.raises(KeyError, match="unknown block_id"):
        registry.meta("preprocess.snv")


def test_register_works_as_decorator_and_is_idempotent() -> None:
    registry = Registry()
    decorated = registry.register(DummyOffset)
    assert decorated is DummyOffset
    registry.register(DummyOffset)
    assert len(registry) == 1


def test_duplicate_block_id_from_another_class_is_rejected() -> None:
    registry = make_registry()

    class Imposter(DummyOffset):
        pass

    with pytest.raises(ValueError, match="already registered by DummyOffset"):
        registry.register(Imposter)
    assert registry.get("testing.offset") is DummyOffset


def test_invalid_block_is_not_registered() -> None:
    registry = Registry()

    class Broken(Block):
        block_id = "broken"

    with pytest.raises(TypeError, match="must define version"):
        registry.register(Broken)
    assert len(registry) == 0

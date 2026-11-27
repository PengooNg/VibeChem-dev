# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/cache/test_store.py
"""``vibechem_engine.cache.ResultCache``: round trip, LRU cap, corrupt-entry recovery
(T2.06 "Done when"; ARCHITECTURE.md §3.6 "checksum mismatch -> discard and recompute")."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from vibechem_core.block import State
from vibechem_engine.cache import ResultCache


def _key(i: int) -> str:
    return f"res_{i:064x}"


def _state(n: int = 100, fill: float = 1.0) -> State:
    return State({"note": "x", "n": n}, {"x": np.full(n, fill), "ids": np.arange(3)})


def _entry(root: Path, i: int) -> Path:
    return root / "entries" / f"{i:064x}"


def _stored(cache: ResultCache, n: int = 10) -> set[int]:
    return {i for i in range(n) if _key(i) in cache}


def _x0(cache: ResultCache, i: int) -> float:
    got = cache.get(_key(i))
    assert got is not None
    return float(got.arrays["x"][0])


def test_round_trip_and_reopen(tmp_path: Path) -> None:
    cache = ResultCache(tmp_path, cap_bytes=10**9)
    assert cache.get(_key(1)) is None
    assert cache.put(_key(1), _state()) == 0
    for c in (cache, ResultCache(tmp_path, cap_bytes=10**9)):
        got = c.get(_key(1))
        assert got is not None
        assert got.values == {"note": "x", "n": 100}
        np.testing.assert_array_equal(got.arrays["x"], np.ones(100))
        assert _stored(c) == {1}
        assert c.size_bytes > 800


def test_lru_cap_evicts_least_recently_used_and_never_the_new_entry(tmp_path: Path) -> None:
    cache = ResultCache(tmp_path, cap_bytes=10**9)
    cache.put(_key(1), _state())
    one = cache.size_bytes
    cache = ResultCache(tmp_path, cap_bytes=3 * one)
    cache.put(_key(2), _state())
    cache.put(_key(3), _state())
    assert cache.get(_key(1)) is not None  # 1 is now the most recent, 2 the oldest
    assert cache.put(_key(4), _state()) == one
    assert _stored(cache) == {1, 3, 4}
    assert not _entry(tmp_path, 2).exists()
    assert cache.size_bytes == 3 * one
    # recency survives a reopen (entry.json mtime)
    reopened = ResultCache(tmp_path, cap_bytes=3 * one)
    reopened.put(_key(5), _state())
    assert _stored(reopened) == {1, 4, 5}
    # an entry larger than the cap is kept until the next put
    tiny = ResultCache(tmp_path, cap_bytes=1)
    tiny.put(_key(6), _state())
    assert _stored(tiny) == {6}


@pytest.mark.parametrize("damage", ["flip_npy", "truncate_npy", "delete_npy", "edit_state"])
def test_corrupt_entry_is_discarded_and_recomputed(tmp_path: Path, damage: str) -> None:
    cache = ResultCache(tmp_path, cap_bytes=10**9)
    cache.put(_key(1), _state())
    npy = _entry(tmp_path, 1) / "arrays" / "0.npy"
    if damage == "flip_npy":
        data = bytearray(npy.read_bytes())
        data[-1] ^= 0xFF
        npy.write_bytes(bytes(data))
    elif damage == "truncate_npy":
        npy.write_bytes(npy.read_bytes()[:50])
    elif damage == "delete_npy":
        npy.unlink()
    else:
        state_json = _entry(tmp_path, 1) / "state.json"
        state_json.write_text(state_json.read_text().replace('"x"', '"y"'))
    assert cache.get(_key(1)) is None
    assert _stored(cache) == set()
    assert not _entry(tmp_path, 1).exists()
    assert cache.size_bytes == 0
    cache.put(_key(1), _state(fill=2.0))  # recompute
    assert _x0(cache, 1) == 2.0


def test_open_discards_bad_entries_and_leftovers(tmp_path: Path) -> None:
    cache = ResultCache(tmp_path, cap_bytes=10**9)
    for i in (1, 2, 3, 4):
        cache.put(_key(i), _state())
    (_entry(tmp_path, 1) / "entry.json").write_text("{not json")
    meta = json.loads((_entry(tmp_path, 2) / "entry.json").read_text())
    (_entry(tmp_path, 2) / "entry.json").write_text(json.dumps({**meta, "key": _key(9)}))
    meta = json.loads((_entry(tmp_path, 4) / "entry.json").read_text())
    meta["files"]["../../outside.txt"] = "0" * 64
    (_entry(tmp_path, 4) / "entry.json").write_text(json.dumps(meta))
    (tmp_path / "entries" / "not-a-key").mkdir()
    (tmp_path / "tmp" / "half-written" / "arrays").mkdir(parents=True)
    reopened = ResultCache(tmp_path, cap_bytes=10**9)
    assert _stored(reopened) == {3}
    assert sorted(p.name for p in (tmp_path / "entries").iterdir()) == [f"{3:064x}"]
    assert list((tmp_path / "tmp").iterdir()) == []


def test_put_existing_key_keeps_entry_clear_frees_all_and_bad_keys_raise(tmp_path: Path) -> None:
    cache = ResultCache(tmp_path, cap_bytes=10**9)
    cache.put(_key(1), _state(fill=1.0))
    cache.put(_key(1), _state(fill=5.0))  # same key = same content by construction
    assert _x0(cache, 1) == 1.0
    cache.put(_key(2), _state())
    size = cache.size_bytes
    assert cache.clear() == size
    assert _stored(cache) == set()
    assert cache.size_bytes == 0
    assert list((tmp_path / "entries").iterdir()) == []
    with pytest.raises(ValueError, match="result key"):
        cache.get("res_../../etc")
    with pytest.raises(ValueError, match="cap_bytes"):
        ResultCache(tmp_path, cap_bytes=-1)

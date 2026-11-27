# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/registry.py
"""Block registry: block classes by ``block_id``, with their checked metadata.

``Registry.register`` checks a block class (``Block.metadata``) and stores it;
``Registry.metadata()`` lists every block in the ``GET /blocks`` shape
(DATA_MODEL.md §2.3), sorted by ``block_id``. ``register`` also works as a class
decorator.
"""

from __future__ import annotations

from collections.abc import Iterator

from vibechem_core.block import Block, BlockMeta


class Registry:
    """A set of block classes, unique by ``block_id``."""

    def __init__(self) -> None:
        self._blocks: dict[str, tuple[type[Block], BlockMeta]] = {}

    def register[B: type[Block]](self, block: B) -> B:
        """Check ``block`` and add it; returns the class (usable as a decorator).

        Raises ``ValueError`` if another class already uses the ``block_id``, and the
        ``TypeError``/``ValueError`` of :meth:`Block.metadata` for definition mistakes.
        """
        meta = block.metadata()
        known = self._blocks.get(meta.block_id)
        if known is not None and known[0] is not block:
            raise ValueError(
                f"block_id {meta.block_id!r} is already registered by {known[0].__qualname__}"
            )
        self._blocks[meta.block_id] = (block, meta)
        return block

    def get(self, block_id: str) -> type[Block]:
        """Block class for ``block_id``; ``KeyError`` if unknown."""
        try:
            return self._blocks[block_id][0]
        except KeyError:
            raise KeyError(f"unknown block_id {block_id!r}") from None

    def meta(self, block_id: str) -> BlockMeta:
        """Checked metadata for ``block_id``; ``KeyError`` if unknown."""
        self.get(block_id)
        return self._blocks[block_id][1]

    def block_ids(self) -> tuple[str, ...]:
        """Registered block ids, sorted."""
        return tuple(sorted(self._blocks))

    def metadata(self) -> list[BlockMeta]:
        """Metadata of every registered block, sorted by ``block_id``."""
        return [self._blocks[block_id][1] for block_id in self.block_ids()]

    def __contains__(self, block_id: object) -> bool:
        return block_id in self._blocks

    def __len__(self) -> int:
        return len(self._blocks)

    def __iter__(self) -> Iterator[type[Block]]:
        return (self._blocks[block_id][0] for block_id in self.block_ids())

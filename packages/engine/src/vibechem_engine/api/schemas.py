# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/api/schemas.py
"""pydantic models of the ``GET /blocks/{block_id}`` object (DATA_MODEL.md §2.3, §4.3, §5).

:class:`BlockDetail` is DATA_MODEL.md §5 written as a model: it validates what
``vibechem_core.block.BlockMeta.to_detail_dict()`` produces, and
``BlockDetail.model_json_schema()`` gives its JSON Schema for the API description.
The models only check the shape and the rules inside one object; value validation of
a pipeline's parameters is ``vibechem_core.block.parse_params`` (§5.3).
"""

from __future__ import annotations

import operator
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "BlockDetail",
    "BoolParam",
    "EnumParam",
    "FloatParam",
    "Implementation",
    "InputPort",
    "IntParam",
    "OutputPort",
    "ParamEntry",
    "StringParam",
    "VisibleIf",
]

type Scalar = str | int | float | bool
SnakeId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
Key = Annotated[str, Field(min_length=1)]
Constraint = Annotated[
    str,
    Field(
        pattern=r"^[a-z][a-z0-9_]* (<=|>=|<|>|!=) ([a-z][a-z0-9_]*|-?[0-9]+(\.[0-9]+)?([eE][-+]?[0-9]+)?)$"
    ),
]
_COMPARE = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "!=": operator.ne,
}
PortType = Literal["Spectra", "Table", "Model", "Transform", "Folds", "Results", "ImageCube"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class VisibleIf(_Model):
    """Show the parameter only while ``param_id`` has one of ``values`` (§5.1)."""

    param_id: SnakeId
    values: Annotated[list[Scalar], Field(min_length=1)]


class _Param(_Model):
    param_id: SnakeId
    label_key: Key
    tooltip_key: Key
    advanced: bool
    visible_if: VisibleIf | None = None


class _Number(_Param):
    min: int | float | None = None
    max: int | float | None = None
    unit: Key | None = None
    constraint: Constraint | None = None

    def _check_bounds(self, default: float) -> None:
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError(f"min {self.min} is greater than max {self.max}")
        if (self.min is not None and default < self.min) or (
            self.max is not None and default > self.max
        ):
            raise ValueError(f"default {default} is outside [{self.min}, {self.max}]")
        if self.constraint is not None and not self.constraint.startswith(f"{self.param_id} "):
            raise ValueError(f"constraint {self.constraint!r} must start with {self.param_id!r}")


class IntParam(_Number):
    type: Literal["int"]
    default: int
    odd_only: Literal[True] | None = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        self._check_bounds(self.default)
        if self.odd_only and self.default % 2 == 0:
            raise ValueError(f"default {self.default} is not odd")
        return self


class FloatParam(_Number):
    type: Literal["float"]
    default: float

    @model_validator(mode="after")
    def _check(self) -> Self:
        self._check_bounds(self.default)
        return self


class BoolParam(_Param):
    type: Literal["bool"]
    default: bool


class StringParam(_Param):
    type: Literal["string"]
    default: str


class EnumParam(_Param):
    type: Literal["enum"]
    default: Scalar
    choices: Annotated[list[Scalar], Field(min_length=1)]

    @model_validator(mode="after")
    def _check(self) -> Self:
        float_kind = any(type(c) is float for c in self.choices)
        # JSON has one number type: a client may send the float choice 1.0 as 1.
        kinds = {float if type(c) is int and float_kind else type(c) for c in self.choices}
        if len(kinds) != 1:
            raise ValueError("choices must all be of one kind")
        if not self.allows(self.default):
            raise ValueError(f"default {self.default!r} is not one of the choices")
        if len({(type(c), c) for c in self.choices}) != len(self.choices):
            raise ValueError("choices has duplicates")
        return self

    def allows(self, value: Scalar) -> bool:
        """True if ``value`` is one of the choices (a JSON integer matches a float choice)."""
        numbers = (int, float)
        return any(
            c == value
            and (type(c) is type(value) or (type(c) in numbers and type(value) in numbers))
            for c in self.choices
        )


ParamEntry = Annotated[
    IntParam | FloatParam | BoolParam | EnumParam | StringParam, Field(discriminator="type")
]
"""One entry of ``params`` (§5.1, implemented types of §5.2)."""


class InputPort(_Model):
    port_id: SnakeId
    port_type: PortType
    required: bool
    multiple: bool
    requires: list[Literal["y", "classes", "groups", "spatial"]] | None = None
    rows_match: SnakeId | None = None
    axis_match: SnakeId | None = None
    refit_per_fold: Literal[True] | None = None


class OutputPort(_Model):
    port_id: SnakeId
    port_type: PortType


class Implementation(_Model):
    library: Key
    function: Key


class BlockDetail(_Model):
    """``GET /blocks/{block_id}`` (DATA_MODEL.md §2.3)."""

    block_id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")]
    version: Annotated[str, Field(pattern=r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")]
    block_class: SnakeId
    title_key: Key
    tooltip_key: Key
    icon: Key
    fitted: bool
    tier: Literal["P0", "P1", "P2"]
    inputs: list[InputPort]
    outputs: list[OutputPort]
    params: list[ParamEntry]
    references: list[Key]
    implementation: Implementation
    help_key: Key
    custom_panel: Key | None

    @model_validator(mode="after")
    def _check_params(self) -> Self:
        by_id = {p.param_id: p for p in self.params}
        if len(by_id) != len(self.params):
            raise ValueError("param_id values must be unique")
        for p in self.params:
            if isinstance(p, IntParam | FloatParam) and p.constraint is not None:
                right = p.constraint.rsplit(" ", 1)[1]
                other = by_id.get(right)
                if right[0].isalpha() and (
                    right == p.param_id or not isinstance(other, IntParam | FloatParam)
                ):
                    raise ValueError(f"{p.param_id}: constraint must name another number param")
            if p.visible_if is not None:
                target = by_id.get(p.visible_if.param_id)
                if p.visible_if.param_id == p.param_id or not isinstance(
                    target, BoolParam | EnumParam
                ):
                    raise ValueError(f"{p.param_id}: visible_if must name a bool or enum param")
                for value in p.visible_if.values:
                    valid = (
                        target.allows(value)
                        if isinstance(target, EnumParam)
                        else type(value) is bool
                    )
                    if not valid:
                        raise ValueError(f"{p.param_id}: visible_if value {value!r} is not valid")
        defaults = {p.param_id: p.default for p in self.params}
        for p in self.params:
            if isinstance(p, IntParam | FloatParam) and p.constraint is not None:
                _, op, right = p.constraint.split(" ")
                other = defaults[right] if right[0].isalpha() else float(right)
                if not _COMPARE[op](p.default, other):
                    raise ValueError(f"{p.param_id}: defaults break {p.constraint!r}")
        return self

# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/block.py
"""The block contract (ARCHITECTURE.md §3.1, CLAUDE.md §5).

A block is one class with class-level metadata, typed ports, a frozen dataclass of
parameters and the methods that do the work, following scikit-learn's split between
fitting and applying:

- stateless blocks (``fitted = False``) implement ``apply(<inputs>, params)``;
- fitted blocks (``fitted = True``) implement ``fit(<inputs>, params) -> State`` on
  training rows only and ``apply(<inputs>, params, state)`` on any rows.

Inputs are passed as keyword arguments named after the input ``port_id``\\ s.
``State`` holds JSON values and named NumPy arrays only, so :func:`save_state` and
:func:`load_state` store it as ``state.json`` plus ``.npy`` files, without pickle
(ADR-007).

:meth:`Block.metadata` checks the class definition and returns its ``BlockMeta``, the
``GET /blocks`` entry of DATA_MODEL.md §2.3. Definition mistakes raise
``TypeError``/``ValueError``; errors about user data raise ``vibechem_core.errors``
classes with the codes defined below (DATA_MODEL.md §7, "Defined in core/block").
"""

from __future__ import annotations

import dataclasses
import json
import math
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, ClassVar, Literal, cast

import numpy as np
from numpy.typing import ArrayLike, NDArray

# Error codes defined in this module (DATA_MODEL.md §7). They are raised by the
# run-time input checks of §4.3/§4.5 (``requires``, ``rows_match``, ``axis_match``).
BLOCK_INPUT_REQUIREMENT_MISSING = "BLOCK_INPUT_REQUIREMENT_MISSING"
BLOCK_INPUT_ROWS_MISMATCH = "BLOCK_INPUT_ROWS_MISMATCH"
BLOCK_INPUT_AXIS_MISMATCH = "BLOCK_INPUT_AXIS_MISMATCH"

PORT_TYPES = frozenset({"Spectra", "Table", "Model", "Transform", "Folds", "Results", "ImageCube"})
"""Port type names of DATA_MODEL.md §4.1."""
REQUIREMENTS = frozenset({"y", "classes", "groups", "spatial"})
"""Values allowed in an input port's ``requires`` (DATA_MODEL.md §4.3)."""
TIERS = ("P0", "P1", "P2")
"""Priority tiers of FUNCTION_CATALOG.md."""

_SNAKE = re.compile(r"[a-z][a-z0-9_]*")
_BLOCK_ID = re.compile(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+")
_SEMVER = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")
_PARAM_SPEC = "vibechem_param"  # key of the ParamSpec in a dataclass field's metadata

type ParamValue = str | int | float | bool | None
type JSONValue = str | int | float | bool | list[JSONValue] | dict[str, JSONValue] | None


# ---- Parameters ---------------------------------------------------------------------


@dataclass(frozen=True)
class ParamSpec:
    """What ``Param`` records about one parameter (the schema export is T1.03)."""

    default: ParamValue
    choices: tuple[ParamValue, ...] | None = None
    min: float | None = None
    max: float | None = None
    label_key: str | None = None
    tooltip_key: str | None = None
    advanced: bool = False


def Param[T: ParamValue](
    default: T,
    *,
    choices: tuple[T, ...] | None = None,
    min: float | None = None,
    max: float | None = None,
    label_key: str | None = None,
    tooltip_key: str | None = None,
    advanced: bool = False,
) -> T:
    """Declare a block parameter as a field of the block's frozen params dataclass.

    ``ddof: int = Param(1, choices=(0, 1))`` gives the field the default ``1`` and
    records the ``ParamSpec`` in the field's metadata.
    """
    for label, bound in (("default", default), ("min", min), ("max", max)):
        if isinstance(bound, float) and not math.isfinite(bound):
            raise ValueError(f"{label} must be finite, got {bound}")
    if choices is not None and not any(type(c) is type(default) and c == default for c in choices):
        raise ValueError(f"default {default!r} is not one of the choices {choices!r}")
    if min is not None and max is not None and min > max:
        raise ValueError(f"min {min} is greater than max {max}")
    number = default if isinstance(default, int | float) and not isinstance(default, bool) else None
    if number is not None and (
        (min is not None and number < min) or (max is not None and number > max)
    ):
        raise ValueError(f"default {default} is outside [{min}, {max}]")
    spec = ParamSpec(default, choices, min, max, label_key, tooltip_key, advanced)
    return cast(T, field(default=default, metadata={_PARAM_SPEC: spec}))


@dataclass(frozen=True)
class NoParams:
    """Params type of a block without parameters."""


def param_specs(params_type: type) -> tuple[tuple[str, ParamSpec], ...]:
    """``(name, ParamSpec)`` for every field of a params dataclass, in field order.

    Raises ``TypeError`` if ``params_type`` is not a frozen dataclass or a field was not
    declared with ``Param``.
    """
    label = params_type.__name__
    params = getattr(params_type, "__dataclass_params__", None)
    if not dataclasses.is_dataclass(params_type) or not getattr(params, "frozen", False):
        raise TypeError(f"{label} must be a frozen dataclass")
    specs: list[tuple[str, ParamSpec]] = []
    for f in dataclasses.fields(params_type):
        spec = f.metadata.get(_PARAM_SPEC)
        if not isinstance(spec, ParamSpec):
            raise TypeError(f"{label}.{f.name} must be declared with Param(...)")
        specs.append((f.name, spec))
    return tuple(specs)


# ---- Ports --------------------------------------------------------------------------


@dataclass(frozen=True)
class Port:
    """A named, typed input or output of a block (DATA_MODEL.md §4.3)."""

    port_id: str
    port_type: str
    required: bool = True
    multiple: bool = False
    requires: tuple[str, ...] = ()
    rows_match: str | None = None
    axis_match: str | None = None
    refit_per_fold: bool = False

    def __post_init__(self) -> None:
        if not _SNAKE.fullmatch(self.port_id):
            raise ValueError(f"port_id {self.port_id!r} must be snake_case")
        if self.port_type not in PORT_TYPES:
            raise ValueError(f"unknown port type {self.port_type!r}; one of {sorted(PORT_TYPES)}")
        unknown = set(self.requires) - REQUIREMENTS
        if unknown:
            raise ValueError(f"unknown requires {sorted(unknown)}; one of {sorted(REQUIREMENTS)}")
        if self.refit_per_fold and self.port_type not in ("Model", "Transform"):
            raise ValueError("refit_per_fold is only allowed on Model or Transform inputs")

    @property
    def is_plain(self) -> bool:
        """True when only ``port_id`` and ``port_type`` are set (required of outputs)."""
        return self == Port(self.port_id, self.port_type)

    def to_dict(self, direction: Literal["input", "output"]) -> dict[str, JSONValue]:
        """Port declaration as in ``GET /blocks`` (optional input fields only when set)."""
        out: dict[str, JSONValue] = {"port_id": self.port_id, "port_type": self.port_type}
        if direction == "output":
            return out
        out |= {"required": self.required, "multiple": self.multiple}
        if self.requires:
            out["requires"] = list(self.requires)
        if self.rows_match is not None:
            out["rows_match"] = self.rows_match
        if self.axis_match is not None:
            out["axis_match"] = self.axis_match
        if self.refit_per_fold:
            out["refit_per_fold"] = True
        return out


def port(
    port_id: str,
    port_type: str,
    *,
    required: bool = True,
    multiple: bool = False,
    requires: tuple[str, ...] = (),
    rows_match: str | None = None,
    axis_match: str | None = None,
    refit_per_fold: bool = False,
) -> Port:
    """Declare a port: ``inputs = (port("spectra", "Spectra"),)``."""
    return Port(
        port_id, port_type, required, multiple, requires, rows_match, axis_match, refit_per_fold
    )


# ---- Fitted state -------------------------------------------------------------------


@dataclass(frozen=True, eq=False)
class State:
    """Fitted state of a block: JSON values plus named arrays, never a Python object.

    ``values`` must be JSON (str, finite int/float, bool, None, lists, dicts with str
    keys) and are deep-copied; arrays are stored as private read-only copies; both
    mappings are read-only. A state can be sent to a worker process (pickled in memory
    only, ADR-007); it is never saved with pickle.
    """

    values: Mapping[str, JSONValue]
    arrays: Mapping[str, NDArray[Any]]

    def __init__(
        self,
        values: Mapping[str, object] | None = None,
        arrays: Mapping[str, ArrayLike] | None = None,
    ) -> None:
        frozen: dict[str, NDArray[Any]] = {}
        for name, value in (arrays or {}).items():
            array = np.array(value)
            if array.dtype.hasobject:
                raise TypeError(f"state array {name!r} has dtype object (not saveable, ADR-007)")
            array.flags.writeable = False
            frozen[name] = array
        copied = {str(k): _json_copy(v, k) for k, v in (values or {}).items()}
        object.__setattr__(self, "values", MappingProxyType(copied))
        object.__setattr__(self, "arrays", MappingProxyType(frozen))

    def __reduce__(self) -> tuple[type[State], tuple[dict[str, JSONValue], dict[str, Any]]]:
        return (State, (dict(self.values), dict(self.arrays)))


def _json_copy(value: object, path: str) -> JSONValue:
    """Deep copy of a JSON value; ``TypeError`` for anything else (ADR-007)."""
    if value is None or isinstance(value, str | bool | int):
        return cast(JSONValue, value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError(f"state value {path!r} is not finite (not JSON)")
        return float(value)
    if isinstance(value, list | tuple):
        items = cast(list[object] | tuple[object, ...], value)
        return [_json_copy(v, f"{path}[{i}]") for i, v in enumerate(items)]
    if isinstance(value, dict):
        entries = cast(dict[object, object], value)
        if not all(isinstance(k, str) for k in entries):
            raise TypeError(f"state value {path!r} has non-string keys (not JSON)")
        return {str(k): _json_copy(v, f"{path}.{k}") for k, v in entries.items()}
    raise TypeError(
        f"state value {path!r} is a {type(value).__name__}, not JSON; store arrays in "
        "State.arrays and convert NumPy scalars with .item() (ADR-007)"
    )


STATE_VERSION = 1
"""Version of the state directory layout written by :func:`save_state`."""
_STATE_KEYS = {"state_version", "values", "arrays"}


def save_state(state: State, directory: str | os.PathLike[str]) -> None:
    """Save ``state`` into ``directory`` (created if missing) as JSON + ``.npy``.

    Layout (ADR-007): ``state.json`` = ``{"state_version": 1, "values": {...},
    "arrays": [name, ...]}`` and ``arrays/<i>.npy`` for the i-th name. Files are
    named by position, so array names never become file names.
    """
    root = Path(directory)
    (root / "arrays").mkdir(parents=True, exist_ok=True)
    names = [str(name) for name in state.arrays]
    for i, array in enumerate(state.arrays.values()):
        np.save(root / "arrays" / f"{i}.npy", array, allow_pickle=False)
    doc = {"state_version": STATE_VERSION, "values": dict(state.values), "arrays": names}
    text = json.dumps(doc, allow_nan=False, ensure_ascii=False, indent=1)
    (root / "state.json").write_text(text, encoding="utf-8")


def load_state(directory: str | os.PathLike[str]) -> State:
    """Load a state saved by :func:`save_state`; arrays use ``allow_pickle=False``.

    Raises ``FileNotFoundError`` for a missing file and ``ValueError`` for invalid
    content (the engine maps it to ``MODEL_PACKAGE_INVALID``, DATA_MODEL.md §7).
    """
    root = Path(directory)
    text = (root / "state.json").read_text(encoding="utf-8")
    try:
        doc: object = json.loads(text, parse_constant=_reject_constant)
    except json.JSONDecodeError as exc:
        raise ValueError(f"state.json is not valid JSON: {exc}") from None
    problem = _state_doc_problem(doc)
    if problem:
        raise ValueError(f"state.json {problem}")
    entries = cast(dict[str, Any], doc)
    arrays: dict[str, NDArray[Any]] = {}
    for i, name in enumerate(cast(list[str], entries["arrays"])):
        loaded: object = np.load(root / "arrays" / f"{i}.npy", allow_pickle=False)
        if isinstance(loaded, np.ndarray):
            arrays[name] = cast(NDArray[Any], loaded)
            continue
        if hasattr(loaded, "close"):  # an .npz archive keeps its file open
            cast(Any, loaded).close()
        raise ValueError(f"arrays/{i}.npy is not a .npy array (state array {name!r})")
    return State(cast(dict[str, object], entries["values"]), arrays)


def _state_doc_problem(doc: object) -> str | None:
    """What is wrong with a parsed ``state.json``, or ``None``."""
    if not isinstance(doc, dict):
        return "must be a JSON object"
    entries = cast(dict[str, object], doc)
    if set(entries) - _STATE_KEYS:
        return f"has unknown keys {sorted(set(entries) - _STATE_KEYS)}"
    version, values, names = (entries.get(k) for k in ("state_version", "values", "arrays"))
    if version != STATE_VERSION or isinstance(version, bool):
        return f"has state_version {version!r}; expected {STATE_VERSION}"
    if not isinstance(values, dict):
        return "'values' must be an object"
    if not isinstance(names, list) or not all(
        isinstance(n, str) for n in cast(list[object], names)
    ):
        return "'arrays' must be a list of str"
    array_names = cast(list[str], names)
    if len(set(array_names)) != len(array_names):
        return f"'arrays' has duplicate names {array_names}"
    return None


def _reject_constant(constant: str) -> object:
    raise ValueError(f"state.json value {constant} is not JSON (not finite)")


# ---- Block --------------------------------------------------------------------------


@dataclass(frozen=True)
class BlockMeta:
    """Checked metadata of a block class; :meth:`to_dict` is its ``GET /blocks`` entry."""

    block_id: str
    version: str
    block_class: str
    icon: str
    fitted: bool
    tier: str
    references: tuple[str, ...]
    inputs: tuple[Port, ...]
    outputs: tuple[Port, ...]
    params: tuple[tuple[str, ParamSpec], ...]

    @property
    def title_key(self) -> str:
        return f"blocks.{self.block_id}.title"

    @property
    def tooltip_key(self) -> str:
        return f"blocks.{self.block_id}.tip"

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "block_id": self.block_id,
            "version": self.version,
            "block_class": self.block_class,
            "title_key": self.title_key,
            "tooltip_key": self.tooltip_key,
            "icon": self.icon,
            "fitted": self.fitted,
            "tier": self.tier,
            "inputs": [p.to_dict("input") for p in self.inputs],
            "outputs": [p.to_dict("output") for p in self.outputs],
        }


class Block:
    """Base class of every block. Subclasses set the class attributes below.

    ``block_class`` defaults to the first segment of ``block_id`` and ``tier`` to
    ``"P0"``.
    """

    block_id: ClassVar[str]
    version: ClassVar[str]
    icon: ClassVar[str]
    fitted: ClassVar[bool]
    inputs: ClassVar[tuple[Port, ...]]
    outputs: ClassVar[tuple[Port, ...]]
    references: ClassVar[tuple[str, ...]] = ()
    params_type: ClassVar[type] = NoParams
    block_class: ClassVar[str | None] = None
    tier: ClassVar[str] = "P0"

    # The engine calls these with the inputs as keyword arguments (one per port_id),
    # so the base signatures are open; each block declares its own typed signature.
    def fit(self, *args: Any, **kwargs: Any) -> State:
        """Fit on training rows and return the state (fitted blocks only)."""
        raise NotImplementedError(f"{type(self).__name__} does not implement fit")

    def apply(self, *args: Any, **kwargs: Any) -> Any:
        """Transform inputs into outputs (fitted blocks also receive ``state``)."""
        raise NotImplementedError(f"{type(self).__name__} does not implement apply")

    @classmethod
    def metadata(cls) -> BlockMeta:
        """Check the class definition and return its metadata.

        Raises ``TypeError``/``ValueError`` describing the first definition mistake.
        """
        name = cls.__name__
        for attr in ("block_id", "version", "icon", "fitted", "inputs", "outputs"):
            if not hasattr(cls, attr):
                raise TypeError(f"{name} must define {attr}")
        # Read as plain objects: subclasses may set any value; this is where it is checked.
        raw: dict[str, object] = {
            a: getattr(cls, a)
            for a in ("block_id", "version", "icon", "fitted", "references", "block_class")
        }
        block_id, version, icon = raw["block_id"], raw["version"], raw["icon"]
        if not isinstance(block_id, str) or not _BLOCK_ID.fullmatch(block_id):
            raise ValueError(f"{name}.block_id {block_id!r} must look like 'class.name'")
        if not isinstance(version, str) or not _SEMVER.fullmatch(version):
            raise ValueError(f"{name}.version {version!r} must be a semantic version x.y.z")
        if not isinstance(icon, str) or not icon:
            raise ValueError(f"{name}.icon must be a non-empty string")
        if not isinstance(raw["fitted"], bool):
            raise TypeError(f"{name}.fitted must be a bool")
        if cls.tier not in TIERS:
            raise ValueError(f"{name}.tier {cls.tier!r} must be one of {TIERS}")
        block_class = raw["block_class"]
        if block_class is None:
            block_class = block_id.partition(".")[0]
        if not isinstance(block_class, str) or not _SNAKE.fullmatch(block_class):
            raise ValueError(f"{name}.block_class {block_class!r} must be snake_case")
        references = raw["references"]
        if not isinstance(references, tuple) or not all(
            isinstance(r, str) and r for r in cast(tuple[object, ...], references)
        ):
            raise TypeError(f"{name}.references must be a tuple of non-empty strings")
        _check_ports(name, cls.inputs, cls.outputs)
        if cls.apply is Block.apply:
            raise TypeError(f"{name} must implement apply")
        if cls.fitted != (cls.fit is not Block.fit):
            raise TypeError(f"{name}: fit must be implemented exactly when fitted = True")
        return BlockMeta(
            block_id=cls.block_id,
            version=cls.version,
            block_class=block_class,
            icon=cls.icon,
            fitted=cls.fitted,
            tier=cls.tier,
            references=cls.references,
            inputs=cls.inputs,
            outputs=cls.outputs,
            params=param_specs(cls.params_type),
        )


def _check_ports(name: str, inputs: object, outputs: object) -> None:
    for label, ports in (("inputs", inputs), ("outputs", outputs)):
        if not isinstance(ports, tuple) or not all(
            isinstance(p, Port) for p in cast(tuple[object, ...], ports)
        ):
            raise TypeError(f"{name}.{label} must be a tuple of port(...) declarations")
        ids = [p.port_id for p in cast(tuple[Port, ...], ports)]
        if len(set(ids)) != len(ids):
            raise ValueError(f"{name}.{label} has duplicate port_ids {ids}")
    input_ports = cast(tuple[Port, ...], inputs)
    single = {p.port_id for p in input_ports if not p.multiple}
    for p in input_ports:
        for other in (p.rows_match, p.axis_match):
            if other is not None and (other == p.port_id or other not in single):
                raise ValueError(
                    f"{name}: input {p.port_id!r} must match another single input, not {other!r}"
                )
    for p in cast(tuple[Port, ...], outputs):
        if not p.is_plain:
            raise ValueError(f"{name}: output {p.port_id!r} may only set port_id and port_type")

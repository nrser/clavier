from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Optional, Protocol, TypeVar
from pathlib import Path

from clavier.cfg.key import Key
from clavier.etc.read_only_mapping import ReadOnlyMapping

TValue = TypeVar("TValue")
TMeta = Mapping[str, Any]
TOp = Literal["add", "del", "set"]


@dataclass(frozen=True)
class Change:
    @classmethod
    def from_value(cls, value: Any) -> Change:
        if isinstance(value, cls):
            return value
        return cls(op="set", value=value)

    op: TOp
    value: Any


class Layer(Protocol):
    """
    Interface for sources of configuration values.
    """

    changes: Mapping[Key, Change]
    meta: Mapping[str, Any]

    @property
    def src(self) -> str:
        return str(self.meta.get("src", "unknown"))


class Update(Layer):
    _changes: Mapping[Key, Change]
    _meta: Mapping[str, Any]

    def __init__(self, changes, meta):
        self._changes = ReadOnlyMapping(
            {key: Change.from_value(value) for key, value in changes.items()}
        )
        self._meta = ReadOnlyMapping({**meta})

    @property
    def changes(self) -> Mapping[Key, Change]:
        return self._changes

    @property
    def meta(self) -> Mapping[str, Any]:
        return self._meta

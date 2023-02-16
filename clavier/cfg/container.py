from __future__ import annotations
from dataclasses import dataclass
from typing import (
    Any,
    Mapping,
    MutableMapping,
    ParamSpec,
    TypeVar,
)
from collections.abc import Iterable
from types import MappingProxyType

from rich.repr import RichReprResult

from sortedcontainers import SortedDict

from .key import Key, KeyMatter
from .changeset import Changeset
from .config import Config, MutableConfig

TParams = ParamSpec("TParams")
TReturn = TypeVar("TReturn")
T = TypeVar("T")

EMPTY_META: Mapping[str, Any] = MappingProxyType({})


@dataclass(frozen=True)
class Update:
    changes: dict[Key, Any]
    meta: dict[str, Any]


class Container(MutableConfig):
    _meta: Mapping[str, Any]
    _parent: Config | None
    _updates: list[Update]
    _view: MutableMapping[Key, Any]

    def __init__(self, parent: Config | None = None, **meta):
        self._parent = parent
        self._meta = meta
        self._updates = []
        self._view = SortedDict()

    def _get_parent_(self) -> Config | None:
        return self._parent

    def _own_keys_(self) -> Iterable[Key]:
        return self._view.keys()

    def _has_own_(self, key: Key) -> bool:
        return key in self._view

    def _get_own_(self, key: Key) -> Any:
        return self._view[key]

    def _description_(self) -> str:
        if meta := self._meta:
            return "{}({})".format(
                super()._description_(),
                ", ".join(f"{k}={v}" for k, v in meta.items()),
            )

        if name := self._name:
            return "{}{}".format(super()._description_(), name)
        return super()._description_()

    def changeset(self, *prefix: KeyMatter, **meta: Any) -> Changeset:
        return Changeset(self, prefix, meta)

    def commit(self, changeset: Changeset) -> None:
        self._view.update(changeset.changes)
        self._updates.append(
            Update(changes={**changeset.changes}, meta={**changeset.meta})
        )

    def configure(self, *prefix: KeyMatter, **meta: Any) -> Changeset:
        return self.changeset(*prefix, **meta)

    def configure_root(self, package: str, **meta: Any) -> Changeset:
        return self.configure(Key(package).root, **meta)

    def __rich_repr__(self) -> RichReprResult:
        yield "meta", self._meta
        yield "parent", self._parent
        yield "updates", self._updates

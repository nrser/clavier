from __future__ import annotations
from collections import namedtuple
from dataclasses import dataclass
from typing import (
    Any,
    MutableMapping,
    ParamSpec,
    TypeVar,
)
from collections.abc import Iterable
from rich.repr import RichReprResult

from sortedcontainers import SortedDict

from .key import Key, KeyMatter
from .scope import WriteScope
from .changeset import Changeset
from .config import Config, MutableConfig

TParams = ParamSpec("TParams")
TReturn = TypeVar("TReturn")
T = TypeVar("T")


@dataclass(frozen=True)
class Update:
    changes: dict[Key, Any]
    meta: dict[str, Any]


class Container(MutableConfig):
    _parent: Config | None
    _updates: list[Update]
    _view: MutableMapping[Key, Any]

    def __init__(self, parent: Config | None = None):
        self._parent = parent
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
        yield "parent", self._parent
        yield "updates", self._updates

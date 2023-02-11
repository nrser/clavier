from __future__ import annotations
from typing import Any
from collections.abc import Mapping, Iterable

from .key import Key, KeyMatter
from .scope import MutableScope
from .config import Config, MutableConfig


class Changeset(Config):
    """
    A runtime object used to create a `Config.Update` in Python code. This is
    what is used under-the-hood when configuring in a source file.

    You don't use this class directly; it's an intermediary between the
    `Config` and various `WriteScope` instances that are used to set values.

    Intended use:

    ```python
    >>> from clavier import CFG
    >>> with CFG.configure("stats.doctest", src=__file__) as c:
    ...     c.x = "ex"
    ...     c.y = "why?"
    ...
    >>> CFG.stats.doctest.x
    'ex'
    >>> CFG.stats.doctest.y
    'why?'

    ```

    In that example, `c` is a `WriteScope` with `._key` of
    `Key("stats", "doctests")`. `c._base` is the internal `Changeset`, which
    references back to the `Config` via `c._base.config`.
    """

    prefix: Key
    _parent: MutableConfig
    changes: dict[Key, Any]
    meta: Mapping[str, Any]

    def __init__(
        self,
        parent: MutableConfig,
        prefix: KeyMatter,
        meta: Mapping[str, Any],
    ):
        self._parent = parent
        self.prefix = Key(prefix)
        self.meta = meta
        self.changes = {}

    def _get_parent_(self) -> Config | None:
        return self._parent

    def _own_keys_(self) -> Iterable[Key]:
        return self.changes.keys()

    def _has_own_(self, key: Key) -> bool:
        return key in self.changes

    def _get_own_(self, key: Key) -> Any:
        return self.changes[key]

    def __setitem__(self, key: KeyMatter, value: Any) -> None:
        key = Key(key)

        if key.is_empty():
            raise KeyError(
                f"Can not set value for empty key; value: {repr(value)}"
            )

        # TODO  Make sure we're not trashing any keys / scopes of the parent!

        # Items are always set in the changes
        self.changes[key] = value

    def __enter__(self) -> MutableScope:
        return MutableScope(parent=self, key=self.prefix)

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if exc_type is None and exc_value is None and traceback is None:
            self._parent.commit(self)

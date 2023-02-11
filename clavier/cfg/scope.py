from __future__ import annotations
from typing import Any, TYPE_CHECKING, TypeVar, Union
from collections.abc import Iterable

from rich.repr import RichReprResult

from .key import Key, KeyMatter
from .config import Config, MutableConfig

if TYPE_CHECKING:
    from .changeset import Changeset


class Scope(Config):
    """\
    A small adapter providing read access to a particular scope of a Config.
    """

    _parent: Config
    _key: Key

    def __init__(self, parent: Config, key: Key):
        object.__setattr__(self, "_parent", parent)
        object.__setattr__(self, "_key", key)

    def _get_parent_(self) -> Config | None:
        return self._parent

    def _own_keys_(self) -> Iterable[Key]:
        return ()

    def _has_own_(self, key: Key) -> bool:
        return False

    def _get_own_(self, key: Key) -> Any:
        raise KeyError("ReadScope does not own any keys")

    def _own_scopes_(self) -> set[Key]:
        return set()

    def _has_own_scope_(self, scope: Key) -> bool:
        return False

    def _as_key_(self, key_matter: KeyMatter) -> Key:
        return Key(self._key, key_matter)

    def to_dict(self) -> dict[str, Any]:
        from .config import Config

        if not isinstance(self._base, Config):
            raise TypeError(
                "`to_dict` only works when base is a Config (it's a {})".format(
                    type(self._base)
                )
            )

        prefix = str(self._key) + Key.STRING_SEPARATOR
        dct = {}
        for key, value in self._base.to_dict().items():
            if key.startswith(prefix):
                dct[key.removeprefix(prefix)] = value
        return dct

    def __rich_repr__(self) -> RichReprResult:
        # yield "base", self._base
        # NOTE  Can't just yield a Key, 'cause it's a tuple?
        yield str(self._key)


TMutableScope = TypeVar("TMutableScope", bound="MutableScope")


class MutableScope(Scope):
    """\
    A scope adapter that funnels writes through to a `Changeset` (in addition
    to facilitating scoped reads).
    """

    _parent: "Changeset"

    def __init__(self, parent: "Changeset", key: Key):
        super().__init__(parent, key)

    def __setitem__(self, key: KeyMatter, value: Any) -> None:
        self._parent[self._as_key_(key)] = value

    def __setattr__(self, name: str, value: Any) -> None:
        self._parent[self._as_key_(name)] = value

    def __enter__(self) -> MutableScope:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        pass

    def configure(
        self: TMutableScope, *prefix: KeyMatter, **meta: Any
    ) -> TMutableScope:
        return self.__class__(parent=self._parent, key=self._as_key_(prefix))

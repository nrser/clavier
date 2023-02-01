from __future__ import annotations
from typing import Any, TYPE_CHECKING, Union

from rich.repr import RichReprResult

from .key import Key

if TYPE_CHECKING:
    from .config import Config
    from .changeset import Changeset


class ReadScope:
    """\
    A small adapter providing read access to a particular scope of a Config.
    """

    _base: Union["Config", "Changeset"]
    _key: Key

    def __init__(self, base, key):
        object.__setattr__(self, "_base", base)
        object.__setattr__(self, "_key", Key(key))

    def __contains__(self, name: Any) -> bool:
        try:
            return Key(self._key, name) in self._base
        except Exception:
            return False

    def __getattr__(self, name: str) -> Any:
        try:
            return self._base[Key(self._key, name)]
        except AttributeError as error:
            raise error
        except Exception as error:
            raise AttributeError(
                f"`{self.__class__.__name__}` has no attribute {repr(name)}"
            ) from error

    def __getitem__(self, key: Any) -> Any:
        try:
            return self._base[Key(self._key, key)]
        except KeyError as error:
            raise error
        except Exception as error:
            raise KeyError(
                f"`{self.__class__.__name__}` has no key {repr(key)}"
            ) from error

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


class WriteScope(ReadScope):
    """\
    A scope adapter that funnels writes through to a `Changeset` (in addition
    to facilitating scoped reads).
    """

    _base: "Changeset"

    def __setattr__(self, name: str, value: Any) -> None:
        self._base[Key(self._key, name)] = value

    __setitem__ = __setattr__

    def __enter__(self) -> WriteScope:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        pass

    def configure(self, *key: str, **meta):
        return self.__class__(base=self._base, key=Key(self._key, key))

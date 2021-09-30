from __future__ import annotations
from typing import (
    Any,
)

from .key import Key


class ReadScope:
    """\
    A small adapter providing read access to a particular scope of a Config.
    """

    def __init__(self, base, key):
        super().__setattr__("_base", base)
        super().__setattr__("_key", Key(key))

    def __contains__(self, key: Any) -> bool:
        return key in self._base

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


class WriteScope(ReadScope):
    """\
    A scope adapter that funnels writes through to a `Changeset` (in addition
    to facilitating scoped reads).
    """

    def __setattr__(self, name: str, value: Any) -> None:
        self._base[Key(self._key, name)] = value

    __setitem__ = __setattr__

    def __enter__(self) -> WriteScope:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        pass

    def configure(self, *key: str, **meta):
        return self.__class__(base=self._base, key=Key(self._key, key))

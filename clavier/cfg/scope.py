from __future__ import annotations
from typing import (
    Any,
    Dict,
    Generator,
    Iterable,
    Iterator,
    Mapping,
    Tuple,
)

from sortedcontainers.sorteddict import SortedDict

from clavier.cfg.config import Config, ValueState
from clavier.etc.coll import bury

from .key import Key


class ReadScope(Config):
    """\
    A small adapter providing read access to a particular scope of a Config.
    """

    _base: Config
    _key: Key

    def __init__(self, base, key):
        super().__setattr__("_base", base)
        super().__setattr__("_key", Key(key))

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

    def __len__(self) -> int:
        return sum(1 for _ in self.keys())

    def items(self) -> Iterable[Tuple[Key, Any]]:
        for key in self.keys():
            yield (key, self[key])

    def keys(self) -> Generator[Key, None, None]:
        """
        >>> config = Root()
        >>> with config.configure("package_a") as package_a:
        ...     package_a.x = "AX"
        ...     package_a.y = "AY"
        >>> with config.configure("package_b") as b:
        ...     b.z = "BZ"
        ...     b.w = "BW"
        >>> package_a_scope = config.package_a
        >>> list(package_a_scope)
        [Key('x'), Key('y')]
        """
        for key in self._base:
            if key != self._key and key.starts_with(self._key):
                yield key[len(self._key) :]

    __iter__ = keys

    def values(self) -> Generator[Any, None, None]:
        for key in self.keys():
            yield self[key]

    def view(self) -> Mapping[Key, ValueState]:
        dct = SortedDict()
        for key, value_state in self._base.view().items():
            if key != self._key and key.starts_with(self._key):
                dct[key[len(self._key) :]] = value_state
        return dct

    def to_dict(self, *, deep: bool = False) -> Dict[str, Any]:
        if deep:
            dct = {}
            for key, value in self.items():
                bury(dct, key, value)
            return dct
        return {str(key): value for key, value in self.items()}


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


if __name__ == "__main__":
    from clavier.cfg.root import Root
    import doctest

    doctest.testmod()

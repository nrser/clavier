# from collections.abc import Mapping as AbstractMapping
from typing import (
    Any,
    # Generic,
    Iterable,
    Iterator,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Mapping,
    Union,
    cast,
)

from clavier.err import ArgTypeError

TKey = TypeVar("TKey")
TValue = TypeVar("TValue")
TDefault = TypeVar("TDefault")


class ReadOnlyMapping(Mapping[TKey, TValue]):
    """A `typing.Mapping` that wraps around another `typing.Mapping` (such as a
    `builtin.dict`) and only offers read methods.

    >>> rom = ReadOnlyMapping({"a": 1, "b": 2})
    >>> rom["a"]
    1
    >>> rom["b"]
    2
    >>> "c" in rom
    False
    >>> rom["c"] = 3
    Traceback (most recent call last):
        ...
    TypeError: 'ReadOnlyMapping' object does not support item assignment
    """

    __slots__ = ("_mapping",)

    _mapping: Mapping[TKey, TValue]

    def __init__(
        self, mapping: Optional[Mapping[TKey, TValue]] = None, **splat: TValue
    ):
        if mapping is None:
            # NOTE  In the case when `**splat` is used then `TKey` is
            # constrained to be `str`, but I don't know how to make `mypy`
            # figure this out (if it even can).
            self._mapping = cast(Mapping[TKey, TValue], splat)
        else:
            if len(splat) > 0:
                raise TypeError(
                    "Must give a single positional argument OR keyword "
                    + "arguments, received BOTH"
                )
            if not isinstance(mapping, Mapping):
                raise ArgTypeError("mapping", Mapping, mapping)
            self._mapping = mapping

    def __contains__(self, key):
        return key in self._mapping

    def __getitem__(self, key):
        return self._mapping[key]

    def __iter__(self):
        return iter(self._mapping)

    def __len__(self) -> int:
        return len(self._mapping)

    def __eq__(self, other: Any):
        return self._mapping == other

    def get(self, key, default=None):
        return self._mapping.get(key, default)

    def items(self):
        return self._mapping.items()

    def keys(self):
        return self._mapping.keys()

    def values(self):
        return self._mapping.values()


if __name__ == "__main__":
    import doctest

    doctest.testmod()

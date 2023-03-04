"""Operating primarily on `typing.Iterable` objects."""

from typing import (
    TypeGuard,
    TypeVar,
    Any,
    Callable,
    Iterable,
    overload,
)

from splatlog.lib.collections import find
from more_itertools import intersperse

T = TypeVar("T")
V = TypeVar("V")


def interspersed(separator: V, iterable: Iterable[T]) -> list[T | V]:
    """Just `intersperse`, but converts the result to a `list` for you (instead
    of a generator).

    >>> list(intersperse('and', [1, 2, 3]))
    [1, 'and', 2, 'and', 3]
    """
    return list(intersperse(separator, iterable))


@overload
def filtered(predicate: Callable[[T], Any], iterable: Iterable[T]) -> list[T]:
    ...


@overload
def filtered(
    predicate: Callable[[T], TypeGuard[V]],
    iterable: Iterable[T],
) -> list[V]:
    ...


def filtered(predicate, iterable):
    return list(filter(predicate, iterable))

"""\
Operating primarily on `typing.Iterable` objects.
"""

from typing import (
    Generator,
    TypeVar,
    Union,
    Literal,
    NewType,
    Any,
    Callable,
    Iterable,
    overload,
    Optional,
    Container,
    List,
)

from .type import Null, is_null

K = TypeVar("K")
T = TypeVar("T")
V = TypeVar("V")

TItem = TypeVar("TItem")
TNotFound = TypeVar("TNotFound")
TResult = TypeVar("TResult")
TKey = TypeVar("TKey")
TValue = TypeVar("TValue")
TAlias = TypeVar("TAlias")

# Used to as the type variables for arguments that are used as identify null
# results returned from given functions.
#
# We generally consider exactly `None` and `False` to indicate null results —
# see `.type.Null` and `.type.is_null` — but optionally defer control to the
# caller where we can.
#
TNullResult = TypeVar("TNullResult")

@overload
def find(
    predicate: Callable[[TItem], Any],
    itr: Iterable[TItem],
    not_found: TNotFound,
) -> Union[TItem, TNotFound]:
    pass


@overload
def find(
    predicate: Callable[[TItem], Any], itr: Iterable[TItem]
) -> Optional[TItem]:
    pass


def find(predicate, itr, not_found=None):
    """Return the first item in an iterator `itr` for which `predicate`
    returns anything other than `False` or `None`.

    >>> find(lambda x: x % 2 == 0, (1, 2, 3, 4))
    2

    If `predicate` returns `False` or `None` for **all** items in `itr` then
    `not_found` is returned, which defaults to `None`.

    >>> find(lambda p: Path(p).exists(), ('./a/b', './c/d'), '/dev/null')
    '/dev/null'

    Notes that this diverges from Python's "truthy" behavior, where things like
    empty lists and the number zero are "false". That (obviously) got in the way
    of finding objects like those. I think this approach is a lot more clear,
    if a bit more work to explain.

    Allows this to work, for example:

    >>> find(lambda lst: len(lst) == 0, ([1, 2], [], [3, 4, 5]))
    []
    """
    for item in itr:
        if not is_null(predicate(item)):
            return item
    return not_found


@overload
def find_map(
    fn: Callable[[TItem], Union[TResult, Null]],
    itr: Iterable[TItem],
) -> Optional[TResult]:
    pass


@overload
def find_map(
    fn: Callable[[TItem], Union[TResult, Null]],
    itr: Iterable[TItem],
    not_found: TNotFound,
) -> Union[TResult, TNotFound]:
    pass


@overload
def find_map(
    fn: Callable[[TItem], Union[TResult, TNullResult]],
    itr: Iterable[TItem],
    nothing: Container[TNullResult],
) -> Optional[TResult]:
    pass


@overload
def find_map(
    fn: Callable[[TItem], Union[TResult, TNullResult]],
    itr: Iterable[TItem],
    not_found: TNotFound,
    nothing: Container[TNullResult],
) -> Union[TResult, TNotFound]:
    pass


def find_map(
    fn,
    itr,
    not_found=None,
    nothing=(None, False),
):
    """\
    Like `find()`, but returns first value returned by `predicate` that is not
    `False` or `None`.

    >>> find_map(
    ...     lambda dct: dct.get('z'),
    ...     ({'x': 1}, {'y': 2}, {'z': 3}),
    ... )
    3
    """
    for item in itr:
        result = fn(item)
        if result not in nothing:
            return result
    return not_found


def intersperse(
    iterable: Iterable[TItem], separator: V
) -> Generator[Union[TItem, V], None, None]:
    """\
    Like a "join", but general.

    >>> list(intersperse([1, 2, 3], 'and'))
    [1, 'and', 2, 'and', 3]
    """
    iterator = iter(iterable)
    yield next(iterator)
    for item in iterator:
        yield separator
        yield item

def interspersed(
    iterable: Iterable[TItem], separator: V
) -> List[Union[TItem, V]]:
    """\
    Just `intersperse`, but converts the result to a `list` for you (instead
    of a generator).

    >>> list(intersperse([1, 2, 3], 'and'))
    [1, 'and', 2, 'and', 3]
    """
    return list(intersperse(iterable, separator))

if __name__ == '__main__':
    from pathlib import Path
    import doctest
    doctest.testmod()

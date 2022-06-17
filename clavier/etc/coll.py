##############################################################################
# Collection Manipulators
# ============================================================================
##############################################################################

from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    List,
    Mapping,
    Sequence,
    Union,
)

TDiggable = Union[Sequence, Mapping]


def dig(target: TDiggable, *key_path: Sequence, not_found: Any = None):
    """Like Ruby - get the value at a key-path, or `not_found` if any keys in
    the path are missing.

    >>> d = {'A': {'B': 'V'}}
    >>> dig(d, 'A', 'B')
    'V'
    >>> dig(d, 'A', 'C') is None
    True
    >>> dig(d)
    {'A': {'B': 'V'}}

    >>> dig(['a', 'b'], 0)
    'a'

    >>> mixed = {'a': [{'x': 1}, {'y': [2, 3]}], 'b': {'c': [4, 5]}}
    >>> dig(mixed, 'a', 0, 'x')
    1
    >>> dig(mixed, 'a', 1, 'y', 0)
    2
    >>> dig(mixed, 'a', 1, 'y', 1)
    3
    >>> dig(mixed, 'b', 'c', 0)
    4
    >>> dig(mixed, 'b', 'c', 1)
    5
    """

    for key in key_path:
        if isinstance(target, Sequence):
            if isinstance(key, int) and key >= 0 and key < len(target):
                target = target[key]
            else:
                return not_found
        elif isinstance(target, Collection) and key in target:
            target = target[key]
        else:
            return not_found
    return target


def default_bury_create(
    target: TDiggable,
    for_key: Sequence,
) -> TDiggable:
    # return [] if isinstance(for_key, int) else {}
    return {}


def bury(
    root: TDiggable,
    key_path: Sequence,
    value: Any,
    *,
    create: Callable[[TDiggable, Any], TDiggable] = default_bury_create,
):
    """
    >>> bury({}, ["A", 1, "B", 2], "TREASURE")
    {'A': {1: {'B': {2: 'TREASURE'}}}}

    >>> bury({}, ["family", "debian"], "payload")
    {'family': {'debian': 'payload'}}
    """
    target = root
    while len(key_path) > 0:
        key, *key_path = key_path
        if len(key_path) == 0:
            # Termination case — no more keys!
            target[key] = value
        else:
            # We now _know_ there are more keys on the path...
            if key in target:
                # Easy case — more the target down the path
                target = target[key]
            else:
                # Wonky case — need to create something, which depends on the
                # _next_ key (which — as mentioned above — we know exists)
                #
                target[key] = create(target, key_path[0])
                target = target[key]
    return root


if __name__ == "__main__":
    import doctest

    doctest.testmod()

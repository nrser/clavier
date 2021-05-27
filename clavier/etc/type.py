from typing import Union, Literal, NewType, Any

Null = NewType("Null", Union[None, Literal[False]])  # type: ignore

def is_null(x: Any) -> bool:
    """
    >>> is_nope(None)
    True

    >>> is_nope(False)
    True

    >>> any(is_nope(x) for x in ('', [], {}, 0, 0.0))
    False
    """
    return x is None or x is False

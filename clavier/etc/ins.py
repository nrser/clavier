"""Library functions we wish were in `inspect`."""

from typing import Callable, Any
from inspect import isfunction, isclass, signature, unwrap


def is_unbound_method_of(fn: Callable, obj: Any) -> bool:
    # We want to work with the original function, unwrapping any decorators
    unwrapped_fn = unwrap(fn)

    # The user can pass a class or an instance value, so figure out what the
    # class is
    cls = obj if isclass(obj) else obj.__class__

    # Source function gotta have a name for us to find it on the class
    if not hasattr(unwrapped_fn, "__name__"):
        return False
    attr_name = unwrapped_fn.__name__

    # If class doesn't have an attribute named the same as the function then it
    # sure can't have the function as it's value
    if not hasattr(cls, attr_name):
        return False
    attr_value = getattr(cls, attr_name)

    # If the attribute value is not a function, then it can't be our function
    # either
    if not isfunction(attr_value):
        return False

    # Finally, unwrap the value from got from the class and see if it's the same
    return unwrap(attr_value) is unwrapped_fn


def accepts_kwd(fn: Callable, name: str) -> bool:
    """
    ##### Examples #####

    ```python
    >>> def f(x, /, y=None):
    ...     pass

    >>> accepts_kwd(f, "y")
    True

    >>> accepts_kwd(f, "x")
    False

    >>> def g(x, y):
    ...     pass

    >>> accepts_kwd(g, "x")
    True

    >>> accepts_kwd(g, "y")
    True

    >>> def h(x, **kwds):
    ...     pass

    >>> accepts_kwd(h, "x")
    True

    >>> accepts_kwd(h, "y")
    True

    >>> accepts_kwd(h, "z")
    True

    ```
    """
    sig = signature(fn)

    if param := sig.parameters.get(name):
        return (
            param.kind is param.POSITIONAL_OR_KEYWORD
            or param.kind is param.KEYWORD_ONLY
        )

    return any(
        param.kind is param.VAR_KEYWORD for param in sig.parameters.values()
    )

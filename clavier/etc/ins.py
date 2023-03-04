"""Library functions we wish were in `inspect`."""

from typing import Callable, Any, Mapping, MutableMapping, ParamSpec, TypeVar
from inspect import (
    BoundArguments,
    isfunction,
    isclass,
    signature,
    unwrap,
    Parameter,
)

TParams = ParamSpec("TParams")
TReturn = TypeVar("TReturn")


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


def adaptive_bind(fn: Callable, **available: Any) -> BoundArguments:
    """
    Bind arguments from the `available` name/value mapping given the
    `Parameter.name` and `Parameter.kind` found in the `Signature` of `fn`.

    The goal is to successfully create `BoundArguments` for `fn` using a subset
    of the `available` values. Raises a `TypeError` if this fails.

    > 📝 NOTE
    >
    > Doesn't even look at type annotations. So, no type checking, casting, etc.
    > Binding is _solely_ based on parameter names to mapping keys.

    ##### Parameters #####

    -   `fn` — function to bind to.
    -   `available` — mapping of names to values available to bind.

    ##### Discussion #####

    This function is used for "inversion of control" between a caller and
    callee: the callee (`fn` in this case) is able to dictate what values it
    wants to receive from the caller simply by knowing what variables the caller
    may have available and defining its signature to reflect its wants and
    needs.

    This technique is useful in "framework" situations where the framework will
    be invoking a user-defined function and may have a lot of information
    available that it can pass to said function. It allows the user function to
    be defined exactly as it would be for call by first-party code, removing the
    need for decorators, registration, or other method of converying the
    information.

    ##### Examples #####

    1.  A function that accepts no arguments will _always_ successfully bind as it
        can be satisfied with an empty binding.

        ```python
        >>> def f_1():
        ...     pass

        >>> adaptive_bind(f_1, a=1, b=2)
        <BoundArguments ()>

        ```

    2.  Providing arguments that match parameter names results in them being
        bound in the result. Arguments that do not match are ignored.

        ```python
        >>> def f_2(a, b):
        ...     pass

        >>> adaptive_bind(f_2, a=1, b=2, c=3)
        <BoundArguments (a=1, b=2)>

        ```

    3.  Takes account of `Parameter.kind` (positional-only, keyword-only, etc.)
        and parameter defaults.

        ```python
        >>> def f_3(a, /, b, *, c=3, **kwds):
        ...     pass

        >>> adaptive_bind(f_3, a=1, b=2)
        <BoundArguments (a=1, b=2, c=3)>

        ```

    4.  If a _variable keyword_ parameter (`**`/double-splat) is part of the
        `Signature` of `fn` then all items from `available` that were _not_
        bound to other paramters will be bound there.

        ```python
        >>> adaptive_bind(f_3, a=1, b=2, c=0, d=4)
        <BoundArguments (a=1, b=2, c=0, kwds={'d': 4})>

        ```

    5.  If a _variable positional_ parameter (`*`/single-splat) is part of the
        `Signature` of `fn` _and_ `available` has a item with the same name then
        that value will be bound to the splat parameter.

        ```python
        >>> def f_4(*var_pos, opt_1=1, opt_2=2):
        ...     pass

        >>> adaptive_bind(f_4, var_pos=('a', 'b', 'c'), opt_2=8)
        <BoundArguments (var_pos=('a', 'b', 'c'), opt_1=1, opt_2=8)>

        ```

        If the `available` value is not `typing.Iterable` an error will be
        raised.

        ```python
        >>> adaptive_bind(f_4, var_pos=123, opt_2=8)
        Traceback (most recent call last):
            ...
        TypeError: failed to bind to parameter `var_pos` of
            <function f_4 at ...> -- 'int' object is not iterable

        ```

    ##### See Also #####

    1.  `adaptive_bind_mut` — when you already have a mutable `available`
        mapping that you don't need again.
    """
    return adaptive_bind_mut(fn, available)


def adaptive_bind_mut(
    fn: Callable, available: MutableMapping[str, Any]
) -> BoundArguments:
    """The work-horse of `adaptive_bind`. This function assumes it can mutate
    `available` however it likes ("owns" it, you might say).

    If you have a mutable mapping already that you won't need again you can
    call this method directly and avoid the re-splatter of going through
    `adaptive_bind`.

    I'm sure this really isn't necessary and doesn't really make a difference on
    a performance level but I'm just in one of those moods today I guess, so
    here it is.

    ##### Parameters #####

    See `adaptive_bind`.

    """

    def pop(param: Parameter):
        if param.default is Parameter.empty:
            return available.pop(param.name)
        return available.pop(param.name, param.default)

    sig = signature(fn)

    args: list[Any] = []
    kwds: dict[str, Any] = {}

    for param in sig.parameters.values():
        try:
            match param.kind:
                case Parameter.POSITIONAL_ONLY:
                    args.append(pop(param))
                case Parameter.POSITIONAL_OR_KEYWORD:
                    args.append(pop(param))
                case Parameter.VAR_POSITIONAL:
                    args.extend(pop(param))
                case Parameter.KEYWORD_ONLY:
                    kwds[param.name] = pop(param)
                case Parameter.VAR_KEYWORD:
                    kwds.update(available)
        except Exception as error:
            raise TypeError(
                "failed to bind to parameter `{}` of {} -- {}".format(
                    param.name, fn, error
                )
            ) from error

    return sig.bind(*args, **kwds)


def adaptive_call(fn: Callable[..., TReturn], **available: Any) -> TReturn:
    binding = adaptive_bind(fn, **available)
    return fn(*binding.args, **binding.kwargs)

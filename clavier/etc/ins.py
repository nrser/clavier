"""Library functions we wish were in `inspect`."""

from typing import Callable, Any
from inspect import isfunction, isclass, unwrap

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

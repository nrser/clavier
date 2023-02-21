##############################################################################
# Some Really Lame "Functional" Crap
# ============================================================================
#
# Ok I'll admit I was screwing around with Rust to write the fast `clavier.srv`
# endpoint, and I've always been annoyed by using random "sentinel" values to
# mean "really nothing, not even `None`" so I threw this together in a few
# minutes.
#
# I don't think it works all that great, but I'm gonna stick with it for a
# minute here and see how it goes (2023-02-21).
#
##############################################################################

from __future__ import annotations
from typing import Generic, TypeVar, final, overload


T = TypeVar("T")


@final
class Nada(Generic[T]):
    __slots__ = ()

    def __bool__(self) -> bool:
        return False

    def unwrap(self) -> T:
        raise AttributeError("Nothing here")

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Nada)


@final
class Some(Generic[T]):
    __slots__ = "_value"

    _value: T

    def __init__(self, value: T):
        self._value = value

    def __bool__(self) -> bool:
        return True

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Nada)

    def unwrap(self) -> T:
        return self._value


Option = Some[T] | Nada[T]


@overload
def as_option(x: Option[T]) -> Option[T]:
    ...


@overload
def as_option(x: T) -> Option[T]:
    ...


def as_option(x):
    """Make `x` into an `Option`. If it already was one, it simply gets
    returned. Otherwise, it becomes `Some(x)`.

    Note that `Some(None)` is perfectly valid. In fact it's kinda the whole
    point of this stupid exercise: to be able to differentiate between `None`
    and "really nothing, not even `None`" (which is `Nada`), such as in the case
    of argument defaults.
    """
    if isinstance(x, Nada):
        return x
    if isinstance(x, Some):
        return x
    return Some(x)

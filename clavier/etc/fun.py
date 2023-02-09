from typing import Generic, TypeVar


T = TypeVar("T")


class Nada(Generic[T]):
    def __bool__(self) -> bool:
        return False

    def unwrap(self) -> T:
        raise AttributeError("Nothing here")


class Some(Generic[T]):
    _value: T

    def __init__(self, value: T):
        self._value = value

    def __bool__(self) -> bool:
        return True

    def unwrap(self) -> T:
        return self._value


Option = Some[T] | Nada[T]


def as_option(x: Option[T] | T) -> Option[T]:
    if isinstance(x, Nada):
        return x
    if isinstance(x, Some):
        return x
    return Some(x)

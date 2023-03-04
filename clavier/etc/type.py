from typing import Callable, TypeGuard, TypeVar


T = TypeVar("T")


def instance_guard(t: type[T]) -> Callable[[object], TypeGuard[T]]:
    def isinstance_guard(x: object) -> TypeGuard[T]:
        return isinstance(x, t)

    return isinstance_guard

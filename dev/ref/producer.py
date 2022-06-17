from __future__ import annotations
from typing import Callable, Generic, TypeVar, Union


T = TypeVar("T")

Produces = Union[T, Callable[[], T]]


class Producer(Generic[T]):
    @staticmethod
    def value_for(ref: Union[T, Producer[T]]) -> T:
        if isinstance(ref, Producer):
            return ref()
        return ref

    _callable: Callable[[], T]

    def __init__(self, callable: Callable[[], T]):
        self._callable = callable

    def __call__(self) -> T:
        return self._callable()
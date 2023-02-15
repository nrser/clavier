from __future__ import annotations
from typing import (
    Callable,
    Generic,
    ParamSpec,
    TypeVar,
)
from contextvars import Context, ContextVar, Token


T = TypeVar("T")
TParams = ParamSpec("TParams")
_T = TypeVar("_T")


class ContextVarManager(Generic[TParams, T]):
    class _ContextManager(Generic[_T]):
        __slots__ = ["_var", "_value", "_token", "_reset_on_error"]

        _var: ContextVar[_T]
        _value: _T
        _token: Token | None
        _reset_on_error: bool

        def __init__(
            self, var: ContextVar[_T], value: _T, reset_on_error: bool
        ):
            self._var = var
            self._value = value
            self._token = None
            self._reset_on_error = reset_on_error

        def __enter__(self) -> _T:
            if self._token is not None:
                raise RuntimeError("can not re-enter context")

            self._token = self._var.set(self._value)

            return self._value

        def __exit__(self, exc_type, exc_value, traceback) -> None:
            if self._token is None:
                raise RuntimeError("can not __exit__ without __enter__ first")

            if self._reset_on_error or exc_type is None:
                self._var.reset(self._token)

    _constructor: Callable[TParams, T]
    _var: ContextVar[T]
    _default: T
    _reset_on_error: bool

    def __init__(
        self,
        name: str,
        constructor: Callable[TParams, T],
        default: T,
        reset_on_error: bool = True,
    ):
        self._constructor = constructor
        self._var = ContextVar(name, default=default)
        self._default = default
        self._reset_on_error = reset_on_error

    @property
    def default(self) -> T:
        return self._default

    def get(self) -> T:
        return self._var.get()

    def reset(self):
        """Resets to the `default` value. Useful if not resetting on error."""
        self._var.set(self._default)

    def get_and_reset(self) -> T:
        value = self.get()
        self.reset()
        return value

    def __call__(self, *args: TParams.args, **kwds: TParams.kwargs):
        return self._ContextManager(
            var=self._var,
            value=self._constructor(*args, **kwds),
            reset_on_error=self._reset_on_error,
        )

from contextvars import Context, ContextVar, copy_context, Token
from typing import Any, Callable, TypeVar, overload


from .config import Config, MutableConfig
from .container import Container
from .key import KeyMatter
from .changeset import Changeset

T = TypeVar("T")
TReturn = TypeVar("TReturn")

GLOBAL = Container()

config = ContextVar[Config]("config", default=GLOBAL)


def current() -> Config:
    return config.get()


def changeset(*prefix: KeyMatter, **meta: Any) -> Changeset:
    config = current()

    if isinstance(config, MutableConfig):
        return config.changeset(*prefix, **meta)

    raise Exception("Not mutable")


@overload
def get_as(key: KeyMatter, as_a: type[T]) -> T:
    ...


@overload
def get_as(key: KeyMatter, as_a: type[T], default: T) -> T:
    ...


def get_as(key: KeyMatter, as_a: type[T], *args, **kwds) -> T:
    return current().get_as(key, as_a, *args, **kwds)


def derive() -> Token:
    current = config.get()
    derived = Container(parent=current)
    return config.set(derived)


def derived_context() -> Context:
    context = copy_context()
    context.run(derive)
    return context


def run_in_derived_context(fn: Callable[[], TReturn]) -> TReturn:
    ctx = copy_context()
    ctx.run(derive)
    return ctx.run(fn)

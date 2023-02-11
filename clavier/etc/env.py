from os import environ
from typing import Any, Callable, TypeVar, cast

import yaml
from splatlog.lib.typeguard import satisfies
from splatlog.lib.text import fmt, fmt_type_of

from clavier.etc.fun import Option, Nada, Some, as_option

T = TypeVar("T")

TRUE_STRINGS = frozenset(
    (
        "1",
        "t",
        "y",
        "true",
        "yes",
    )
)
FALSE_STRINGS = frozenset(
    (
        "",
        "0",
        "f",
        "n",
        "false",
        "no",
    )
)


class UnreachableError(RuntimeError):
    def __init__(self):
        super().__init__("This code should never be reachable")


def get_bool(name: str) -> bool:
    match environ.get(name):
        case None:
            return False
        case str(s):
            if s in TRUE_STRINGS:
                return True
            if s in FALSE_STRINGS:
                return False
            raise TypeError(
                f"can't get `bool` from env var {name}={s!r}; "
                f"recognized values are True={'|'.join(TRUE_STRINGS)} "
                f"and False={'|'.join(FALSE_STRINGS)} (case-insensitive)"
            )
    raise UnreachableError()


def get_str(name: str) -> str:
    match environ.get(name):
        case None:
            return ""
        case str(s):
            return s
    raise UnreachableError()


def get_int(name: str) -> int:
    match environ.get(name):
        case None | "":
            return 0
        case str(s):
            return int(s)
    raise UnreachableError()


def get_float(name: str) -> float:
    match environ.get(name):
        case None | "":
            return 0.0
        case str(s):
            return float(s)
    raise UnreachableError()


def get_yaml(name: str) -> Any:
    match environ.get(name):
        case None | "":
            return None
        case str(s):
            try:
                return yaml.safe_load(s)
            except Exception as error:
                raise TypeError(
                    f"can't parse YAML from env var {name}={s!r}; "
                    f"string value: {s!r}"
                )
    raise UnreachableError()


def get_as(name: str, as_a: type[T]) -> T:
    match as_a:
        case t if t is bool:
            return cast(T, get_bool(name))
        case t if t is str:
            return cast(T, get_str(name))
        case t if t is int:
            return cast(T, get_int(name))
        case t if t is float:
            return cast(T, get_float(name))
        case _:
            value = get_yaml(name)
            if satisfies(value, as_a):
                return value
            raise TypeError(
                f"YAML-parsed value {fmt(value)} from env var {name} "
                f"does not satisfy type {fmt(as_a)}"
            )

from __future__ import annotations
from typing import Iterable, TypeVar, cast, overload

from clavier.cfg.scope import ReadScope
from typeguard import check_type
import splatlog

from .config import Config
from .key import Key

T = TypeVar("T")
_T1 = TypeVar("_T1")
_T2 = TypeVar("_T2")
_T3 = TypeVar("_T3")
_T4 = TypeVar("_T4")
_T5 = TypeVar("_T5")
_T6 = TypeVar("_T6")
_T7 = TypeVar("_T7")
_T8 = TypeVar("_T8")

_LOG = splatlog.get_logger(__name__)
SELF_ROOT_KEY = Key(__package__).root
CFG = Config()

with CFG.configure(SELF_ROOT_KEY, src=__file__) as clavier:
    clavier.backtrace = False
    clavier.verbosity = 0

    with clavier.configure("log") as log:
        log.level = "WARNING"

    with clavier.configure("sh") as sh:
        sh.encoding = "utf-8"
        sh.rel_paths = False

        with sh.configure("opts") as opts:
            opts.long_prefix = "--"
            opts.sort = True
            opts.style = "="

    with clavier.configure("dyn") as dyn:
        with dyn.configure("children_modules") as children_modules:
            children_modules.on_error = "warn"


def get_root(module_name: str):
    return CFG[Key(module_name).root]


@overload
def extract(scope: object, k1: tuple[str, type[_T1]], /) -> tuple[_T1]:
    ...


@overload
def extract(
    scope: object, k1: tuple[str, type[_T1]], k2: tuple[str, type[_T2]], /
) -> tuple[_T1, _T2]:
    ...


@overload
def extract(
    scope: object,
    k1: tuple[str, type[_T1]],
    k2: tuple[str, type[_T2]],
    k3: tuple[str, type[_T3]],
    /,
) -> tuple[_T1, _T2, _T3]:
    ...


@overload
def extract(
    scope: object,
    k1: tuple[str, type[_T1]],
    k2: tuple[str, type[_T2]],
    k3: tuple[str, type[_T3]],
    k4: tuple[str, type[_T4]],
    /,
) -> tuple[_T1, _T2, _T3, _T4]:
    ...


def extract(scope: object, *keys):
    check_type(scope, Config | ReadScope, argname="scope")
    scope = cast(Config | ReadScope, scope)

    values = []

    for key, type_ in keys:
        value = scope[key]
        check_type(value, type_, argname=key)
        values.append(value)

    return tuple(values)


configure = CFG.configure
get = CFG.get
inject = CFG.inject

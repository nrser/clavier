from __future__ import annotations
from contextvars import ContextVar
from typing import Any, Literal, TypeVar, cast, overload

from typeguard import check_type

from clavier import etc

from .config import Config, MutableConfig
from .key import Key, KeyMatter
from .scope import Scope, MutableScope
from .changeset import Changeset
from .container import Container
from .context import ContextualConfig

T = TypeVar("T")

SELF_ROOT_KEY = Key(__package__).root

# Globals
# ============================================================================
#
# These are the global values that underpin the config system. There is some
# ceremony involved to:
#
# 1.  Use lower-case names (upper-case for there bothers me, except `GLOBAL`
#     where I think it help to "call it out" like that).
# 2.  Make the values read-only.
# 3.  Satisfy the type checker (PyLance at the moment of 2023-02-13).
#

#: The global root `Container`, shared by all contexts.
GLOBAL = Container(name="GLOBAL")

#: The actual `contextvars.ContextVar` reference, which holds the current
#: `Config` for the active `contetvars.Context`.
_context_var = ContextVar[Config]("context_var", default=GLOBAL)


_current = ContextualConfig(_context_var)

#: `contextvars.ContextVar` holding the current config.
#:
#: > 📝 NOTE This is simply a type declaration to make PyLance happy; actual
#: > resolution is performed by a module-level `__getattr__` in order to protect
#: > the variable from being reassigned.
#:
context_var: ContextVar[Config]

#: A `ContextualConfig` (which is a `Config`) that dynamically resolves
#: operations to the current config (via the `context_var`).
#:
#: > 📝 NOTE This is simply a type declaration to make PyLance happy; actual
#: > resolution is performed by a module-level `__getattr__` in order to protect
#: > the variable from being reassigned.
#:
current: ContextualConfig


@overload
def __getattr__(name: Literal["current"]) -> ContextualConfig:
    ...


@overload
def __getattr__(name: Literal["context_var"]) -> ContextVar[Config]:
    ...


def __getattr__(name: str):
    """Handles resolution of the `current` and `context_var` globals, so as
    to protect their variables from being reassigned.
    """
    match name:
        case "current":
            return _current
        case "context_var":
            return _context_var

    raise AttributeError(f"module {__name__} has no attribute {name}")


# Global Configuration
# ============================================================================

with GLOBAL.configure(SELF_ROOT_KEY, src=__file__) as clavier:
    clavier.backtrace = False
    clavier.verbosity = 0
    clavier.output = "rich"

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

    with clavier.configure("arg_par") as arg_par:
        with arg_par.configure("formatters.rich_help_formatter") as formatter:
            formatter.min_width = 64
            formatter.invocation_ratio = 0.33
            formatter.indent = 2


# Convenience Functions
# ============================================================================


@overload
def get(key: Key[T], /) -> T:
    ...


@overload
def get(key: dict[KeyMatter, type[T]], /) -> T:
    ...


@overload
def get(*key_parts: KeyMatter) -> Any:
    ...


@overload
def get(*key_parts: KeyMatter, v_type: type[T]) -> T:
    ...


@overload
def get(key: Key[T], /, *, default: T) -> T:
    ...


@overload
def get(key: dict[KeyMatter, type[T]], /, *, default: T) -> T:
    ...


@overload
def get(*key_parts: KeyMatter, default: Any) -> Any:
    ...


@overload
def get(*key_parts: KeyMatter, default: T, v_type: type[T]) -> T:
    ...


def get(*args, **kwds):
    """Get a value from the `current` `Config` using a `Key` or information that
    can be made into a `Key`.

    The operation can by typed by providing a `v_type` (value type) to the `Key`
    or as a keyword argument.

    A `default` keyword argument may also be provided to return if there is no
    value for the `Key`.

    > ❗❗ WARNING ❗❗
    >
    > This function is _not_ the same as `Config.get`. `Config.get` adheres to
    > the `collections.abc.Mapping` API, which has _slightly_ different
    > semantics.
    >
    > The biggest difference is that this `get` will raise when given a key that
    > doesn't exist _unless_ you explicitly provide a `default` keyword.
    >
    > This is all to make the type hints situation a bit easier. It may need to
    > change depending on how confusing it ends up being in practice.
    >
    > The equivalent method on `Config` is `Config.__call__` btw.
    >
    """
    default = etc.as_option(kwds.pop("default", etc.Nada()))
    key = Key(*args, **kwds)

    match default:
        case etc.Nada():
            return _current[key]
        case etc.Some():
            return _current.get(key, default.unwrap())


def get_scope(
    *key_parts: KeyMatter,
    strict: bool = False,
    keep__init__: bool = False,
) -> Scope:
    key = Key(*key_parts, v_type=Scope)

    if "__init__" in key and not keep__init__:
        key = key.reject(lambda part: part == "__init__")

    if strict or key in _current:
        return _current[key]

    return Scope(parent=_current, key=key)


def get_pkg_scope(
    module_name: str,
    *,
    strict: bool = False,
    keep__init__: bool = False,
) -> Scope:
    """Helper to get the root scope for a package given the name of a one of
    the package's modules. Resolved against the `current` config.

    This is (kinda) useful when you want to configure package stuff during some
    sort of setup, basically instead of hard-coding the package name as a `str`
    or doing the `__name__.split(".")[0]` dance.

    > 📝 NOTE
    >
    > This does _not_ take namespaced package distributions into account at all.
    > For example, if `get_pkg_scope` is called with module names from package
    > distributions `whatever.core` and `whatever.util` _both_ calls will
    > resolve the same `whatever` package scope.

    ##### Examples #####

    Get the root `Scope` for this package (`"clavier"`) given some `__name__` in
    it (`"calvier.cfg.__init__"` in this case).

    ```python
    >>> pkg_scope = get_pkg_scope(__name__)

    >>> pkg_scope
    <Scope[clavier] -> Container(name=GLOBAL)>

    >>> isinstance(pkg_scope, Scope)
    True

    >>> pkg_scope._key_ == Key("clavier")
    True

    ```

    By default, this function is not `strict` — if no configuration exists for
    the package root it will return an empty `Scope`. This makes life easier
    when

    ```python
    # >>> get_pkg_scope("some.made_up.package")

    ```
    """
    return get_scope(Key(module_name).root)


pkg = get_pkg_scope


def changeset(*prefix: KeyMatter, **meta: Any) -> Changeset:
    config = _context_var.get()

    if isinstance(config, MutableConfig):
        return config.changeset(*prefix, **meta)

    raise TypeError("Current config must be a {} to create a {}; found ")

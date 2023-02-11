from __future__ import annotations
from abc import ABCMeta, abstractmethod
from functools import wraps
import os
from typing import (
    TYPE_CHECKING,
    Any,
    ParamSpec,
    Concatenate,
    TypeVar,
    cast,
    overload,
)
from collections.abc import Mapping, Iterator, Callable, Iterable, KeysView

from splatlog.lib.typeguard import satisfies
from splatlog.lib.text import fmt, fmt_type_of
import yaml
from clavier.etc.fun import Option, Nada, Some, as_option
from clavier import etc

from .key import Key, KeyMatter

if TYPE_CHECKING:
    from .changeset import Changeset

TParams = ParamSpec("TParams")
TReturn = TypeVar("TReturn")
T = TypeVar("T")


class Config(Mapping[KeyMatter, Any], metaclass=ABCMeta):

    # Internal API
    # ========================================================================

    # Required Methods
    # ------------------------------------------------------------------------
    #
    # These are the ones the realizing classes **must** implement.
    #

    @abstractmethod
    def _get_parent_(self) -> Config | None:
        ...

    @abstractmethod
    def _own_keys_(self) -> Iterable[Key]:
        ...

    @abstractmethod
    def _has_own_(self, key: Key) -> bool:
        ...

    @abstractmethod
    def _get_own_(self, key: Key) -> Any:
        ...

    # Optional Methods
    # ------------------------------------------------------------------------
    #
    # These have default implementations, but realizing classes may want to
    # override them if they have a more efficient solution, especially if they
    # are going to be called often.
    #

    def _own_scopes_(self) -> set[Key]:
        own_scopes: set[Key] = set()

        for key in self._own_keys_():
            own_scopes.update(key.scopes())

        return own_scopes

    def _has_own_scope_(self, scope: Key) -> bool:
        return any(k.has_scope(scope) for k in self._own_keys_())

    def _as_key_(self, key_matter: KeyMatter) -> Key:
        return Key(key_matter)

    def _check_type_(self, key: Key[T], value: object) -> T:
        """Verify that a `value` — which has presumably been retrieved from the
        `Config` — has the appropriate type given the `key` used to retreive it.
        """

        if satisfies(value, key.v_type):
            return value
        raise TypeError(
            f"expected config value {key!s} to be {fmt(key.v_type)}; "
            f"found {fmt_type_of(value)}: {fmt(value)}"
        )

    # Public API
    # ========================================================================

    # Environment Variables
    # ------------------------------------------------------------------------

    def env_has(self, key: Key) -> bool:
        return key.env_name in os.environ

    def env_get(self, key: Key[T]) -> T:
        return etc.env.get_as(key.env_name, key.v_type)

    # Scopes
    # ------------------------------------------------------------------------

    def scopes(self) -> set[Key]:
        scopes = self._own_scopes_()

        if parent := self._get_parent_:
            scopes.update(parent.scopes())

        return scopes

    # Collections API
    # ------------------------------------------------------------------------
    #
    # Supports `Config` being a `collections.abc.Mapping`.
    #

    ### `collections.abc.Iterable` ###

    def __iter__(self) -> Iterator[Key]:
        yield from self._own_keys_()

        if parent := self._get_parent_():
            for key in parent:
                if not self._has_own_(key):
                    yield key

    ### `collections.abc.Sized` ###

    def __len__(self) -> int:
        return sum(1 for _ in self)

    ### `collections.abc.Mapping` ###

    @overload
    def __getitem__(self, __key: Key[T], /) -> T:
        """Get an item of type `T` by providing a typed `Key[T]`.

        ```python
        v: int = config[Key("a.b.c", v_type=int)]
        ```
        """
        ...

    @overload
    def __getitem__(self, __key: dict[KeyMatter, type[T]], /) -> T:
        """Get an item of type `T` by providing a `dict` with a _single_
        key/value pair (a constrain which can not be represented in the type
        signature at this time) of `KeyMatter => type[T]`.

        ```python
        v: int = config[{"a.b.c": int}]
        ```

        """
        ...

    @overload
    def __getitem__(self, __key: KeyMatter, /) -> Any:
        """Get an untyped (`typing.Any`) value using `KeyMatter`.

        ```python
        v: Any = config["a.b.c"]
        ```
        """
        ...

    def __getitem__(self, __key, /):
        key = self._as_key_(__key)

        # Env vars override all
        if self.env_has(key):
            return self.env_get(key)

        # If this config has the extact key, then return that value
        if self._has_own_(key):
            return self._check_type_(key, self._get_own_(key))

        # If the key matches one of the config's own scopes then return a read
        # scope around it. This needs to be here to deal with overriding a value
        # in the parent with a scope in this config.
        if self._has_own_scope_(key):
            from .scope import Scope

            return self._check_type_(key, Scope(parent=self, key=key))

        # and check the parent
        if parent := self._get_parent_():
            try:
                return parent[key]
            except KeyError:
                pass

        raise KeyError(f"Config has no key or scope {repr(key)}")

    # Attribute Access
    # ------------------------------------------------------------------------

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except AttributeError as error:
            raise error
        except Exception as error:
            raise AttributeError(f"Not found: {repr(name)}") from error

    # `dict` Materialization
    # ------------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {str(key): self[key] for key in self}

    # Updating
    # ------------------------------------------------------------------------

    def inject(
        self, fn: Callable[Concatenate[Any, TParams], TReturn]
    ) -> Callable[TParams, TReturn]:
        key = Key(fn.__module__, fn.__name__)

        @wraps(fn)
        def configured(*args: TParams.args, **kwds: TParams.kwargs) -> TReturn:
            config = self.get(key)
            return fn(config, *args, **kwds)

        return configured


class MutableConfig(Config, metaclass=ABCMeta):
    @abstractmethod
    def changeset(self, *prefix: KeyMatter, **meta: Any) -> "Changeset":
        ...

    @abstractmethod
    def commit(self, changeset: "Changeset") -> None:
        ...

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
    overload,
)
from collections.abc import Mapping, Iterator, Callable, Iterable, KeysView

import yaml
from typeguard import check_type
from clavier.etc.fun import Option, Nada, Some, as_option

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

    # Public API
    # ========================================================================

    # Environment Variables
    # ------------------------------------------------------------------------

    def env_has(self, key: Key) -> bool:
        return key.env_name in os.environ

    def env_get(self, key: Key):
        value_s = os.environ[key.env_name]
        return yaml.safe_load(value_s)

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

    def __getitem__(self, key) -> Any:
        key = self._as_key_(key)

        # Env vars override all
        if self.env_has(key):
            return self.env_get(key)

        # If this config has the extact key, then return that value
        if self._has_own_(key):
            return self._get_own_(key)

        # If the key matches one of the config's own scopes then return a read
        # scope around it. This needs to be here to deal with overriding a value
        # in the parent with a scope in this config.
        if self._has_own_scope_(key):
            from .scope import ReadScope

            return ReadScope(parent=self, key=key)

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

    # Typed Access
    # ------------------------------------------------------------------------

    # @overload
    # def get_as(self, key: KeyMatter, as_a: type[T]) -> T:
    #     ...

    # @overload
    # def get_as(self, key: KeyMatter, as_a: type[T], default: T) -> T:
    #     ...

    # def get_as(self, key: KeyMatter, as_a: type[T], *args, **kwds) -> T:
    def get_as(
        self, key: KeyMatter, as_a: type[T], default: Option[T] | T = Nada()
    ) -> T:
        default = as_option(default)

        if isinstance(default, Some):
            value = self.get(key, default.unwrap())
        else:
            value = self[key]

        check_type(value, as_a, argname=str(key))

        return value

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

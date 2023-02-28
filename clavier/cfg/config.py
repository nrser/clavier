from __future__ import annotations
from abc import ABCMeta, abstractmethod
from functools import wraps
import os
from typing import (
    TYPE_CHECKING,
    Any,
    Generator,
    ParamSpec,
    Concatenate,
    TypeVar,
    overload,
)
from collections.abc import Mapping, Iterator, Callable, Iterable, KeysView

import splatlog
from splatlog.lib.typeguard import satisfies
from splatlog.lib.text import fmt, fmt_type_of
from rich.repr import RichReprResult

from clavier import etc, err

from .key import Key, KeyMatter

if TYPE_CHECKING:
    from .changeset import Changeset

TParams = ParamSpec("TParams")
TReturn = TypeVar("TReturn")
T = TypeVar("T")

_ExtractKey = Key[T] | tuple[KeyMatter, type[T]]
T_1 = TypeVar("T_1")
T_2 = TypeVar("T_2")
T_3 = TypeVar("T_3")
T_4 = TypeVar("T_4")
T_5 = TypeVar("T_5")
T_6 = TypeVar("T_6")
T_7 = TypeVar("T_7")
T_8 = TypeVar("T_8")

_LOG = splatlog.get_logger(__name__)


class Config(Mapping[KeyMatter, Any], metaclass=ABCMeta):
    """Universal interface for configuration objects."""

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
        """Hey"""
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
        ...

    @overload
    def __getitem__(self, __key: dict[KeyMatter, type[T]], /) -> T:
        ...

    @overload
    def __getitem__(self, __key: KeyMatter, /) -> Any:
        ...

    def __getitem__(self, __key, /):
        """Get an item from the config. Typed and untyped (`typing.Any`) forms
        available.

        `Config` adheres to the `collections.abc.Mapping` interface, with the
        notable addition of _typed keys_.

        You can attach a `type[T]` (for some concrete type `T`, not a
        `typing.TypeVar`) to a `Key` via the `v_type` parameter and successful
        queries for that key will return a value of type `T`.

        ##### Examples #####

        Preamble...

        ```python
        >>> from clavier import cfg

        >>> isinstance(cfg.current, Config)
        True

        ```

        1.  Get an item of type `T` by providing a typed `Key[T]`.

            ```python
            >>> v: int = cfg.current[Key("clavier.verbosity", v_type=int)]

            ```

            This will fail if the value at the key can not be coerced to the
            provided type.

            ```python
            >>> v: int = cfg.current[Key("clavier.output", v_type=int)]
            Traceback (most recent call last):
                ...
            TypeError: expected config value clavier.output to be int;
                found str: 'rich'

            ```

        2.  Get an untyped (`typing.Any`) value using an untyped `Key`.

            ```python
            >>> v: Any = cfg.current[Key("clavier.verbosity")]

            ```

        3.  Get an item of type `T` by providing a `dict` with a _single_
            key/value pair¹ () of `KeyMatter => type[T]`.

            ```python
            >>> v: int = cfg.current[{"clavier.verbosity": int}]
            >>> v: int = cfg.current[{("clavier", "verbosity"): int}]

            ```

            ¹ Note that this constraint can not be represented in the type
            signature at this time, but it is enforced at runtime.

        4.  Get an untyped (`typing.Any`) value using `KeyMatter`.

            ```python
            >>> v: Any = cfg.current["clavier.verbosity"]
            >>> v: Any = cfg.current["clavier", "verbosity"]

            ```

        """

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

    @overload
    def get(self, key: Key[T]) -> T | None:
        ...

    @overload
    def get(self, key: dict[KeyMatter, type[T]]) -> T | None:
        ...

    @overload
    def get(self, key: KeyMatter) -> Any:
        ...

    @overload
    def get(self, key: Key[T], default: T) -> T:
        ...

    @overload
    def get(self, key: dict[KeyMatter, type[T]], default: T) -> T:
        ...

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default
        except TypeError as error:
            _LOG.warning(f"Bad key type? {error}")
            return default

    # Attribute-Style Access
    # ------------------------------------------------------------------------

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except AttributeError as error:
            raise error
        except Exception as error:
            raise AttributeError(f"Not found: {repr(name)}") from error

    # Call-Style Access
    # ------------------------------------------------------------------------

    @overload
    def __call__(self, key: Key[T], /) -> T:
        ...

    @overload
    def __call__(self, key: dict[KeyMatter, type[T]], /) -> T:
        ...

    @overload
    def __call__(self, *key_parts: KeyMatter) -> Any:
        ...

    @overload
    def __call__(self, *key_parts: KeyMatter, v_type: type[T]) -> T:
        ...

    @overload
    def __call__(self, key: Key[T], /, *, default: T) -> T:
        ...

    @overload
    def __call__(self, key: dict[KeyMatter, type[T]], /, *, default: T) -> T:
        ...

    @overload
    def __call__(self, *key_parts: KeyMatter, default: Any) -> Any:
        ...

    @overload
    def __call__(self, *key_parts: KeyMatter, default: T, v_type: type[T]) -> T:
        ...

    def __call__(self, *args, **kwds):
        """Get a value from the `Config` by calling it like a function.

        ##### Examples #####

        1.  Doin' it right. Result is typed (per [PyLance][] at least).

            [PyLance]: https://github.com/microsoft/pylance-release#readme

            ```python
            >>> from clavier import cfg

            >>> cfg.current("clavier.verbosity", v_type=int)
            0

            ```

        2.  Wrong type raises.

            ```python
            >>> cfg.current("clavier.verbosity", v_type=str)
            Traceback (most recent call last):
                ...
            TypeError: expected config value clavier.verbosity to be str;
                found int: 0

            ```

        3.  Missing key raises.

            ```python
            >>> cfg.current("clavier.not_here", v_type=str)
            Traceback (most recent call last):
                ...
            KeyError: "Config has no key or scope
                Key('clavier.not_here', v_type=str)"

            ```

        4.  Unless you provide a `default`.

            ```python
            >>> cfg.current("clavier.not_here", v_type=str, default="but I insist")
            'but I insist'

            ```

        5.  Defaults of the _wrong type_... work, I guess.

            ```python
            >>> cfg.current("clavier.not_here", v_type=int, default="but I insist")
            'but I insist'

            ```

            In [PyLance][] the result will type as `int | str`, which is
            interesting... but I guess that's ok since you'll have to sort the
            union out to use the value. Might actually be kinda nice with
            `default=None`: automatic `typing.Optional`!

        6.  Key exists, key type is wrong, and a default was provided.

            This is an interesting one. I _think_ should give you the default
            back and drop a warning.

            The use case is a setting or default that the user may override,
            but you don't want to stop the show if they set a bad value.

            Let's say I'm an app using the library, and I set a bad value for
            `clavier.output`. It's supposed to be a `str`, but here I've
            (mistakenly, I'm sure) set it to be a `list[int]`.

            ```python
            >>> my_cfg = cfg.Container(parent=cfg.current._get_parent_())
            >>> with my_cfg.configure("clavier") as clavier:
            ...     clavier.output = [1, 2, 3]

            ```

            As the library author, however, there are places I don't want to
            fail due to the app's bad configuration value, so in addition to
            the `v_type` I also provide a `default`.

            ```python
            >>> my_cfg("clavier.output", v_type=str, default="json")
            'json'

            ```

            I feel like this goes with the `collections.abc.Mapping.get` vibe of
            "don't raise during the normal course of business".

        ##### Rationale #####

        This would preferably be named 'get' (as the same functionality for the
        global scope is with `clavier.cfg.get`), because that just feel like
        what you _want_ to be doing, but `collections.abc.Mapping` specifies a
        'get' method, and...

        1.  I feel like it would be confusing to violate that API, as it's so
            commonly used. It seems like an a-hole move to be _almost_ a
            `collections.abc.Mapping`.

        2.  Without violating that API (simply expanding it, as `__getitem__`
            does, which seems more ok to me) the method would need to return an
            implicit default of `None` when the key does not exist, and that's
            a pain from a typing perspective.

        So, I wanted something super-short for a name, and what's shorter than
        _no name at all_? Feels like fun and functional too, reminds me of
        Clojure or something that allows you to call maps with key to get
        values.
        """

        default = etc.as_option(kwds.pop("default", etc.Nada()))
        key = Key(*args, **kwds)

        match default:
            case etc.Nada():
                return self[key]
            case etc.Some():
                return self.get(key, default.unwrap())

    # Multi-Key Access
    # ------------------------------------------------------------------------

    @overload
    def _extract_(
        self, k_1: _ExtractKey[T_1], k_2: _ExtractKey[T_2], /
    ) -> tuple[T_1, T_2]:
        ...

    @overload
    def _extract_(
        self,
        k_1: _ExtractKey[T_1],
        k_2: _ExtractKey[T_2],
        k_3: _ExtractKey[T_3],
        /,
    ) -> tuple[T_1, T_2, T_3]:
        ...

    @overload
    def _extract_(
        self,
        k_1: _ExtractKey[T_1],
        k_2: _ExtractKey[T_2],
        k_3: _ExtractKey[T_3],
        k_4: _ExtractKey[T_4],
        /,
    ) -> tuple[T_1, T_2, T_3, T_4]:
        ...

    @overload
    def _extract_(
        self,
        k_1: _ExtractKey[T_1],
        k_2: _ExtractKey[T_2],
        k_3: _ExtractKey[T_3],
        k_4: _ExtractKey[T_4],
        k_5: _ExtractKey[T_5],
        /,
    ) -> tuple[T_1, T_2, T_3, T_4, T_5]:
        ...

    @overload
    def _extract_(
        self,
        k_1: _ExtractKey[T_1],
        k_2: _ExtractKey[T_2],
        k_3: _ExtractKey[T_3],
        k_4: _ExtractKey[T_4],
        k_5: _ExtractKey[T_5],
        k_6: _ExtractKey[T_6],
        /,
    ) -> tuple[T_1, T_2, T_3, T_4, T_5, T_6]:
        ...

    @overload
    def _extract_(
        self,
        k_1: _ExtractKey[T_1],
        k_2: _ExtractKey[T_2],
        k_3: _ExtractKey[T_3],
        k_4: _ExtractKey[T_4],
        k_5: _ExtractKey[T_5],
        k_6: _ExtractKey[T_6],
        k_7: _ExtractKey[T_7],
        /,
    ) -> tuple[T_1, T_2, T_3, T_4, T_5, T_6, T_7]:
        ...

    @overload
    def _extract_(
        self,
        k_1: _ExtractKey[T_1],
        k_2: _ExtractKey[T_2],
        k_3: _ExtractKey[T_3],
        k_4: _ExtractKey[T_4],
        k_5: _ExtractKey[T_5],
        k_6: _ExtractKey[T_6],
        k_7: _ExtractKey[T_7],
        k_8: _ExtractKey[T_8],
        /,
    ) -> tuple[T_1, T_2, T_3, T_4, T_5, T_6, T_7, T_8]:
        ...

    def _extract_(self, *keys):
        """Extract up to 8 typed values in a single call.

        ##### Examples #####

        ```python
        >>> from clavier import cfg

        >>> backtrace, verbosity, output = cfg.current._extract_(
        ...     ("clavier.backtrace", bool),
        ...     ("clavier.verbosity", int),
        ...     ("clavier.output", str),
        ... )

        ```
        """
        values = []

        for i, k in enumerate(keys):
            match k:
                case Key():
                    key = k
                case (km, v_type):
                    key = Key(km, v_type=v_type)
                case _:
                    raise err.ArgTypeError(
                        f"keys[{i}]", Key | tuple[KeyMatter, type[T]], k
                    )

            values.append(self[key])

        return tuple(values)

    # Logging / Printing
    # ------------------------------------------------------------------------

    def _ancestors_(
        self, include_self: bool = False
    ) -> Generator[Config, None, None]:
        target = self if include_self else self._get_parent_()
        while target is not None:
            yield target
            target = target._get_parent_()

    def _description_(self) -> str:
        return etc.txt.fmt_type_of(self, module_names=False)

    def __repr__(self) -> str:
        return "<{}>".format(
            " -> ".join(
                c._description_() for c in self._ancestors_(include_self=True)
            )
        )

    __str__ = __repr__

    def __rich_repr__(self) -> RichReprResult:
        yield "parent", self._get_parent_()

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

from __future__ import annotations
from functools import total_ordering
from types import FunctionType, ModuleType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generator,
    Generic,
    Iterable,
    Mapping,
    Type,
    TypeGuard,
    TypeVar,
    Union,
    cast,
    overload,
)
import re
from inspect import isclass, ismodule, isfunction
from collections.abc import Sequence, Iterator

if TYPE_CHECKING:
    from .scope import Scope

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
V = TypeVar("V")

#: What you can make a `Key` out of. It is type of `value` that `Key.split`
#: accepts, which is recursive across `collection.abc.Sequence`.
#:
#: This _used_ to be
#:
#:       KeyMatter = Union[
#:           "Key",
#:           str,
#:           bytes,
#:           type,
#:           ModuleType,
#:           # NOTE  It seems like this _should_ be `types.FunctionType`, but pylance
#:           #       doesn't like that. It seems ok with `typing.Callable` though.
#:           Callable,
#:           Sequence["KeyMatter"],
#:       ]
#:
#: but PyLance couldn't infer the `__new__(dict[KeyMatter, type[T]])` part, so
#: now it's just `typing.Any`, which seems to work.
#:
KeyMatter = Any

TKey = TypeVar("TKey", bound="Key")


def is_key_matter(x: object) -> TypeGuard[KeyMatter]:
    if isinstance(x, (Key, str, bytes, type, ModuleType, FunctionType)):
        return True
    if isinstance(x, Sequence):
        return all(is_key_matter(e) for e in x)
    return False


@total_ordering
class Key(Sequence[str], Generic[T]):
    """
    A configuration key.

    ##### Examples #####

    Keys can be empty.

    ```python
    >>> Key()
    Key()

    >>> len(Key())
    0

    ```

    Empty keys disappear when used as segments:

    ```python
    >>> Key(Key(), "a.b")
    Key('a', 'b')

    ```

    This is pretty much _just_ so that `Changeset` can have an empty
    `Changeset.prefix`, making a bit of code cleaner and clearer. Please don't
    abuse it.

    However, you _can't_ embed empty segments into string representations:

    ```python
    >>> Key(".a.b")
    Traceback (most recent call last):
        ...
    ValueError: each segment in a `key` must full-match [A-Za-z][A-Za-z0-9_]*,
        found '' in '.a.b'

    >>> Key("a..b")
    Traceback (most recent call last):
        ...
    ValueError: each segment in a `key` must full-match [A-Za-z][A-Za-z0-9_]*,
        found '' in 'a..b'

    ```
    """

    STRING_SEPARATOR = "."
    SEGMENT_FORMAT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

    @classmethod
    def is_segment(cls, x) -> bool:
        if isinstance(x, str) and cls.SEGMENT_FORMAT.fullmatch(x):
            return True
        return False

    @classmethod
    def normalize(cls, value: KeyMatter) -> Generator[str, None, None]:
        """
        Yield the normalized sequence of validated `Key` segment string for the
        given `value`. As it uses `Key.split` internally, accepts:

        1.  `str`
        2.  `bytes` -- decoded with UTF-8 to `str`
        3.  Class -- Fully qualified name (module + class name) is split (at the
            `.` separators).
        4.  Module -- Name is split at the `.` separators.
        5.  `typing.Iterable` containing any of the accepted types, including
            other iterables.

        **Raises**

        -   `ValueError` if any `str` segment does not conform to the segment
            pattern (see `Key.SEGMENT_FORMAT`).
        -   `TypeError` if `value` is not one of the accepted types listed above
            (via `Key.split`).
        -   `UnicodeDecodeError` if any element is a `bytes` instance that fails
            to decode as a utf-8 string (via `Key.split`).
        """
        for segment in cls.split(value):
            if cls.is_segment(segment):
                yield segment
            else:
                raise ValueError(
                    "each segment in a `key` must full-match "
                    f"{cls.SEGMENT_FORMAT.pattern}, found {repr(segment)} in "
                    f"{repr(value)}"
                )

    @classmethod
    def split(cls, value: KeyMatter) -> Generator[str, None, None]:
        """
        Recursively splits `value` according to `Key` semantics, yielding `str`
        elements. Accepts:

        1.  `str`
        2.  `bytes` -- decoded with UTF-8 to `str`
        3.  Class -- Fully qualified name (module + class name) is split (at the
            `.` separators).
        4.  Module -- Name is split at the `.` separators.
        5.  Function -- Full name is split by `.` separators.
        6.  `typing.Iterable` containing any of the accepted types, including
            other iterables.

        > 📝 NOTE
        > This method does _not_ validate the yielded `str` segments, it simply
        > splits them. Validation is handled when invoked through `normalize`.

        Raises

        -   `TypeError` if `value` is not one of the accepted types listed
            above.
        -   `UnicodeDecodeError` if any element is a `bytes` instance that fails
            to decode as a utf-8 string.

        ##### Examples #####

        Splits strings:

        ```python
        >>> list(Key.split("a.b.c"))
        ['a', 'b', 'c']

        ```

        Just to avoid dealing with the fact that they are `Iterable`, decodes
        `bytes` as `utf-8`:

        ```python
        >>> list(Key.split(b"a.b.c"))
        ['a', 'b', 'c']

        ```

        Recurs into `Iterable`:

        ```python
        >>> list(Key.split(["a.b", "c.d"]))
        ['a', 'b', 'c', 'd']

        ```

        Does what you (hopefully) want with classes:

        ```python
        >>> from pathlib import Path
        >>> list(Key.split(Path))
        ['pathlib', 'Path']

        ```

        Everyhing else barfs:

        ```python
        >>> list(Key.split(1))
        Traceback (most recent call last):
            ...
        TypeError: expected str, bytes, Iterable, class or module; given <class 'int'>: 1

        ```
        """

        if isinstance(value, str):
            yield from value.split(cls.STRING_SEPARATOR)
        elif isinstance(value, bytes):
            # Since `bytes` are a `Sequence`, need to do something about them
            # that makes more sense than dotting their integers together
            #
            # This will fail if `input` is does not decode into UTF-8
            yield from cls.split(value.decode("utf-8"))
        elif isinstance(value, Iterable):
            for v in value:
                yield from cls.split(v)
        elif isclass(value):
            # Allows you to use classes, like
            #
            #       import what.ever
            #       cfg[what.ever.SomeClass, "default_value"]
            #       -> Key("what", "ever", "SomeClass", "default_value")
            #
            yield from cls.split((value.__module__, value.__qualname__))
        elif ismodule(value):
            # Allows you to use modules, like
            #
            #       import what.ever
            #       cfg[what.ever, "default_value"]
            #       -> Key("what", "ever", "default_value")
            #
            yield from cls.split(value.__name__)
        elif isfunction(value):
            # Allows you to use functions much the same as classes and modules
            yield from cls.split((value.__module__, value.__qualname__))
        else:
            raise TypeError(
                "expected str, bytes, Iterable, class or module; "
                f"given {type(value)}: {repr(value)}"
            )

    @classmethod
    def parse_init_args(
        cls, args: tuple[Any, ...], kwds: dict[str, Any]
    ) -> tuple[KeyMatter, type[T]]:
        match (args, tuple(kwds.items())):
            # __new__(cls, __key: Key[T]) -> Key[T]

            case ((Key() as key,), ()):
                return key._parts, key._v_type

            # __new__(cls, __key_v_type: dict[KeyMatter, type[T]]) -> Key[T]

            case ((a_0,), ()) if isinstance(a_0, dict):
                match tuple(a_0.items()):
                    case (((parts,), v_type),) | (([parts], v_type),):
                        return parts, v_type

                    case ((parts, v_type),):
                        return parts, v_type

                raise TypeError("bad dict")

            # __new__(cls, *parts: KeyMatter, v_type: type[T]) -> Key[T]

            case ((parts,), (("v_type", v_type),)):
                return parts, v_type

            case (parts, (("v_type", v_type),)):
                return parts, v_type

            # __new__(cls, *parts: KeyMatter) -> Key[Any]

            case ((parts,), ()):
                return parts, Any

            case (parts, ()):
                return parts, Any
        raise TypeError("here'")

    @overload
    def __new__(cls, __key: Key[T]) -> Key[T]:
        ...

    @overload
    def __new__(cls, __key_v_type: dict[KeyMatter, type[T]]) -> Key[T]:
        ...

    @overload
    def __new__(cls, *parts: KeyMatter, v_type: type[T]) -> Key[T]:
        ...

    @overload
    def __new__(cls, *parts: KeyMatter) -> Key[Any]:
        ...

    def __new__(cls, *args, **kwds):
        """Construct a `Key`.

        Since keys are tuples, and tuples are immutable, an optimization is
        performed to simply return any sole `Key` instance argument.
        """
        # Special-case single argument calls
        # if len(values) == 1:
        #     if (
        #         isinstance(values[0], cls)
        #         and values[0]._value_type is value_type
        #     ):
        #         # Called with a single `Key`. Since they're immutable we just
        #         # return it back.
        #         return values[0]

        return super().__new__(cls)

    _v_type: type[T]
    _parts: tuple[str, ...]

    def __init__(self, *args, **kwds):
        parts, v_type = self.parse_init_args(args, kwds)
        self._parts = tuple(self.normalize(parts))
        self._v_type = v_type

    # Properties
    # ========================================================================

    @property
    def v_type(self) -> type[T]:
        return self._v_type

    @property
    def parts(self) -> tuple[str, ...]:
        return self._parts

    @property
    def env_name(self):
        """The environment variable name for a `Key`.

        Examples:

        We're just using `"_"` instead of `"."` to join the segments and
        upper-casing:

        ```python
        >>> Key("hey.ho.lets_go").env_name
        'HEY_HO_LETS_GO'

        >>> Key("clavier", "some", "setting").env_name
        'CLAVIER_SOME_SETTING'

        ```

        Notes that this process is **_ambiguous_**:

        ```python
        >>> ( Key("clavier", "some", "setting")
        ...   == Key("clavier", "some_setting") )
        False
        >>> ( Key("clavier", "some", "setting").env_name
        ...   == Key("clavier", "some_setting").env_name )
        True

        ```

        Only _you_ can prevent environment variable name collisions!
        """
        return "_".join(self).upper()

    @property
    def root(self) -> Key[Any]:
        """
        Get the root key.

        Examples:

        1.  Useful when with `__package__`

            ```python
            >>> Key("clavier.cfg").root
            Key('clavier')

            ```

        """
        if self.is_empty():
            raise IndexError("The empty Key has no root")
        return self.__class__(self[0], v_type=Any)

    # Dunders
    # ========================================================================

    def __repr__(self) -> str:
        """\
        Here.

        Examples:

        ```python
        >>> repr(Key("a"))
        "Key('a')"

        >>> repr(Key("a.b.c"))
        "Key('a', 'b', 'c')"

        ```
        """
        s = ", ".join(repr(s) for s in self._parts)

        if self._v_type is not Any:
            if isclass(self._v_type):
                s += f", v_type={self._v_type.__name__}"
            else:
                s += f", v_type={self._v_type!r}"

        return "Key(" + s + ")"

    def __str__(self):
        """\
        Here.

        Examples:

        ```python
        >>> str(Key("a"))
        'a'

        >>> str(Key("a", "b", "c"))
        'a.b.c'

        ```
        """
        return self.STRING_SEPARATOR.join(self)

    # Hashable
    # ------------------------------------------------------------------------

    def __hash__(self) -> int:
        return hash(self._parts)

    # Comparable
    # ------------------------------------------------------------------------

    def __lt__(self, __x: Key) -> bool:
        return self._parts < __x._parts

    def __le__(self, __x: Key) -> bool:
        return self._parts <= __x._parts

    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, Key) and self._parts == __o._parts

    def __gt__(self, __x: Key) -> bool:
        return self._parts > __x._parts

    def __ge__(self, __x: Key) -> bool:
        return self._parts >= __x._parts

    # `collections.abc.Sequence`
    # ------------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._parts)

    @overload
    def __getitem__(self, index: int) -> str:
        ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[str]:
        ...

    def __getitem__(self, index):
        return self._parts[index]

    # `/` Operator — `pathlib.Path`-Like Combination
    # ------------------------------------------------------------------------

    def __truediv__(self: TKey, key) -> TKey:
        """
        Support extending a key using the `/` operator, like `pathlib.Path`.

        ##### Examples #####

        ```python
        >>> Key("a.b") / "c"
        Key('a', 'b', 'c')

        >>> Key("a.b") / "c.d" / "e"
        Key('a', 'b', 'c', 'd', 'e')

        >>> Key("a.b") / Key("c.d")
        Key('a', 'b', 'c', 'd')

        ```
        """
        return self.extend(key)

    def __rtruediv__(self: TKey, key) -> TKey:
        """
        Support prepending a key using the `/` operator, like `pathlib.Path`.

        ##### Examples #####

        ```python
        >>> "a.b" / Key("c")
        Key('a', 'b', 'c')

        >>> "a.b" / Key("c", v_type=int)
        Key('a', 'b', 'c', v_type=int)

        ```
        """
        return self.prepend(key)

    # Custom API
    # ============================================================================

    def is_empty(self) -> bool:
        """\
        Is this key empty?

        Examples:

        ```python
        >>> Key().is_empty()
        True

        >>> Key("a.b.c").is_empty()
        False

        ```
        """
        return len(self) == 0

    def has_scope(self, scope: Key) -> bool:
        if len(scope) >= len(self):
            return False

        for k_1, k_2 in zip(self, scope):
            if k_1 != k_2:
                return False

        return True

    def scopes(self) -> Generator[Key["Scope"], None, None]:
        """
        Yield a each key-scope that this `Key` belongs to, which have a `v_type`
        of `Scope`.

        ##### Examples #####

        ```python
        >>> list(Key("a.b.c.d").scopes())
        [Key('a', v_type=Scope),
            Key('a', 'b', v_type=Scope),
            Key('a', 'b', 'c', v_type=Scope)]

        ```

        It's always true that

            len(list(k.scopes())) == len(k) - 1

        for any key _non-empty_ `k`.

        Empty keys have no scopes:

        ```python
        >>> list(Key().scopes()) == []
        True

        ```

        Same as keys of length 1:

        ```python
        >>> list(Key("blah").scopes()) == []
        True

        ```
        """
        from .scope import Scope

        for stop in range(1, len(self)):
            yield cast(Key[Scope], self.__class__(self[0:stop], v_type=Scope))

    # Modifying Keys
    # ------------------------------------------------------------------------
    #
    # As keys are immutable, all methods return a _new_ instance.
    #

    @overload
    def append(self, __key: Key[V]) -> Key[V]:
        ...

    @overload
    def append(self, __key_v_type: dict[KeyMatter, type[V]]) -> Key[V]:
        ...

    @overload
    def append(self, *parts: KeyMatter, v_type: type[V]) -> Key[V]:
        ...

    @overload
    def append(self, *parts: KeyMatter) -> Key[Any]:
        ...

    def append(self, *args, **kwds):
        """
        Add to the end of a key. `v_type` assumed from the appended key, unless
        specified.

        ##### Examples #####

        ```python
        >>> Key("a.b").append("c")
        Key('a', 'b', 'c')

        >>> Key("a.b").append("c.d", "e")
        Key('a', 'b', 'c', 'd', 'e')

        ```

        The _value type_ (`v_type`) of the resulting key assumes the
        _value type_ of the appended key (opposite of how `prepend` works),
        unless a new _value type_ is specified (same forms as `__new__`).

        ```python
        >>> Key("a.b").append("c").v_type
        typing.Any

        >>> Key("a.b").append(Key("c", v_type=int))
        Key('a', 'b', 'c', v_type=int)

        >>> Key("a.b").append("c.d", "e", v_type=int)
        Key('a', 'b', 'c', 'd', 'e', v_type=int)

        >>> Key("a.b").append({('c.d', 'e'): int})
        Key('a', 'b', 'c', 'd', 'e', v_type=int)

        ```

        """
        parts, v_type = self.parse_init_args(args, kwds)
        return cast(Key[V], self.__class__(self, parts, v_type=v_type))

    #: Support alternative name for `append`, similar to `list`.
    #:
    #: Due to how `normalize` works the difference between `list.append` (takes
    #: a single entry) and `list.extend` (takes an iterable of entries) is not
    #: present so we can simple alias one to the other.
    #:
    extend = append

    def prepend(self, *key: KeyMatter) -> Key[T]:
        """
        Add to the begining of a key. `v_type` assumed from this key, unless
        specified.

        ##### Examples #####

        ```python
        >>> Key("c.d").prepend("a.b")
        Key('a', 'b', 'c', 'd')

        >>> Key("d").prepend(Key("a"), Key("b.c"))
        Key('a', 'b', 'c', 'd')

        ```
        """
        return self.__class__(key, self, v_type=self._v_type)

    def select(self, predicate: Callable[[str], Any]) -> Key[T]:
        return Key(
            *(part for part in self._parts if predicate(part)),
            v_type=self.v_type,
        )

    def reject(self, predicate: Callable[[str], Any]) -> Key[T]:
        return Key(
            *(part for part in self._parts if not predicate(part)),
            v_type=self.v_type,
        )

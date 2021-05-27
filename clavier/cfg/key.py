from __future__ import annotations
from typing import Generator, Iterable
import re

class Key(tuple):
    """
    A key.

    Examples:

    Keys can be empty:

        >>> Key()
        Key()
        >>> len(Key())
        0

    Empty keys disappear when used as segments:

        >>> Key(Key(), "a.b")
        Key('a', 'b')

    This is pretty much _just_ so that `Changeset` can have an empty
    `.prefix`, making a bit of code cleaner and clearer. Please don't abuse
    it.

    However, you _can't_ embed empty segments into string representations:

        >>> Key(".a.b")
        Traceback (most recent call last):
            ...
        ValueError: Each segment in a `key` must full-match [A-Za-z][A-Za-z0-9_]*, found '' in '.a.b'

        >>> Key("a..b")
        Traceback (most recent call last):
            ...
        ValueError: Each segment in a `key` must full-match [A-Za-z][A-Za-z0-9_]*, found '' in 'a..b'

    """

    STRING_SEPARATOR = "."
    SEGMENT_FORMAT = re.compile(r"[A-Za-z][A-Za-z0-9_]*")

    @classmethod
    def is_segment(cls, x) -> bool:
        if isinstance(x, str) and cls.SEGMENT_FORMAT.fullmatch(x):
            return True
        return False

    @classmethod
    def normalize(cls, value):
        for segment in cls.split(value):
            if cls.is_segment(segment):
                yield segment
            else:
                raise ValueError(
                    "Each segment in a `key` must full-match "
                    f"{cls.SEGMENT_FORMAT.pattern}, found {repr(segment)} in "
                    f"{repr(value)}"
                )

    @classmethod
    def split(cls, value):
        """\
        Yield key segment `str`.

        Examples:

        Splits strings:

            >>> list(Key.split("a.b.c"))
            ['a', 'b', 'c']

        Just to avoid dealing with the fact that they are `Iterable`, decodes
        `bytes` as `utf-8`:

            >>> list(Key.split(b"a.b.c"))
            ['a', 'b', 'c']

        Recurs into `Iterable`:

            >>> list(Key.split(["a.b", "c.d"]))
            ['a', 'b', 'c', 'd']

        Does what you (hopefully) want with classes:

            >>> from pathlib import Path
            >>> list(Key.split(Path))
            ['pathlib', 'Path']

        Everyhing else barfs:

            >>> list(Key.split(1))
            Traceback (most recent call last):
                ...
            TypeError: Expected str, bytes, Iterable or class, given <class 'int'>: 1

        """
        # print(f"HERE {repr(value)}")
        if isinstance(value, str):
            yield from value.split(cls.STRING_SEPARATOR)
        elif isinstance(value, bytes):
            # Since `bytes` are a `Sequence`, need to do something about them
            # that makes more sense than dotting their integers together
            #
            # This will fail if `input` is does not decode into UTF-8
            yield from cls.normalize(value.decode("utf-8"))
        elif isinstance(value, Iterable):
            for v in value:
                yield from cls.normalize(v)
        elif hasattr(value, "__module__") and hasattr(value, "__name__"):
            # Allows you to use classes, like
            #
            #       cfg[what.ever.SomeClass, "default_value"]
            #       -> Key("what", "ever", "SomeClass", "default_value")
            #
            yield from cls.split((value.__module__, value.__name__))
        else:
            raise TypeError(
                "Expected str, bytes, Iterable or class, "
                f"given {type(value)}: {repr(value)}"
            )

    def __new__(self, *values):
        if len(values) == 1 and isinstance(values[0], self.__class__):
            return values[0]
        return tuple.__new__(Key, self.normalize(values))

    @property
    def env_name(self):
        """\
        The environment variable name for a `Key`.

        Examples:

        We're just using `"_"` instead of `"."` to join the segments and
        upper-casing:

            >>> Key("hey.ho.lets_go").env_name
            'HEY_HO_LETS_GO'

            >>> Key("clavier", "some", "setting").env_name
            'CLAVIER_SOME_SETTING'

        Notes that this process is **_ambiguous_**:

            >>> ( Key("clavier", "some", "setting")
            ...   == Key("clavier", "some_setting") )
            False
            >>> ( Key("clavier", "some", "setting").env_name
            ...   == Key("clavier", "some_setting").env_name )
            True

        Only _you_ can prevent environment variable name collisions!
        """
        return "_".join(self).upper()

    @property
    def root(self) -> Key:
        """
        Get the root key.

        Examples:

        1.  Useful when with `__package__`

            >>> Key("clavier.cfg").root
            Key('clavier')

        """
        if self.is_empty():
            raise IndexError("The empty Key has no root")
        return self.__class__(self[0])

    def __repr__(self) -> str:
        """\
        Here.

        Examples:

            >>> repr(Key("a"))
            "Key('a')"

            >>> repr(Key("a.b.c"))
            "Key('a', 'b', 'c')"

        """
        return "Key(" + ', '.join(repr(s) for s in self) + ")"

    def __str__(self):
        """\
        Here.

        Examples:

            >>> str(Key("a"))
            'a'

            >>> str(Key("a", "b", "c"))
            'a.b.c'

        """
        return self.STRING_SEPARATOR.join(self)

    def is_empty(self):
        """\
        Is this key empty?

        Examples:

            >>> Key().is_empty()
            True

            >>> Key("a.b.c").is_empty()
            False

        """
        return len(self) == 0

    def scopes(self) -> Generator[Key, None, None]:
        """\
        Yield a each key-scope that this `Key` belongs to.

            >>> list(Key("a.b.c.d").scopes())
            [Key('a'), Key('a', 'b'), Key('a', 'b', 'c')]

        It's always true that

            len(list(k.scopes())) == len(k) - 1

        for any key _non-empty_ `k`.

        Empty keys have no scopes:

            >>> list(Key().scopes()) == []
            True

        Same as keys of length 1:

            >>> list(Key("blah").scopes()) == []
            True

        """
        for stop in range(1, len(self)):
            yield Key(self[0:stop])

if __name__ == '__main__':
    from pathlib import Path
    import doctest
    doctest.testmod()

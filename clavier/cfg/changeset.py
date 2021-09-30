from __future__ import annotations
from typing import Any

from .key import Key
from .scope import ReadScope, WriteScope


class Changeset:
    """\
    A runtime object used to create a `Config.Update` in Python code. This is
    what is used under-the-hood when configuring in a source file.

    You don't use this class directly; it's an intermediary between the
    `Config` and various `WriteScope` instances that are used to set values.

    Intended use:

        >>> from clavier import CFG
        >>> with CFG.configure("stats.doctest", src=__file__) as c:
        ...     c.x = "ex"
        ...     c.y = "why?"
        ...
        >>> CFG.stats.doctest.x
        'ex'
        >>> CFG.stats.doctest.y
        'why?'

    In that example, `c` is a `WriteScope` with `._key` of
    `Key("stats", "doctests")`. `c._base` is the internal `Changeset`, which
    references back to the `Config` via `c._base.config`.
    """

    def __init__(self, config, prefix, meta):
        self.config = config
        self.prefix = Key(prefix)
        self.meta = meta
        self.changes = {}
        self.write_scope = None

    def __contains__(self, key: Any) -> bool:
        try:
            key = Key(key)
        except Exception:
            return False
        return key in self.changes or key in self.config

    def __getitem__(self, key):
        try:
            key = Key(key)
        except KeyError as error:
            raise error
        except Exception as error:
            raise KeyError(f"Not convertible to a Key: {repr(key)}") from error

        # 1.  See if we have a value for the key...

        # ENV overrides _always_ win. We need this so that value composition
        # correctly uses the ENV overrides.
        if self.config.env_has(key):
            return self.config.env_get(key)

        # Next, anything already written as a change, as those take priority
        # over anything previously stored in the `Config`.
        if key in self.changes:
            return self.changes[key]

        # Then anything already in the config.
        if key in self.config:
            return self.config[key]

        # 2.  The exact key doesn't exists, but we may want to return scope,
        #     allowing nested access...

        # If `key` represents a scope we have changes to, ok. Note this this is
        # only a `ReadScope` for reading values, not a `WriteScope`.
        for k in self.changes:
            if key in k.scopes():
                return ReadScope(base=self, key=key)

        # The config might have a scope for us too
        for k in self.config:
            if key in k.scopes():
                return ReadScope(base=self, key=key)

        # 3. ...and that's it, nothing more we can do.
        raise KeyError(f"Key not found: {repr(key)}")

    def __setitem__(self, key, value):
        key = Key(key)
        if key.is_empty():
            raise KeyError(
                f"Can not set value for empty key; value: {repr(value)}"
            )
        # Items are always set in the changes
        self.changes[key] = value

    def __enter__(self):
        return WriteScope(base=self, key=self.prefix)

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if exc_type is None and exc_value is None and traceback is None:
            self.config.update(self.changes, self.meta)


if __name__ == "__main__":
    import doctest

    doctest.testmod()

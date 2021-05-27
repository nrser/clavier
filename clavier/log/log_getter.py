"""Defines `LogGetter` class."""

from functools import wraps
import logging
from typing import Any

from clavier.etc.ins import is_unbound_method_of

class LogGetter:
    """\
    Proxy to `logging.Logger` instance that defers construction until use.

    This allows things like:

        LOG = logging.getLogger(__name__)

    at the top scope in files, where it is processed _before_ `setup()` is
    called to switch the logger class. Otherwise, those global definitions would
    end up being regular `logging.Logger` classes that would not support the
    "keyword" log method signature we prefer to use.

    See `KwdsLogger` and `getLogger`.
    """

    name: str

    def __init__(self, *name: str):
        self.name = ".".join(name)

    @property
    def _logger(self) -> logging.Logger:
        return logging.getLogger(self.name)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._logger, name)

    def getChild(self, name):
        return LogGetter(f"{self.name}.{name}")

    def inject(self, fn):
        @wraps(fn)
        def log_inject_wrapper(*args, **kwds):
            if len(args) == 0:
                return fn(self.getChild(fn.__name__), **kwds)

            # See if this is a method call, where we need to deal with the
            # _second_ argument
            insert_at = 1 if is_unbound_method_of(fn, args[0]) else 0

            pre_args = args[0:insert_at]
            post_args = args[insert_at:]

            if len(post_args) == 0:
                # There are no regular args, so there can't be an overriding
                # logger given as the first regular arg.
                #
                # Inject as the (only) regular arg
                return fn(*pre_args, self.getChild(fn.__name__), **kwds)

            if isinstance(post_args[0], (self.__class__, logging.Logger)):
                # The first regular arg is a `LogGetter` or `logging.Logger`,
                # so no injection this time
                return fn(*args, **kwds)

            # And finally, the first regular arg is not an logger override,
            # so inject in there and be done with it
            return fn(*pre_args, self.getChild(fn.__name__), *post_args, **kwds)

        return log_inject_wrapper

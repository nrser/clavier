"""Defines `KwdsLogger` class."""

from __future__ import annotations
import logging
from typing import (
    Any,
    Optional,
    Mapping,
)

class KwdsLogger(logging.Logger):
    """\
    A `logging.Logger` extension that overrides the `logging.Logger._log` method
    the underlies all "log methods" (`logging.Logger.debug`,
    `logging.Logger.info`, etc) to treat the double-splat keyword arguments
    as a map of names to values to be logged.

    This map is added as `"data"` to the `extra` mapping that is part of the
    log method API, where it eventually is assigned as a `data` attribute
    on the emitted `logging.LogRecord`.

    This allows logging invocations like:

        logger.debug(
            "Check this out!",
            x="hey,
            y="ho",
            z={"lets": "go"},
        )

    which I (obviously) like much better.
    """

    def _log(
        self: KwdsLogger,
        level: int,
        msg: Any,
        args,
        exc_info=None,
        extra: Optional[Mapping]=None,
        stack_info=False,
        **data,
    ) -> None:
        """
        Override to treat double-splat as a `"data"` extra.

        See `KwdsLogger` doc for details.
        """

        if extra is not None:
            # This will fail if you give a non-`None` value that is not a
            # `Mapping` as `extra`, but it would have failed in
            # `logging.Logger.makeRecord` in that case anyways, so might as well
            # blow up here and save a cycle or two.
            extra = {"data": data, **extra}
        else:
            extra = {"data": data}

        super()._log(
            level,
            msg,
            args,
            exc_info=exc_info,
            stack_info=stack_info,
            extra=extra,
        )


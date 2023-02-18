"""The `Sesh` class."""

from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from typing import (
    Any,
    NamedTuple,
    NoReturn,
    ParamSpec,
    Sequence,
    TypeVar,
)
from pathlib import Path
import argparse
import sys
from contextvars import Context
import signal


import splatlog
from rich.console import Console
from rich.repr import RichReprResult

from . import err, io, cfg, etc
from .arg_par import ArgumentParser
from .arg_par.argument_parser import TARGET_NAME, Setting, Target, check_target

from .req import Req

_LOG = splatlog.get_logger(__name__)

T = TypeVar("T")
TParams = ParamSpec("TParams")


class _ErrorContext(NamedTuple):
    message: str
    expect_system_exit: bool = False


error_context = etc.ctx.ContextVarManager(
    name="error_context",
    constructor=_ErrorContext,
    default=_ErrorContext("(unknown)", False),
    reset_on_error=False,
)


class Sesh:
    """
    A CLI app session
    """

    _log = splatlog.LoggerProperty()

    _pkg_name: str
    _parser: ArgumentParser
    _args: argparse.Namespace | None = None
    _init_cmds: Any
    _context: Context

    def __init__(
        self: Sesh,
        pkg_name: str,
        description: str | Path,
        cmds: Any,
        parser: ArgumentParser | None = None,
        prog_name: str | None = None,
        autocomplete: bool = True,
        setup_logging: bool = True,
    ):
        self._pkg_name = pkg_name
        self.description = description
        self._init_cmds = cmds
        self._context = cfg.current.create_derived_context(name="session")

        if setup_logging:
            self.setup_logging()

        if parser is None:
            self._parser = ArgumentParser.create(
                self.description,
                self.init_cmds,
                autocomplete=autocomplete,
                prog=pkg_name if prog_name is None else prog_name,
                settings=self.get_parser_settings(),
            )
        else:
            self._parser = parser

    @property
    def _splatlog_self_(self) -> Any:
        return splatlog.lib.rich.REPR_HIGHLIGHTER(f"<Sesh {self._parser.prog}>")

    @property
    def pkg_name(self) -> str:
        return self._pkg_name

    @property
    def args(self):
        if self._args is None:
            raise err.InternalError("Must `parse()` first to populate `args`")
        return self._args

    @property
    def init_cmds(self) -> Any:
        return self._init_cmds

    @property
    def parser(self) -> ArgumentParser:
        return self._parser

    def get_target(self, args: argparse.Namespace) -> Target:
        try:
            return check_target(getattr(args, TARGET_NAME))
        except err.InternalError:
            raise
        except Exception as error:
            raise err.InternalError("Failed to get target") from error

    def get_app_setting_key(self, name: str, v_type: type[T]) -> cfg.Key[T]:
        return cfg.Key(self.pkg_name, name, v_type=v_type)

    def get_lib_setting_key(self, name: str, v_type: type[T]) -> cfg.Key[T]:
        return cfg.Key(cfg.SELF_ROOT_KEY, name, v_type=v_type)

    def get_setting(self, name: str, v_type: type[T]) -> T:
        config = cfg.current._get_parent_()

        app_key = self.get_app_setting_key(name, v_type)

        if app_key in config:
            return config[app_key]

        return config[self.get_lib_setting_key(name, v_type)]

    def is_backtracing(self) -> bool:
        return self.get_setting("backtrace", bool)

    def get_parser_settings(self) -> Sequence[Setting]:
        return [
            Setting(
                key=self.get_app_setting_key("backtrace", bool),
                flags=("-B", "--backtrace"),
                action="store_true",
                propagate=True,
                help="Print backtrace on error.",
            ),
            Setting(
                key=self.get_app_setting_key("verbosity", int),
                flags=("-V", "--verbose"),
                action="count",
                propagate=True,
                help="Make noise. Repeat for more noise.",
            ),
            Setting(
                key=self.get_app_setting_key("output", str),
                flags=("-O", "--output"),
                propagate=True,
                help=io.View.help(),
            ),
        ]

    def get_parser_setting(self, name: str) -> Setting | None:
        key = self.get_app_setting_key(name, Any)
        return etc.iter.find(lambda s: s.key == key, self.get_parser_settings())

    def setup_logging(
        self, verbosity: None | splatlog.Verbosity = None
    ) -> Sesh:
        """This has really become "setup logging"."""
        if verbosity is None:
            verbosity = self.get_setting("verbosity", splatlog.Verbosity)

        console = Console(
            file=sys.stderr,
            color_system="truecolor",
            force_terminal=True,
        )

        splatlog.setup(
            console=console,
            verbosity_levels={
                self.pkg_name: (
                    (0, splatlog.WARNING),
                    (1, splatlog.INFO),
                    (2, splatlog.DEBUG),
                ),
                splatlog.root_name(__package__): (
                    (0, splatlog.WARNING),
                    (3, splatlog.INFO),
                    (4, splatlog.DEBUG),
                ),
            },
            verbosity=verbosity,
        )

        return self

    def parse(
        self,
        argv: Sequence[str] | None = None,
    ) -> Req:
        return self._context.run(self._parse, argv)

    def _parse(
        self,
        argv: Sequence[str] | None = None,
    ) -> Req:
        _argv = sys.argv[1:] if argv is None else argv

        with error_context("parsing arguments"):
            args = self.parser.parse_args(_argv)

        with error_context("constructing request"):
            request = Req(
                argv=tuple(_argv),
                args=args,
            )

        splatlog.set_verbosity(
            self.get_setting("verbosity", splatlog.Verbosity)
        )

        self._log.debug("Parsed arguments", request=request)
        return request

    def handle(self, request: Req) -> int:
        return self._context.run(self._handle, request)

    def _handle(self, request: Req) -> int:
        with error_context(
            f"executing {etc.txt.fmt(request.target)}", expect_system_exit=True
        ):
            if request.is_async:
                result = asyncio.run(request.target(**request.kwds))
            else:
                result = request.target(**request.kwds)

        view = result if isinstance(result, io.View) else io.View(result)

        return self._render_view(view)

    def _render_view(self, view: io.View) -> int:
        with error_context(f"rendering view {etc.txt.fmt_type_of(view)}"):
            try:
                view_format = self.get_setting("output", str)
                view.render(view_format)

            except (asyncio.CancelledError, KeyboardInterrupt):
                return self.exit_status_for_signal(signal.SIGINT)

            except BaseException as error:
                # Check if we were doing our own view rendering
                if isinstance(view, io.views.SeshView):
                    # Ok, we were. In this case we do **not** want to go back
                    # in to `handle_error` because we might cause an infinite
                    # loop.
                    #
                    # Our views are never supposed to raise, but, well, here we
                    # are. Until we figure something better out just let it
                    # fly on up and get nasty I guess.
                    #
                    raise err.InternalError(
                        "failed to render internal view {}".format(
                            view.__class__.__qualname__
                        )
                    ) from error

                return self.handle_error(error)

            return view.exit_status

    @classmethod
    def exit_status_for_signal(cls, signal_number: int) -> int:
        """What exit status to return when exiting due to receiving a singal.

        In practice for us this means an _interput_ signal, usually issued by a
        user byt pressing `ctrl+c`. Here _interupt_ means:

        1.  A `signal.SIGINT` signal, which we pick up by way of a
            `KeyboardInterput` error.

        2.  A `asyncio.CancelledError`, since it seems just from messing around
            that these can show up when handling interupts in async code?

        Anyways, what to return when exiting from a signal; is, of course, kinda
        a mess:

        https://unix.stackexchange.com/a/386856

        This implementation just assumes a `bash` shell and returns

            128 + signal_number

        which should be `130` in the case of `signal.SIGINT`.
        """
        return 128 + signal_number

    def handle_error(self, error: BaseException) -> int:
        context_message, expect_system_exit = error_context.get_and_reset()

        match error:
            case asyncio.CancelledError() | KeyboardInterrupt():
                exit_status = self.exit_status_for_signal(signal.SIGINT)

                self._log.debug(
                    "Interupted while {}, exiting...",
                    context_message,
                    exit_status=exit_status,
                    exc_info=self.is_backtracing(),
                )

                return exit_status

            case err.ParserExit():
                return self._render_view(
                    io.views.ParserExitView(self, error, context_message)
                )

            case SystemExit():
                if not expect_system_exit:
                    level = (
                        splatlog.WARNING if error.code == 0 else splatlog.ERROR
                    )

                    self._log.log(
                        level,
                        "System exit during {}",
                        context_message,
                        code=error.code,
                        exc_info=self.is_backtracing(),
                    )

                # `SystemExit.code` is not necessarily an exit status `int`; in
                # the case of `sys.exit(str)` it will be the given string.
                #
                return error.code if isinstance(error.code, int) else 1

            case _:
                return self._render_view(
                    io.views.SeshErrorView(
                        self,
                        error,
                        context_message,
                    )
                )

    def execute(self, argv: Sequence[str] | None = None) -> int:
        return self._context.run(self._execute, argv)

    def _execute(self, argv: Sequence[str] | None = None) -> int:
        try:
            req = self._parse(argv)
            return self._handle(req)

        except BaseException as error:
            return self.handle_error(error)

    def takeover(self, argv: Sequence[str] | None = None) -> NoReturn:
        sys.exit(self._context.run(self._execute, argv))

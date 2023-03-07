"""The `App` class."""

from __future__ import annotations
import asyncio
from dataclasses import dataclass
import os
from typing import (
    Any,
    NamedTuple,
    NoReturn,
    ParamSpec,
    Sequence,
    TypeVar,
    cast,
)
from pathlib import Path
import argparse
import sys
from contextvars import Context
import signal


import splatlog
from rich.console import Console

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


class App:
    """
    Top-level object for a Calvier application. In general they accept command
    line arguments (_argv_) and execute commands, returning results.

    In the network server metaphor, this is the _app_ or _server_ that accepts
    _requests_ and returns _responses_.

    This used to be called "Sesh" for "session", but it kept feeling more
    natural as the package and documentation evolved to refer to it as the "app",
    so it was renamed.

    As a piece of such heritage, there _should_ be nothing fundamentally
    stopping you from instantiating multiple of 'em and running them
    simultaneously, though this doesn't seems to be a use case that really comes
    up outside of testing, and I can't say it's well tested.
    """

    _log = splatlog.LoggerProperty()

    _name: str
    _parser: ArgumentParser
    _args: argparse.Namespace | None = None
    _init_cmds: Any
    _context: Context
    _is_server: bool = False

    def __init__(
        self,
        name: str,
        description: str | Path,
        cmds: Any,
        parser: ArgumentParser | None = None,
        autocomplete: bool = True,
        setup_logging: bool = True,
    ):
        """
        Construct a Clavier application instance.

        ##### Parameters #####

        -   `name` — The name of the application, which is generally used as the
            name of of the executable to invoke it, and generally the name of
            the

        """

        self._name = name
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
                prog=name,
                settings=self.get_parser_settings(),
            )
        else:
            self._parser = parser

    @property
    def _splatlog_self_(self) -> Any:
        return splatlog.lib.rich.REPR_HIGHLIGHTER(
            f"<{self.__class__.__qualname__} {self._parser.prog}>"
        )

    @property
    def name(self) -> str:
        return self._name

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
        return cfg.Key(self.name, name, v_type=v_type)

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

    def setup_logging(self, verbosity: None | splatlog.Verbosity = None) -> App:
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
                self.name: (
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
        argv = sys.argv[1:] if argv is None else argv

        self._log.info("Parsing arguments...", argv=argv)

        with error_context("parsing arguments"):
            args = self.parser.parse_args(argv)

        with error_context("constructing request"):
            request = Req(
                argv=tuple(argv),
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
        self._log.info("Handling request...", request=request)

        with error_context(
            f"executing {etc.txt.fmt(request.target)}", expect_system_exit=True
        ):
            if request.is_async:
                result = asyncio.run(request())
            else:
                result = request()

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
                if isinstance(view, io.views.AppView):
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

            case err.ReplaceProcess():
                if self._is_server:
                    raise
                self._replace_process(error)

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
                    io.views.AppErrorView(
                        self,
                        error,
                        context_message,
                    )
                )

    def _replace_process(self, rep_proc: err.ReplaceProcess) -> NoReturn:
        if rep_proc.cwd is not None:
            os.chdir(rep_proc.cwd)

        # NOTE  I _think_ — from poor-ass memory — that it was difficult
        #       to find examples of how to use these, and that this
        match (rep_proc.env, rep_proc.is_abs_path):
            case (None, True):
                os.execv(rep_proc.program, rep_proc.cmd)
            case (None, False):
                os.execvp(rep_proc.process_name, rep_proc.cmd)
            case (env, True):
                os.execve(
                    rep_proc.program, rep_proc.cmd, cast(dict[str, str], env)
                )
            case (env, False):
                os.execvpe(
                    rep_proc.process_name,
                    rep_proc.cmd,
                    cast(dict[str, str], env),
                )

        assert False, "unreachable"

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

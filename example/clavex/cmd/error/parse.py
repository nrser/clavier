from argparse import Action, Namespace
import sys
from textwrap import dedent
from typing import Any, NoReturn, Sequence

import splatlog
from clavier import arg_par, cfg

_LOG = splatlog.get_logger(__name__)


class RaiseParsing(Action):
    def __init__(self, *args, **kwds):
        super().__init__(*args, nargs=0, **kwds)

    def __call__(
        self,
        parser: arg_par.ArgumentParser,
        namespace: Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> NoReturn:
        raise Exception("Raised during parsing")


class ExitParsing(Action):
    def __init__(self, *args, **kwds):
        super().__init__(*args, nargs=1, **kwds)

    def __call__(
        self,
        parser: arg_par.ArgumentParser,
        namespace: Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> NoReturn:
        match values:
            case [str(s)] | (str(s)) | str(s):
                try:
                    status = int(s)
                except:
                    parser.exit(message=s)
                else:
                    parser.exit(
                        status=status,  # message=f"Exited with status {status}"
                    )
            case other:
                parser.exit(message=f"Unexpected `values`: {other!r}")


class SysExitParsing(Action):
    def __init__(self, *args, **kwds):
        super().__init__(*args, nargs=1, **kwds)

    def __call__(
        self,
        parser: arg_par.ArgumentParser,
        namespace: Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> NoReturn:
        match values:
            case [str(s)] | (str(s)) | str(s):
                try:
                    status = int(s)
                except:
                    sys.exit(s)
                else:
                    sys.exit(status)
            case other:
                sys.exit(f"Unexpected `values`: {other!r}")


def add_parser(subparsers: arg_par.Subparsers) -> None:
    parser = subparsers.add_parser(
        "parse",
        target=run,
        help="""
            Generate errors during argument parsing (during
            `argparse.ArgumentParser.parse_args`).
        """,
    )

    parser.add_argument(
        "--raise",
        action=RaiseParsing,
        help="""
            Raise an exception while parsing (in `argparse.Action.__call__`).
        """,
    )

    parser.add_argument(
        "--exit",
        action=ExitParsing,
        help="""
            Exit (calling `parser.exit`) during parsing (like the built-in
            `--help` action does).

            If the argument is an integer it is used as the exit status with a
            message saying so. Otherwise the argument is used as the exit
            message (with the default status of `0`).

            Note that this argument takes _immediate_ action (like `--help`), so
            no further arguments will be processed.
        """,
    )

    parser.add_argument(
        "--sys-exit",
        action=SysExitParsing,
        help="""
            Exit by calling `sys.exit` (and hence raising `SystemExit`).

            This doesn't seem like the _right_ way for parser actions to
            jettison (which would be calling `argparse.ArgumentParser.exit` or
            `argparse.ArgumentParser.error`), but a parser action _could_ of
            course do so (if it wanted to be annoying, I guess).
        """,
    )


def run():
    raise NotImplementedError()

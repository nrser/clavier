import splatlog

from clavier import arg_par


LOG = splatlog.get_logger(__name__)


def add_parser(subparsers: arg_par.Subparsers) -> None:
    parser = subparsers.add_parser(
        "sub-command-2",
        target=run,
        help="Another subcommand",
    )


def run():
    return "We #2!"

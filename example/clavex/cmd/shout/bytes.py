import splatlog
from clavier import arg_par, cfg

_LOG = splatlog.get_logger(__name__)


def add_parser(subparsers: arg_par.Subparsers) -> None:
    parser = subparsers.add_parser(
        "bytes",
        target=run,
        help="""
            Exercise the `clavier.sh` "shell-out" functions with `bytes`
            instances in the args/env.
        """,
    )


def run():
    raise NotImplementedError()

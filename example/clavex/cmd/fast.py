import splatlog
from clavier import arg_par

_LOG = splatlog.get_logger(__name__)


def add_parser(subparsers: arg_par.Subparsers) -> None:
    parser = subparsers.add_parser(
        "fast",
        target=run,
        help="""
            Do something that doesn't take much time.

            Just prints out the option values.
        """,
    )

    parser.add_argument(
        "-x",
        "--ex",
        help="Gon' give it to ya",
    )

    parser.add_argument(
        "-y",
        "--why",
        help="You always frontin'",
    )


def run(ex: str = "dx", why: str = "dy"):
    return (ex, why)

import splatlog
from clavier import arg_par
from .error_consts import ERROR_TYPES

_LOG = splatlog.get_logger(__name__)


def add_parser(subparsers: arg_par.Subparsers) -> None:
    parser = subparsers.add_parser(
        "target",
        target=run,
        help="""Raise an error while executing the command target""",
    )

    parser.add_argument(
        "-m",
        "--message",
        help="Set the error message",
    )

    parser.add_argument(
        "-t",
        "--type",
        dest="error_type_key",
        metavar="ERROR_TYPE",
        choices=tuple(ERROR_TYPES.keys()),
        help="Select the type of exception to be raised",
    )


def run(
    message: str = "default message, set with -m | --message",
    error_type_key: str = "runtime",
):
    error_type = ERROR_TYPES[error_type_key]
    raise error_type(message)

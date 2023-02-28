import splatlog
from clavier import arg_par, io
from .error_consts import ERROR_TYPES

_LOG = splatlog.get_logger(__name__)


def add_parser(subparsers: arg_par.Subparsers) -> None:
    parser = subparsers.add_parser(
        "render",
        target=run,
        help="""Raise an error while rendering the view""",
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


class View(io.View[tuple[str, type[BaseException]]]):
    def render_rich(self) -> None:
        message, error_type = self.data
        raise error_type(message)


def run(
    message: str = "default message, set with -m | --message",
    error_type_key: str = "runtime",
):
    error_type = ERROR_TYPES[error_type_key]
    return View((message, error_type))

import splatlog
from clavier import arg_par, cfg

_LOG = splatlog.get_logger(__name__)


def add_parser(subparsers: arg_par.Subparsers) -> None:
    parser = subparsers.add_parser(
        "action",
        target=run,
        help="""Demonstration and edge case action helps""",
    )

    parser.add_argument(
        "--long-long-really-long-option",
        help="Will it break the rendering...?",
        default="yes",
    )

    parser.add_argument(
        "--a-lot",
        "--of-different",
        "--options",
        help="Will it break the rendering...?",
        default="yes",
    )


def run():
    raise NotImplementedError()

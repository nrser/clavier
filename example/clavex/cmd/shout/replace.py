import splatlog
from clavier import arg_par, cfg, sh

_LOG = splatlog.get_logger(__name__)


def add_parser(subparsers: arg_par.Subparsers) -> None:
    parser = subparsers.add_parser(
        "replace",
        target=run,
        help="""replace the process""",
    )


def run():
    sh.replace("poetry", "run", "python")

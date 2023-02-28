import splatlog
from clavier import arg_par, cfg

_LOG = splatlog.get_logger(__name__)


def add_parser(subparsers: arg_par.Subparsers) -> None:
    parser = subparsers.add_parser(
        "config",
        target=run,
        help="""Print config""",
    )


def run():
    return cfg.current.to_dict()

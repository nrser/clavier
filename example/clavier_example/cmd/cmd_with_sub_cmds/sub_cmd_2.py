import splatlog as logging


LOG = logging.getLogger(__name__)


def add_to(subparsers):
    parser = subparsers.add_parser(
        "sub-command-2",
        target=run,
        help="Another subcommand",
    )


def run():
    return "We #2!"

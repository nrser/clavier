import splatlog


LOG = splatlog.get_logger(__name__)


def add_to(subparsers):
    parser = subparsers.add_parser(
        "whatever",
        target=run,
        help="""A "first level" subcommand""",
    )


def run():
    return "Whatever"

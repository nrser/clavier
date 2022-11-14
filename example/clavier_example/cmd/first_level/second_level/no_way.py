import splatlog


LOG = splatlog.get_logger(__name__)


def add_to(subparsers):
    parser = subparsers.add_parser(
        "no-way",
        target=run,
        help="""A "second level" subcommand""",
    )


def run():
    return "No way!"

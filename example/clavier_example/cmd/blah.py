import splatlog as logging


LOG = logging.getLogger(__name__)


def add_to(subparsers):
    parser = subparsers.add_parser(
        "blah",
        target=run,
        help="Hey hey blah blah!",
    )


def run():
    return "blah!!!"

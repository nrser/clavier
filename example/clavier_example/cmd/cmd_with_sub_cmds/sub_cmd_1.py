import splatlog


LOG = splatlog.get_logger(__name__)


def add_to(subparsers):
    parser = subparsers.add_parser(
        "sub-command-1",
        target=run,
        help="A subcommand",
    )


def run(**kwds):
    LOG.debug("Arguments", kwds=kwds)
    return "We #1!"

import sys
from time import sleep

import splatlog
from clavier import arg_par, cfg, io

_LOG = splatlog.get_logger(__name__)


def add_parser(subparsers: arg_par.Subparsers) -> None:
    parser = subparsers.add_parser(
        "count",
        target=count,
        help="""Count up to a number `n`, delaying `d` between each number""",
    )

    parser.add_argument(
        "-n",
        "--number",
        type=int,
        help="Number to count to",
    )

    parser.add_argument(
        "-d", "--delay", type=float, help="Delay between counts (in seconds)"
    )


def count(number: int = 10, delay: float = 1.0):
    assert number > 0, "number must be > 0"
    assert delay > 0, "delay must be > 0"

    try:
        for i in range(1, number + 1):
            sleep(delay)
            io.OUT.print("Count", i)
    except KeyboardInterrupt:
        io.OUT.print("Interrupted! Exiting...")
    else:
        io.OUT.print("Done!")

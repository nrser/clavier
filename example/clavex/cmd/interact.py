from argparse import SUPPRESS
import asyncio
import readline

import splatlog
from clavier import arg_par, io, cfg, cmd, embed

_LOG = splatlog.get_logger(__name__)


def add_parser(subparsers: arg_par.Subparsers) -> None:
    parser = subparsers.add_parser(
        "interact",
        target=run,
        help="""
            Interact back-and-forth with user.
        """,
    )


@cmd.as_cmd
async def sleep(delay: float = 3):
    """Sleep (asynchronously!) for `delay` seconds."""

    assert delay > 0

    io.OUT.print(f"Sleeping for {delay} seconds...")
    await asyncio.sleep(delay)

    io.OUT.print("Woke back up!")


@cmd.as_cmd
async def count(*, n: int = 10, delay: float = 1):
    """Count from 1 to `n`, printing as we go, waiting `delay` seconds between
    each.

    Used to test interupt signals (`ctrl-C` / `signal.SIGINT` /
    `KeyboardInterput`).
    """
    assert n > 0
    assert delay > 0

    io.OUT.print(f"Counting to {n}...")
    for i in range(1, n + 1):
        await asyncio.sleep(1)
        io.OUT.print("Count", i)

    io.OUT.print("Done counting!")


@cmd.as_cmd
def config(*, as_dict: bool = False):
    """Print the current config."""
    if as_dict:
        return cfg.current.to_dict()
    return cfg.current


@cmd.as_cmd
def x(src: str):
    return eval(src)


async def run():
    ifc = embed.AsyncEmbeddedConsole(
        pkg_name=__name__.split(".")[0],
        description="A lil' interactive console!",
        cmds=(sleep, count, config, x),
        prog_name="interact",
    )

    await ifc.run()

    print("Done-zo.")

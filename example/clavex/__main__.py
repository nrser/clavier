import logging
from pathlib import Path

import splatlog

from clavier import Sesh, etc

# NAME = __package__
NAME = "clavex"
WORK_DIR = Path(__file__).parents[1]

_LOG = splatlog.get_logger(__name__)


def get_sesh() -> Sesh:
    from . import cmd

    return Sesh(
        pkg_name=NAME,
        description="Clavier example CLI",
        cmds=cmd,
        autocomplete=False,
        prog_name=NAME,
    )


def main():
    if etc.env.get_bool("CLAVIER_SRV"):
        from clavier.srv import Config, Server

        Server.takeover(
            Config(
                name=NAME,
                work_dir=WORK_DIR,
                get_sesh=get_sesh,
                cache_sesh=True,
                server_log_level=logging.DEBUG,
                server_log_width=80,
            )
        )

    get_sesh().takeover()


if __name__ == "__main__":
    main()

import logging
from pathlib import Path

import splatlog

from clavier import App, etc
from clavier.name import Name

NAME = Name.of(__name__)
WORK_DIR = Path(__file__).parents[1]

_LOG = splatlog.get_logger(__name__)


def get_app() -> App:
    from . import cmd

    return App(
        name=NAME,
        description="Clavier example CLI",
        cmds=cmd,
        autocomplete=False,
    )


def main():
    if etc.env.get_bool("CLAVIER_SRV"):
        from clavier.srv import Config, Server

        Server.takeover(
            Config(
                name=NAME,
                work_dir=WORK_DIR,
                get_app=get_app,
                cache_app=True,
                server_log_level=logging.DEBUG,
                server_log_width=80,
            )
        )

    get_app().takeover()


if __name__ == "__main__":
    main()

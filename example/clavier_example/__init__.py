from __future__ import annotations

from clavier import Sesh, log as logging, builtin

from . import cmd


def run():
    sesh = Sesh(
        __name__,
        # TODO  Add a README and use it here
        "Clavier package example CLI app",
        (builtin, cmd),
    )
    sesh.setup(logging.INFO)
    sesh.parse()
    sesh.exec()

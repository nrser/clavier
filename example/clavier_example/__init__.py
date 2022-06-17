from __future__ import annotations

import splatlog as logging
from clavier import Sesh, builtin

from . import cmd, config


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

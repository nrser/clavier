from pathlib import Path

import splatlog
from clavier import cfg

with cfg.GLOBAL.configure("clavex") as clavex:
    clavex.description = "Clavier example CLI"

    with clavex.configure("paths") as paths:
        paths.root = Path(__file__).parents[1]

    with clavex.configure("srv") as srv:
        srv.cache_app = True

        with srv.configure("paths") as paths:
            paths.pid = clavex.paths.root / "run" / "clavex.pid"
            paths.socket = clavex.paths.root / "run" / "clavex.sock"

        with srv.configure("log") as log:
            log.level = splatlog.DEBUG
            log.width = 80

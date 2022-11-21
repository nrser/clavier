from __future__ import annotations

from .config import Config
from .key import Key

SELF_ROOT_KEY = Key(__package__).root
CFG = Config()

with CFG.configure(SELF_ROOT_KEY, src=__file__) as clavier:
    clavier.backtrace = False
    clavier.verbosity = 0

    with clavier.configure("log") as log:
        log.level = "WARNING"

    with clavier.configure("sh") as sh:
        sh.encoding = "utf-8"
        sh.rel_paths = False

        with sh.configure("opts") as opts:
            opts.long_prefix = "--"
            opts.sort = True
            opts.style = "="

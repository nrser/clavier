from __future__ import annotations

from .config import Config

CFG = Config()

with CFG.configure_root(__package__, src=__file__) as clavier:
    with clavier.configure("log") as log:
        log.level = "WARNING"
    with clavier.configure("sh") as sh:
        sh.encoding = "utf-8"
        sh.rel_paths = False
        with sh.configure("opts") as opts:
            opts.long_prefix = "--"
            opts.sort = True
            opts.style = "="

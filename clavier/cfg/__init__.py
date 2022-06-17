from __future__ import annotations
from pathlib import Path

from clavier.cfg.root import Root

CFG = Root()

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

    with clavier.configure("io.rel.roots") as rel_roots:
        # with rel_roots.__schema__ as schema:
        #     schema.typing = Mapping[str, PathRoot]

        with rel_roots.configure("clavier") as rr:
            rr.path = Path(__file__).parents[2]
            rr.symbol = ":musical_keyboard:"
            rr.enabled = True

        with rel_roots.configure("cwd") as rr:
            rr.path = Path.cwd()
            rr.prefix = "./"
            rr.enabled = True

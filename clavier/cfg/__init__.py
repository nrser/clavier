from __future__ import annotations

from .config import Config

CFG = Config()

with CFG.configure_root(__package__, src=__file__) as clavier:
    with clavier.configure("log") as log:
        log.level = "WARNING"

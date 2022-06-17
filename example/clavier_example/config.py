import json
from pathlib import Path

from clavier import CFG, io

with CFG.configure_root(__package__, src=__file__) as pkg:
    pkg.a = "aye!"
    pkg["b.c"] = "bee ci?"

    # pkg.deep = Value(
    #     {
    #         "x": 1,
    #         "y": 2,
    #     },
    #     type=dict,
    #     loads=json.loads,
    # )

    # pkg.b.d = "blah! blah!"

    # with pkg.pets as pets:
    #     pets.fav = "蝴蝶猫猫"

with CFG.configure(io.rel, "roots", src=__file__) as rel_roots:
    with rel_roots.configure("package") as rr:
        rr.path = Path(__file__).parents[1]
        rr.prefix = "📦 "
        rr.enabled = True

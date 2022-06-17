from pathlib import Path

from clavier.io.rel_path import RelRoot, RelPath
from clavier.cfg import CFG
from clavier import io

rel_root = RelRoot(**CFG.clavier.io.rel.roots.clavier.to_dict())
rel_path = RelPath(path=__file__, rel_to=rel_root)

io.OUT.print(rel_path)

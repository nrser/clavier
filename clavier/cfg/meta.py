from enum import Enum
from typing import Any, Mapping, Union
from pathlib import Path

from clavier.etc.path import TFilename, path_for


class SrcType(Enum):
    ENV = "env"
    FILE = "file"
    RUNTIME = "runtime"


class Meta:
    def __init__(
        self, src_type: SrcType = SrcType.RUNTIME, **extra: Mapping[str, Any]
    ):
        self.src_type = src_type
        self.extra = extra


class FileMeta(Meta):
    file: Path

    def __init__(self, file: TFilename, **kwds):
        self.file = path_for(file)
        super().__init__(src_type=SrcType.FILE, **kwds)

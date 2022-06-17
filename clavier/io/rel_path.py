from pathlib import Path, PosixPath, WindowsPath
from typing import Optional

from rich.console import Console, ConsoleOptions, RenderResult
from rich.segment import Segment

from clavier.etc.path import TFilename, path_for


class RelRoot:
    DEFAULT_ENABLED = True
    DEFAULT_PREFIX = None
    DEFAULT_PRIORITY = 5

    path: Path
    enabled: bool
    prefix: Optional[str]
    priority: int

    def __init__(
        self,
        path: Path,
        *,
        enabled: bool = DEFAULT_ENABLED,
        prefix: Optional[str] = DEFAULT_PREFIX,
        priority: int = DEFAULT_PRIORITY,
    ):
        self.path = path
        self.enabled = enabled
        self.prefix = prefix
        self.priority = priority

    def __rich_repr__(self):
        yield "path", self.path
        yield "enabled", self.enabled, self.__class__.DEFAULT_ENABLED
        yield "prefix", self.prefix, self.__class__.DEFAULT_PREFIX
        yield "priority", self.priority, self.__class__.DEFAULT_PRIORITY


class RelPath:
    path: Path
    rel_to: RelRoot

    def __init__(self, path: TFilename, rel_to: RelRoot):
        path = path_for(path)
        if path.is_absolute():
            self.path = path.relative_to(rel_to.path)
        else:
            self.path = path
        self.rel_to = rel_to

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        if self.rel_to.prefix is not None:
            yield Segment(self.rel_to.prefix)
        yield Segment(str(self.path))

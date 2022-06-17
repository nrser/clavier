from __future__ import annotations
from pathlib import Path
from typing import Any, Optional, Union, overload
from os import access, R_OK
from os.path import isfile
from abc import ABCMeta

from clavier.err import ArgTypeError

TFilename = Union[str, Path]


class PathError(Exception, metaclass=ABCMeta):
    DEFAULT_MESSAGE: str

    @overload
    def __init__(self, path: Path):
        pass

    @overload
    def __init__(self, message: str, path: Path):
        pass

    def __init__(self, path_or_message, path_or_none):
        if path_or_none is None:
            message = self.__class__.DEFAULT_MESSAGE
            path = path_or_message
        else:
            message = path_or_message
            path = path_or_none
        if not isinstance(path, Path):
            raise ArgTypeError("path", Path, path)
        super().__init__(message.format(path=path), path)

    @property
    def path(self) -> Path:
        return self.args[1]


class PathNotFoundError(PathError):
    DEFAULT_MESSAGE = "Path `{path}` not found"


class PathNotAFileError(PathError):
    DEFAULT_MESSAGE = "Path `{path}` is not a regular file"


class PathNotReadable(PathError):
    DEFAULT_MESSAGE = "Path `{path}` is not readable"


def is_filename(x: Any) -> bool:
    return isinstance(x, (str, Path))


def is_readable_file(filename: TFilename) -> bool:
    return isfile(filename) and access(filename, R_OK)


def check_readable_file(filename: TFilename) -> Path:
    path = path_for(filename)
    if not path.exists():
        raise PathNotFoundError(path)
    if not path.is_file():
        raise PathNotAFileError(path)
    if not access(path, R_OK):
        raise PathNotReadable(path)
    return path


def path_for(filename: TFilename) -> Path:
    if isinstance(filename, Path):
        return filename
    return Path(filename)


def dot_ext(ext: str) -> str:
    if ext.startswith("."):
        return ext
    return f".{ext}"


def undot_ext(ext: str) -> str:
    if ext.startswith("."):
        return ext[1:]
    return ext


def add_ext(filename: TFilename, ext: str) -> Path:
    # return path.parent / (path.name + dot_ext(ext))
    return path_for(filename).with_suffix(dot_ext(ext))


def rel_to(filename: TFilename, to: TFilename) -> Path:
    return path_for(filename).resolve().relative_to(path_for(to).resolve())


def path_len(filename: TFilename) -> int:
    if isinstance(filename, Path):
        return len(str(filename))
    return len(filename)

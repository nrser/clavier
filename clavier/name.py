from dataclasses import dataclass
from typing import Any, TypeVar

from .etc.txt import (
    as_env_name,
    as_identifier,
    as_kebab_case,
    is_identifier_path,
)

TName = TypeVar("TName", bound="Name")


@dataclass(frozen=True)
class Name:
    """It would be nice if Calvier apps had a `str` name

    1.  The name as a Python namespace / module-name, called `Name.space`.

        `Name.space` must be an _identifier path_ — a sequence of one or more
        _identifiers_ separated by ".".

        `Name.space` is used as the configuration namespace, and typically
        coresponds to the Clavier app's root module `__name__`.

    2.  The name of the executable program, called `Name.exe`.

        `Name.exe` equates to `argparse.ArgumentParser.progname`, and is the
        name used for _entrypoint_ binaries in client/server mode.

    3.  The environment variable namspace, called `Name.env`.

    Generally, these will all basically be the same thing, and are all derived
    from the `Name.space` via `Name.of(__name__)` or similar.

    However, there are particular situations where you may want to explicitly

    ##### Examples #####

    ```python
    >>> Name.of(pkg="my-app-dev", path="my_app.dev")
    Name(path='my_app.dev',
        pkg='my-app-dev',
        exe='my-app-dev',
        env='MY_APP_DEV')

    ```
    """

    #: `path` suffixes that are stripped off of present.
    #:
    #: The useful one is ".__main__", allowing `Name.of(__name__)` from the
    #: `__main__.py` file, but ".__init__" is thrown in as well 'cause why not.
    #:
    STRIP_SUFFIXES = (".__init__", ".__main__")

    @classmethod
    def strip_path_suffix(cls, path: str) -> str:
        """Strip off one of the `STRIP_SUFFIXES` if present on a name-path."""

        for suffix in cls.STRIP_SUFFIXES:
            if path.endswith(suffix):
                return path.removesuffix(suffix)

        return path

    @classmethod
    def of(cls: type[TName], x: Any) -> TName:
        match x:
            case name if isinstance(name, cls):
                return name

            case str(path) if is_identifier_path(path):
                path = cls.strip_path_suffix(path)
                kebabbed = as_kebab_case(path).replace(".", "-")

                return cls(
                    pkg=kebabbed,
                    path=path,
                    exe=kebabbed,
                    env=as_env_name(path),
                )

            # case str(name):
            #     return cls(
            #         canonical=name,
            #         path=as_identifier(name),
            #         exe=name,
            #         env=as_env_name(name),
            #     )

            case {"path": path, **kwds}:
                return cls(
                    pkg=kwds.get(
                        "pkg",
                        as_kebab_case(path).replace(".", "-"),
                    ),
                    path=path,
                    exe=kwds.get(
                        "executable",
                        as_kebab_case(path).replace(".", "-"),
                    ),
                    env=kwds.get(
                        "env",
                        as_env_name(path),
                    ),
                )

            # case {"executable": exe, **kwds}:
            #     return cls(
            #         pkg=kwds.get(
            #             "pkg",
            #             as_kebab_case(exe).replace(".", "-"),
            #         ),
            #         path=kwds.get(
            #             "identifier_path",
            #             as_identifier(exe),
            #         ),
            #         exe=exe,
            #         env=kwds.get(
            #             "env",
            #             as_env_name(exe),
            #         ),
            #     )

        assert False

    pkg: str
    path: str
    exe: str
    env: str

    def __post_init__(self):
        if not is_identifier_path(self.path):
            raise ValueError(
                f"`path` must be an identifier path, given {self.path!r}"
            )

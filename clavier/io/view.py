import json
from typing import Generic, TypeVar

from rich.console import Console

from mdutils.mdutils import MdUtils

from clavier import err

from .io_consts import OUT, ERR
from .io_helpers import render_to_console
from .view_format import ViewFormat


TData = TypeVar("TData")


class View(Generic[TData]):
    DEFAULT_FORMAT = "rich"

    @classmethod
    def formats(cls) -> list[ViewFormat]:
        def create(attr_name: str) -> ViewFormat:
            fn = getattr(cls, attr_name)
            name = attr_name.replace("render_", "")
            return ViewFormat(name, fn, cls.DEFAULT_FORMAT == name)

        return sorted(
            (
                create(attr)
                for attr in dir(cls)
                if (attr.startswith("render_") and callable(getattr(cls, attr)))
            )
        )

    @classmethod
    def help(cls):
        builder = MdUtils(file_name="")

        builder.new_paragraph(
            "How to print output. Commands can add their own custom output "
            "formats, but pretty much all commands should support `rich` and "
            "`json` outputs."
        )

        builder.new_list([format.list_item for format in cls.formats()])

        return builder.file_data_text

    data: TData
    exit_status: int
    out: Console
    err: Console

    def __init__(
        self,
        data: TData,
        *,
        exit_status: int = 0,
        out: Console = OUT,
        err: Console = ERR,
    ):
        self.data = data
        self.exit_status = exit_status
        self.out = out
        self.err = err

    def print(self, *args, **kwds):
        self.out.print(*args, **kwds)

    def render(self, format: str = DEFAULT_FORMAT) -> None:
        method_name = f"render_{format}"
        method = getattr(self, method_name, None)

        if method is None:
            raise RuntimeError(
                f"format {format} not supported by view {self.__class__} "
                f"(method `{method_name}` does not exist)"
            )

        if not callable(method):
            raise err.InternalError(
                f"found attribute `{method_name}` on "
                f"{self.__class__} view, but it is not callable."
            )

        method()

    def render_json(self) -> None:
        """\
        Dumps the return value in JSON format.
        """
        self.print(json.dumps(self.data, indent=2))

    def render_rich(self) -> None:
        """\
        Pretty, colorful output for humans via the [rich][] Python package.

        [rich]: https://rich.readthedocs.io/en/stable/
        """
        render_to_console(self.data, console=self.out)


# class ErrorView(View):
#     def __init__(
#         self,
#         data,
#         *,
#         exit_status: int = 1,
#         out: Console = OUT,
#         err: Console = ERR,
#     ):
#         super().__init__(data, exit_status=exit_status, out=out, err=err)

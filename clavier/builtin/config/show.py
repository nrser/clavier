from typing import List, Optional
import importlib.util
import sys
from argparse import BooleanOptionalAction

from clavier import arg_par, io, CFG
from rich.table import Table
from rich.pretty import Pretty
from rich.style import Style
from rich.color import Color

from clavier.cfg.config import Config


def add_parser(subparsers: arg_par.Subparsers):
    parser = subparsers.add_parser(
        "show",
        help="Dump config",
        target=show_config,
    )

    parser.add_argument(
        "-s",
        "--src",
        dest="include_src",
        action=BooleanOptionalAction,
        help="Include source of each value",
    )

    parser.add_argument(
        "module_name",
        nargs="?",
        help="Specific module to show config for",
    )


def get_module(name):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.find_spec(name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    return mod


def show_config(module_name: Optional[str] = None, include_src: bool = False):
    if module_name is None:
        config = CFG
    else:
        config = CFG[module_name]
    return ConfigView.from_data(
        config=config,
        module_name=module_name,
        include_src=include_src,
    )


class ConfigView(io.View):
    @property
    def config(self) -> Config:
        return self.data["config"]

    @property
    def module_name(self) -> Optional[str]:
        return self.data["module_name"]

    @property
    def include_src(self) -> bool:
        return self.data["include_src"]

    @property
    def title(self) -> str:
        if self.module_name is None:
            return "Global Config"
        return f"{self.module_name} Config"

    def render_rich(self):
        table = Table(title=self.title)
        table.add_column("Key")
        table.add_column("Value")
        if self.include_src:
            table.add_column("Source")
        for index, (key, value_state) in enumerate(self.config.view().items()):
            style = (
                None
                if index % 2 == 0
                else Style(bgcolor=Color.parse("#333333"))
            )
            row = [str(key), Pretty(value_state.value)]
            if self.include_src:
                row.append(io.fmt(value_state.layer.src))
            table.add_row(*row, style=style)
        self.print(table)

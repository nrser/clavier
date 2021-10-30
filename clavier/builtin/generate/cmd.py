from typing import List
import importlib.util
import sys

from clavier import arg_par


def add_parser(subparsers: arg_par.Subparsers):
    parser = subparsers.add_parser(
        "cmd",
        help="Generate a new command",
        target=generate_cmd,
    )

    parser.add_argument(
        "name",
        nargs="+",
        help="Name of new command. Multiple values represent a sub-command path",
    )

    parser.set_defaults(pkg_name="clavier_example")


def get_module(name):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.find_spec(name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    return mod


def generate_cmd(name, pkg_name):
    mod = get_module(pkg_name)
    # return kwds

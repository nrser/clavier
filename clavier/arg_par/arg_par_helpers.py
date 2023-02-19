from __future__ import annotations
from typing import Iterable, TYPE_CHECKING

from clavier import etc

if TYPE_CHECKING:
    from .subparsers import Subparsers


DEFAULT_HOOK_NAMES = (
    # Preferred name (v0.1.3+)
    "add_parser",
    # Legacy name (v0.1.2 and prior)
    "add_to",
)


def find_hook_name(obj: object, hook_names: Iterable[str]) -> str | None:
    return etc.find(lambda hook_name: hasattr(obj, hook_name), hook_names)


def has_hook(obj: object, hook_names: Iterable[str]) -> bool:
    return find_hook_name(obj, hook_names) is not None


def invoke_hook(
    obj: object, hook_names: Iterable[str], subparsers: "Subparsers"
) -> None:
    if name := find_hook_name(obj, hook_names):
        return getattr(obj, name)(subparsers)
    elif callable(obj):
        obj(subparsers)

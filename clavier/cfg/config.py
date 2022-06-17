from dataclasses import dataclass
from typing import Any, Dict, Iterable, Iterator, Protocol, Tuple, Mapping

from clavier.cfg.key import Key
from clavier.cfg.layer import Layer


@dataclass(frozen=True)
class ValueState:
    """The current state of a configuration value.

    Inclused the value itself as well as the `clavier.cfg.layer.Layer` that
    it came from.
    """

    value: Any
    layer: Layer


class Config(Protocol):
    def __contains__(self, key: Any) -> bool:
        pass

    def __getattr__(self, name: str) -> Any:
        pass

    def __getitem__(self, key: Any) -> Any:
        pass

    def __iter__(self) -> Iterator[Key]:
        pass

    def __len__(self) -> int:
        pass

    def get(self, key: Any, default: Any = None) -> Any:
        pass

    def items(self) -> Iterable[Tuple[Key, Any]]:
        pass

    def keys(self) -> Iterable[Key]:
        pass

    def values(self) -> Iterable[Any]:
        pass

    def view(self) -> Mapping[Key, ValueState]:
        pass

    def to_dict(self, *, deep: bool = False) -> Dict[str, Any]:
        pass

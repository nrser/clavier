from typing import ParamSpec, Protocol, TypeAlias, TypeVar, TYPE_CHECKING

if TYPE_CHECKING:
    from clavier.arg_par.subparsers import Subparsers

TParams = ParamSpec("TParams")
TReturn_co = TypeVar("TReturn_co", covariant=True)


class CmdFn(Protocol[TParams, TReturn_co]):
    def __call__(
        self, *args: TParams.args, **kwds: TParams.kwargs
    ) -> TReturn_co:
        ...

    def add_parser(self, subparsers: "Subparsers") -> None:
        ...


class HasFileno(Protocol):
    def fileno(self) -> int:
        ...


FileDescriptor: TypeAlias = int
FileDescriptorLike: TypeAlias = int | HasFileno

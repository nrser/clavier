from typing import Protocol, TypeAlias


class HasFileno(Protocol):
    def fileno(self) -> int:
        ...


FileDescriptor: TypeAlias = int
FileDescriptorLike: TypeAlias = int | HasFileno

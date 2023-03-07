import os
from typing import AnyStr, Callable, Mapping, TypeAlias, TypeGuard, TypeVar


T = TypeVar("T")


def instance_guard(t: type[T]) -> Callable[[object], TypeGuard[T]]:
    def isinstance_guard(x: object) -> TypeGuard[T]:
        return isinstance(x, t)

    return isinstance_guard


# PyLance Types
# ============================================================================
#
# Types coppied from [PyLance][] in order to match their type definitions (and,
# also, going to assume they're put more work into it than I will ever be able
# to... I have found a few places that seem like they might be errors, but
# generally this stuff is a _huge_ pain to try and derive from the cPython
# source).
#
# [PyLance]: https://github.com/microsoft/pylance-release#readme
#

#: The things you can use as paths, in the general sense.
#:
#: Using same name and definition as PyLance, which looks like it comes from
#: [typeshed][]?
#:
#: Of course, it's worth noting that `pathlib.Path` satisfies `os.PathLike`, so
#: it fits in here.
#:
#: [typeshed]: https://github.com/python/typeshed
#:
StrPath = str | os.PathLike[AnyStr]  # stable (— PyLance)
BytesPath: TypeAlias = bytes | os.PathLike[bytes]  # stable (— PyLance)
GenericPath: TypeAlias = AnyStr | os.PathLike[AnyStr]
StrOrBytesPath: TypeAlias = (
    str | bytes | os.PathLike[str] | os.PathLike[bytes]
)  # stable (— PyLance)


#: Type of environment for the common `subprocess` execution functions, such as
#: `subprocess.run`. From [PyLance][].
#:
#: NOTE Currently _not in use_ because we've elected to limit our API to `str`
#:      (2023-03-06).
#:
ENV: TypeAlias = Mapping[bytes, StrOrBytesPath] | Mapping[str, StrOrBytesPath]

#: Type of environment argument to the _exec_ family of functions (`os.execv`,
#: etc...).
#:
#: NOTE Currently _not in use_ because we've elected to limit our API to `str`
#:      (2023-03-06).
#:
#: Lifted from [PyLance][], where it notes:
#:
#: > Depending on the OS, the keys and values are passed either to
#: > PyUnicode_FSDecoder (which accepts str | ReadableBuffer) or to
#: > PyUnicode_FSConverter (which accepts StrOrBytesPath). For simplicity,
#: > we limit to str | bytes.
#:
ExecEnv: TypeAlias = Mapping[bytes, bytes | str] | Mapping[str, bytes | str]

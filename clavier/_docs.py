"""Just used in generating docs, excluded from the distributed package
(because it depends on dev dependencies).
"""

from abc import abstractmethod
from dataclasses import dataclass
from importlib.metadata import PackagePath, files
from importlib.machinery import SOURCE_SUFFIXES
import logging

from doctor_genova.external_resolver import ExternalResolution

_LOG = logging.getLogger(__name__)


class DependencyResolver:
    @staticmethod
    def as_module_name(source_path: PackagePath) -> str:
        """
        ##### Examples #####

        ```python
        >>> DependencyResolver.as_module_name(
        ...     PackagePath("my_pkg/a/b.py")
        ... )
        'my_pkg.a.b'

        >>> DependencyResolver.as_module_name(
        ...     PackagePath("my_pkg/__init__.py")
        ... )
        'my_pkg'

        >>> DependencyResolver.as_module_name(
        ...     PackagePath("my_pkg.py")
        ... )
        'my_pkg'

        ```
        """
        if source_path.stem == "__init__":
            return ".".join(source_path.parts[:-1])

        return ".".join(source_path.with_suffix("").parts)

    _pkg_name: str
    _source_paths: set[PackagePath]
    _module_names: set[str]

    def __init__(self, pkg_name: str):
        self._pkg_name = pkg_name

        metadata_files = files(pkg_name)

        if metadata_files is None:
            raise Exception(f"package {pkg_name!r} not found")

        source_paths = {
            path for path in metadata_files if path.suffix in SOURCE_SUFFIXES
        }

        self._module_names = {
            self.as_module_name(path) for path in source_paths
        }

    @abstractmethod
    def resolve_name(self, name: str) -> None | ExternalResolution:
        ...


@dataclass(frozen=True)
class MoreItertoolsResolution:
    # Example URL (`more_itertools.prepend`)
    #
    # https://more-itertools.readthedocs.io/en/stable/api.html#more_itertools.prepend
    #
    BASE_URL = "https://more-itertools.readthedocs.io/en/stable/api.html"

    name: str

    def get_name(self) -> str:
        return self.name

    def get_url(self) -> str:
        return self.BASE_URL + "#" + self.name

    def get_md_link(self) -> str:
        return "[{}]({})".format(self.name, self.get_url())


class MoreItertoolsResolver(DependencyResolver):
    def __init__(self):
        super().__init__("more-itertools")

    def resolve_name(self, name: str) -> None | ExternalResolution:
        if any(
            (name == module_name or name.startswith(module_name + "."))
            for module_name in self._module_names
        ):
            return MoreItertoolsResolution(name=name)

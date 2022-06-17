from os import environ
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    Mapping,
    Set,
    Tuple,
    TypeVar,
    Union,
)

from sortedcontainers import SortedDict
import splatlog as logging

from clavier.cfg.key import Key, TKeyable
from clavier.cfg.layer import Layer
from clavier.err import ArgTypeError
from clavier.etc.read_only_mapping import ReadOnlyMapping


LOG = logging.getLogger(__name__)

TDefault = TypeVar("TDefault")


class Env(Mapping[Key, Any], Layer):
    _snapshot: Mapping[str, str]
    _seen_keys: Set[Key]
    _loaded: Dict[Key, Any]
    _meta: Mapping[Key, Any]

    def __init__(self, env: Mapping[str, str] = environ):
        # Take a snapshot -- don't really want to deal with changes to the env
        # during the runtime, seems like most apps are fine with env not being
        # dynamic
        self._snapshot = ReadOnlyMapping(**env)
        self._seen_keys = set()
        self._loaded = SortedDict()
        self._meta = ReadOnlyMapping(src="env", env=env)

    def register(self, key: Key, parse: Callable[[str], Any]) -> bool:
        # Check we were given a Key
        if not isinstance(key, Key):
            raise ArgTypeError(arg_name="key", expected=Key, given=key)

        # Just bail out now if `register` has already been called with the key
        if key in self._seen_keys:
            return key in self._loaded

        # Record that we've seen this key so we don't need to go through this
        # process again
        self._seen_keys.add(key)

        env_name = key.env_name

        # If we don't have a matching env var we can be done now
        if env_name not in self._snapshot:
            return False

        env_value = self._snapshot[key.env_name]

        # Try to load the value
        try:
            value = parse(env_value)
        except Exception as error:
            # Report the error, but don't propigate it -- bad data in env vars
            # will complain but not crash the program
            LOG.error(
                f"Failed to parse env var for key {key} -- {error}",
                env_name=env_name,
                env_value=env_value,
                exc_info=True,
            )
            # We're done. We won't try again, due to `self._snapshot` being static
            # and key having been added to `self._seen_keys`
            return False

        # Set the value and we're done
        self._loaded[key] = value

        return True

    # Layer Protocol
    # ========================================================================

    @property
    def changes(self) -> Mapping[Key, Any]:
        return self

    @property
    def meta(self) -> Mapping[str, Any]:
        return self._meta

    # Mapping Protocol
    # ========================================================================

    def __contains__(self, key: TKeyable) -> bool:
        return Key(key) in self._loaded

    def __getitem__(self, key: TKeyable) -> Any:
        return self._loaded[Key(key)]

    def __iter__(self) -> Iterator[Key]:
        return iter(self._loaded)

    def __len__(self) -> int:
        """The number of values loaded from the environment."""
        return len(self._loaded)

    def get(
        self, key: TKeyable, default: TDefault = None
    ) -> Union[Any, TDefault]:
        key = Key(key)
        if key in self._loaded:
            return self._loaded[key]
        return default

    def items(self) -> Iterable[Tuple[Key, TKeyable]]:
        return self._loaded.items()

    def keys(self) -> Iterable[Key]:
        return self._loaded.keys()

    def values(self) -> Iterable[Any]:
        return self._loaded.values()

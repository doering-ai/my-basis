############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import ClassVar
from pathlib import Path
import functools as ft
import os

### EXTERNAL
import pydantic as pyd
import dotenv

### INTERNAL
from ..utils import ut
from ..types import Buffer
from ..regex import RegexStore


############
### DATA ###
############
dotenv.load_dotenv()
initial_env = dict(os.environ)

NOWHERE = Path('/')


############
### BODY ###
############
class Environment(pyd.BaseModel):
    """An ergonomic interface for reading environment variables.

    As opposed to the builtin interface, this singleton class provides intelligent type coercion,
    automatic dotenv loading, performant caching, and most importantly, a much clearer and more
    ergonomic syntax.

    .. code-block:: python

       from my.apis import env

       # export SOME_TEXT="production"
       print(f'{env.SOME_TEXT=!r}')  # -> 'production'
       print(f'{env.MISSING_VAR=!r}')  # -> ''

       # export SOME_PATH="~/Downloads"
       # export NESTED_PATH="$SOME_PATH/child"
       print(f'{env.paths.SOME_PATH=!r}')  # -> PosixPath('/home/username/Downloads')
       print(f'{env.paths.NESTED_PATH=!r}')  # -> PosixPath('/home/username/Downloads/child')

       # export SOME_FLAG="32"
       # export OTHER_FLAG="yes"
       # export FALSE_FLAG="yes, some non-truthy string"
       print(env.flags.SOME_FLAG)  # -> 32
       print(bool(env.flags.OTHER_FLAG))  # -> True
       print(bool(env.flags.FALSE_FLAG))  # -> False
       print(bool(env.flags.MISSING_FLAG))  # -> False

    Beyond basic string access via attribute or item notation, the class provides specialized
    accessors for common use cases:

    1. The ``paths`` property turns vars into filesystem paths with variable expansion, user home
    directory expansion, and automatic path resolution.

    2. The ``flags`` property interprets environment variables as int flags, recognizing common
    truthy values like ``true``, ``yes``,and ``ON`` as ``1`` for use w/ booleans.

    .. note::
       All environment variable names must be uppercase to be recognized by the interface.
    """

    _ENVIRON: ClassVar[dict[str, str]] = initial_env
    RGXS: ClassVar[RegexStore] = RegexStore.new(
        options=dict(
            force_named_groups=True,
            lazy_load=True,
        ),
        name=r'[_\d[:upper:]]+',
        interpolation=r'\$(?P>name)\b|\${(?P>name)}',
        truthy=r'(?i:t(rue)?|y(es)?|enable[d]?|on)',
    )

    # Override thse so that no sensitive info is automatically printed by loggers
    def __str__(self) -> str:
        return 'Environment(...)'

    def __repr__(self) -> str:
        return 'Environment(...)'

    # -------
    # GETTERS
    # -------
    def __getattr__(self, key: str) -> str:
        return Environment._get(key)

    def __getitem__(self, key: str) -> str:
        return Environment._get(key)

    @ft.lru_cache(maxsize=256)
    @staticmethod
    def _get(key: str, default: str = '') -> str:
        ret = Environment._ENVIRON.get(key, default)
        if '$' in ret:
            ret = Environment.interpolate(ret)
        return ret

    def get(self, key: str, default: str = '') -> str:
        """Get an environment variable as a string, with optional default."""
        return Environment._get(key, default)

    # -------
    # SETTERS
    # -------
    def __setattr__(self, key: str, value: str) -> None:
        self.set(key, value)

    def __setitem__(self, key: str, value: str) -> None:
        self.set(key, value)

    def set(self, key: str, value: str) -> None:
        """Set an environment variable, clearing caches if value changes.

        Args:
            key: Variable name (must be uppercase with underscores).
            value: Variable value.
        Raises:
            AssertionError: If key doesn't match naming convention.
        """
        self.validate_name(key)
        if self.get(key) != value:
            Environment._get.cache_clear()
            Environment._path.cache_clear()
            Environment._flag.cache_clear()

        Environment._ENVIRON[key] = value

    # -----
    # PATHS
    # -----
    class _PathEnv:
        def __getattr__(self, key: str) -> Path:
            return Environment._path(key)

    @ft.cached_property
    def paths(self) -> Environment._PathEnv:
        """A cached property allowing for ergonomic dot-notation access to coerced path vars."""
        return self._PathEnv()

    @ft.lru_cache(maxsize=2**8)
    @staticmethod
    def _path(key: str, default: str = '', mkdir: bool = False) -> Path:
        raw = Environment._get(key, default)
        if not raw:
            return NOWHERE
        path = ut.path(raw)
        if mkdir:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def path(self, key: str, default: str | Path = '', mkdir: bool = False) -> Path:
        """Get environment variable as an expanded, resolved path.

        Performs variable substitution for ${VAR} or $VAR patterns, then expands
        user home directory and resolves to absolute path.

        Args:
            key: Environment variable name.
            default: Default path if variable not set.
            mkdir: Whether to create directory if it doesn't exist.
        Returns:
            Resolved absolute path.
        """
        return Environment._path(key, str(default), mkdir)

    # -----
    # FLAGS
    # -----
    class _FlagEnv:
        def __getattr__(self, key: str) -> int:
            return Environment._flag(key)

    @ft.cached_property
    def flags(self) -> Environment._FlagEnv:
        """A cached property allowing for ergonomic dot-notation access to coerced flag vars."""
        return self._FlagEnv()

    @ft.lru_cache(maxsize=256)
    @staticmethod
    def _flag(key: str, default: int = 0) -> int:
        assert key, '_FlagEnv keys must be non-empty'
        assert key.isupper(), '_FlagEnv keys must be uppercase'
        val = Environment._get(key).strip(' ')

        if not val:
            return default
        elif val.isdigit():
            return int(val)
        elif val.startswith('-') and val[1:].isdigit():
            return -1 * int(val[1:])
        elif Environment.RGXS.fullmatch('truthy', val):
            return 1
        else:
            return default

    def flag(self, key: str, default: int = 0) -> int:
        """Get environment variable as an integer flag, or 0 if no set or coercable.

        Recognizes: `t|true|y|yes|enable|enabled|on` as 1.

        Args:
            key: Environment variable name (must be uppercase).
            default: Default value if not set or unrecognized.
        Returns:
            Any integer.
        Raises:
            AssertionError: If key is empty or not uppercase.
        """
        return Environment._flag(key, default)

    # ---------
    # UTILITIES
    # ---------
    @ft.cached_property
    def is_dev(self) -> bool:
        """Check if environment is in development mode, based on the `$MY_MODE` var."""
        return self.get('MY_MODE', 'dev').lower().startswith('dev')

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and key in Environment._ENVIRON

    @staticmethod
    def is_valid_name(key: str) -> bool:
        """Check if string is a valid environment variable name.

        Args:
            key: String to validate.
        Returns:
            True if key contains only uppercase, digits, and underscores.
        """
        return bool(Environment.RGXS.fullmatch('name', key))

    @staticmethod
    def validate_name(key: str) -> None:
        """Validate environment variable name format.

        Args:
            key: Variable name to validate.
        Raises:
            AssertionError: If key is invalid.
        """
        assert Environment.is_valid_name(key), f'Invalid environment variable name: {key}'

    @staticmethod
    def interpolate(val: str) -> str:
        """Replace envvar references in the value with their corresponding values.

        Args:
            val: A string, e.g. `${HOME}/data/${DATASET}`.
        Returns:
            Interpolated string, e.g. `/home/user/data/mnist`.
        """
        buf = Buffer.new(val)
        for match in Environment.RGXS.finditer('interpolation', buf):
            if subval := Environment._get(match.at('name')):
                buf.replace(match.span, subval)
        return str(buf)


#: Global instance of this class for convenient access.
env = ENV = Environment()

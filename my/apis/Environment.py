############
### HEAD ###
############
### STANDARD
from typing import ClassVar
from pathlib import Path
import functools as ft
import regex as re
import os

### EXTERNAL
import pydantic as pyd
import dotenv

### INTERNAL


############
### DATA ###
############
dotenv.load_dotenv()
initial_env = dict(os.environ)


############
### BODY ###
############
class Environment(pyd.BaseModel):
    """
    Convient interface to environment variables with special cases for accessing fileystem paths
    and flags (integers) with typing.

    Provides attribute and item access to environment variables with caching.
    Includes special accessors for paths (with variable expansion) and boolean flags.
    Environment variables must be uppercase with underscores to be recognized by this interface.
    """

    ENVIRON: ClassVar[dict[str, str]] = initial_env
    NAME_RGX: ClassVar[re.Pattern] = re.compile(r'[_\d[:upper:]]')
    EMB_RGX: ClassVar[re.Pattern] = re.compile(r'\$[_\d[:upper:]]+\b|\${[_\d[:upper:]]+}')

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
        return Environment.ENVIRON.get(key, default)

    def get(self, key: str, default: str = '') -> str:
        return Environment._get(key, default)

    # -------
    # SETTERS
    # -------
    def __setattr__(self, key: str, value: str) -> None:
        self.set(key, value)

    def __setitem__(self, key: str, value: str) -> None:
        self.set(key, value)

    def set(self, key: str, value: str) -> None:
        """
        Set an environment variable, clearing caches if value changes.

        Args:
            key: Variable name (must be uppercase with underscores).
            value: Variable value.

        Raises:
            AssertionError: If key doesn't match naming convention.
        """
        self.validate_name(key)
        if cur := self.get(key):
            if cur == value:
                return
            else:
                Environment._get.cache_clear()
                Environment._path.cache_clear()
                Environment._flag.cache_clear()

        Environment.ENVIRON[key] = value

    # -----
    # PATHS
    # -----
    class PathEnv:
        def __getattr__(self, key: str) -> Path:
            return Environment._path(key)

    @ft.cached_property
    def paths(self) -> 'Environment.PathEnv':
        return self.PathEnv()

    @ft.lru_cache(maxsize=256)
    @staticmethod
    def _path(key: str, default: str = '', mkdir: bool = False) -> Path:
        val = Environment._get(key) or default

        for match in Environment.EMB_RGX.findall(val):
            if subval := Environment._get(match.strip('{}$')):
                val = val.replace(match, subval)

        ret = Path(val).expanduser().resolve()

        if mkdir and val:
            ret.mkdir(parents=True, exist_ok=True)
        return ret

    def path(self, key: str, default: str = '', mkdir: bool = False) -> Path:
        """
        Get environment variable as an expanded, resolved path.

        Performs variable substitution for ${VAR} or $VAR patterns, then expands
        user home directory and resolves to absolute path.

        Args:
            key: Environment variable name.
            default: Default path if variable not set.
            mkdir: Whether to create directory if it doesn't exist.

        Returns:
            Resolved absolute path.
        """
        return Environment._path(key, default, mkdir)

    # -----
    # FLAGS
    # -----
    class FlagEnv:
        def __getattr__(self, key: str) -> int:
            return Environment._flag(key)

    @ft.cached_property
    def flags(self) -> 'Environment.FlagEnv':
        return self.FlagEnv()

    @ft.lru_cache(maxsize=256)
    @staticmethod
    def _flag(key: str, default: int = 0) -> int:
        assert key, 'FlagEnv keys must be non-empty'
        assert key.isupper(), 'FlagEnv keys must be uppercase'
        val = Environment._get(key).lower()

        if val.isdigit():
            return int(val)
        elif val in ('true', 'yes', 'y', 't', 'on', 'enable'):
            return 1
        else:
            return default

    def flag(self, key: str, default: int = 0) -> int:
        """
        Get environment variable as a boolean flag (0 or 1).

        Recognizes: '1', 'true', 'yes', 'y', 't', 'on', 'enable' as 1.
        Numeric values are parsed directly. All other values return default.

        Args:
            key: Environment variable name (must be uppercase).
            default: Default value if not set or unrecognized.

        Returns:
            Integer 0 or 1 (or numeric value).

        Raises:
            AssertionError: If key is empty or not uppercase.
        """
        return Environment._flag(key, default)

    # ---------
    # UTILITIES
    # ---------
    @ft.cached_property
    def is_dev(self) -> bool:
        return self.get('MY_MODE', 'dev').lower().startswith('dev')

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and key in Environment.ENVIRON

    @staticmethod
    def is_valid_name(key: str) -> bool:
        """
        Check if string is a valid environment variable name.

        Args:
            key: String to validate.

        Returns:
            True if key contains only uppercase, digits, and underscores.
        """
        return bool(Environment.NAME_RGX.fullmatch(key))

    @staticmethod
    def validate_name(key: str) -> None:
        """
        Validate environment variable name format.

        Args:
            key: Variable name to validate.

        Raises:
            AssertionError: If key is invalid.
        """
        assert Environment.is_valid_name(key), f'Invalid environment variable name: {key}'


env = Environment()

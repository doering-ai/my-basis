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

### INTERNAL


############
### BODY ###
############
class Environment(pyd.BaseModel):
    ENVIRON: ClassVar[dict[str, str]] = dict(os.environ)
    RGX: ClassVar[re.Pattern] = re.compile(r'\$[_\d[:upper:]]+\b|\${[_\d[:upper:]]+}')

    def __getattr__(self, key: str) -> str:
        return self.get(key)

    @ft.lru_cache(maxsize=128)
    @staticmethod
    def get(key: str, default: str = '') -> str:
        return Environment.ENVIRON.get(key, default)

    # -----------
    # -- Paths --
    # -----------
    class PathEnv:
        def __getattr__(self, key: str) -> Path:
            return Environment._path(key)

    @ft.cached_property
    def paths(self) -> 'Environment.PathEnv':
        return self.PathEnv()

    @ft.lru_cache(maxsize=128)
    @staticmethod
    def _path(key: str, default: str = '', mkdir: bool = False) -> Path:
        val = Environment.get(key) or default

        for match in Environment.RGX.findall(val):
            if subval := Environment.get(match.strip('{}$')):
                val = val.replace(match, subval)

        ret = Path(val).expanduser().resolve()

        if mkdir:
            ret.mkdir(parents=True, exist_ok=True)
        return ret

    def path(self, key: str, default: str = '', mkdir: bool = False) -> Path:
        return Environment._path(key, default, mkdir)

    # -----------
    # -- Flags --
    # -----------
    class FlagEnv:
        def __getattr__(self, key: str) -> int:
            return Environment._flag(key)

    @ft.cached_property
    def flags(self) -> 'Environment.FlagEnv':
        return self.FlagEnv()

    @ft.lru_cache(maxsize=128)
    @staticmethod
    def _flag(key: str, default: int = 0) -> int:
        assert key, 'FlagEnv keys must be non-empty'
        assert key.isupper(), 'FlagEnv keys must be uppercase'
        val = Environment.get(key).lower()

        if val.isdigit():
            return int(val)
        elif val in ('true', 'yes', 'y', 't', 'on', 'enable'):
            return 1
        else:
            return default

    def flag(self, key: str, default: int = 0) -> int:
        return Environment._flag(key, default)


env = Environment()

############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from pathlib import Path
from sys import version_info
import functools as ft
import os

### EXTERNAL
import pydantic as pyd
import sublime as sb
import regex as re

### INTERNAL


############
### DATA ###
############
VER_STR = f'python{version_info.major}{version_info.minor}'
Directory = pyd.DirectoryPath


############
### BODY ###
############
def _normalize(path: str | Path) -> Path:
    """Expand a string path into a resolved Path object."""
    path = Path(path).expanduser()
    if not path or path.is_absolute():
        pass
    elif (_p := Path.cwd() / path).exists():
        return _p
    return path


class PathRegistry(pyd.BaseModel):
    """A registry of file paths, mapping string names to Path objects."""

    # ---- System ----
    host: Directory = _normalize(os.getenv('HOME', '~'))

    # ---- Main ----
    #: The main directory, usually in `$XDG_CONFIG`/`~/.config`.
    home: Directory = _normalize(sb.packages_path()).parent
    #: Unzipped packages.
    pkgs: Directory = home / 'Packages'
    #: Installed (zipped) packages.
    inst: Directory = home / 'Installed Packages'
    #: Package logs.
    logs: Directory = home / 'Logs'
    #: The location of importable libraries for plugins.
    venv: Directory = home / 'Lib' / VER_STR

    # ---- Packages ----
    #: The user package, which contains top-level settings and other overrides.
    user: Directory = pkgs / 'User'
    #: The myBasis package, which contains the main code and resources for this plugin.
    base: Directory = pkgs / 'myBasis'

    # ---- Storage ----
    #: Root of caches for packages and sublime itself, usually in `$XDG_CACHE`/`~/.cache`.
    cache: Directory = _normalize(sb.cache_path())
    #: Package caches in particular.
    data: Directory = cache.parent / 'Package Storage'

    # ---- Root ----
    #: The root of the installed application, usually in `/opt/sublime_text`.
    root: Directory = _normalize(sb.executable_path()).parent
    #: The location of sublime's python adapters b/w plugins and the proprietary `sublime_api`.
    stub: Directory = root / 'Lib' / VER_STR
    #: Distributed packages.
    dist: Directory = root / 'Packages'

    # ---- Misc ----
    console: Path = data / 'myBasis/console.log'

    @staticmethod
    def new(**kwargs: str | Path) -> dict[str, Path]:
        """Expand the given dictionary of paths, mapping names to Paths.

        Args:
            **kwargs: A mapping of string names to file paths (as strings or Paths).
        Returns:
            The paths mapping with all values now expanded to Paths.
        """
        return {key: Path(val).expanduser().resolve() for key, val in kwargs.items()}

    @staticmethod
    def normalize(path: str | Path) -> Path:
        """Expand a string path into a resolved Path object."""
        return _normalize(path)

    def __str__(self) -> str:
        attrs = self.model_dump()
        w = max(map(len, attrs.keys())) + 1
        return '\n'.join(
            [
                f'{self.__class__.__name__}:',
                *(f'\t{key:>{w}}: {val}' for key, val in attrs.items()),
            ]
        )

    @staticmethod
    @ft.lru_cache(maxsize=256)
    def compile_rgx(path: Path | str) -> re.Pattern[str]:
        """Compile a regex pattern matching the given path, allowing for relative leading parts."""
        pathstr = re.escape(str(path).strip('/'))
        return re.compile(rf'(?<![-\w\/.])(?:\.{{0,2}}\/)+({pathstr})(?![-.\w])(\/?)')

    @ft.cached_property
    def rgxs(self) -> dict[str, re.Pattern[str]]:
        """A list of regex patterns matching the paths in this registry."""
        return {name: self.compile_rgx(path) for name, path in reversed(self.model_dump().items())}


PATHS = PathRegistry()

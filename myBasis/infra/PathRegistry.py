############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from pathlib import Path
from sys import version_info
import functools as ft
import os
import tempfile
import warnings

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


def _existing_or_tmp(path: Path, name: str) -> Directory:
    """Return `path` if it's a real, existing directory, else a private tmp dir (warns).

    Guards fields resolved from plain env vars (e.g. `$HOME`) rather than through the `sublime`
    module's own mock/live fallback -- those can still point at a directory that doesn't actually
    exist (a bare CI container with an unusual `$HOME`), which would otherwise raise at
    `PathRegistry()` construction time.
    """
    if path.exists() and path.is_dir():
        return path
    warnings.warn(
        f'{name} directory {str(path)!r} does not exist; falling back to a temp directory.',
        stacklevel=3,
    )
    fallback = Path(tempfile.gettempdir()) / 'myBasis-registry' / name
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


class PathRegistry(pyd.BaseModel):
    """A registry of file paths, mapping short names to `Path` objects.

    `host`, `home`, `cache`, and `root` are resolved straight from the live (or mocked) `sublime`
    module and validated as real, existing directories. Everything else is *derived* from those and
    may not exist yet -- e.g. `Packages/myBasis` in a bare Python env with no live ST install --
    so those fields are left as plain, unvalidated `Path`s; call-sites are expected to create them
    on demand (mirroring `Utils.log_to_disk`'s `target.parent.mkdir(parents=True, exist_ok=True)`).
    """

    # ---- System ----
    host: Directory

    # ---- Main ----
    #: The main directory, usually in `$XDG_CONFIG`/`~/.config`.
    home: Directory
    #: Unzipped packages.
    pkgs: Path
    #: Installed (zipped) packages.
    inst: Path
    #: Package logs.
    logs: Path
    #: The location of importable libraries for plugins.
    venv: Path

    # ---- Packages ----
    #: The user package, which contains top-level settings and other overrides.
    user: Path
    #: The myBasis package, which contains the main code and resources for this plugin.
    base: Path

    # ---- Storage ----
    #: Root of caches for packages and sublime itself, usually in `$XDG_CACHE`/`~/.cache`.
    cache: Directory
    #: Package caches in particular.
    data: Path
    #: Shared storage for all packages using myBasis.
    my: Path

    # ---- Root ----
    #: The root of the installed application, usually in `/opt/sublime_text`.
    root: Directory
    #: The location of sublime's python adapters b/w plugins and the proprietary `sublime_api`.
    stub: Path
    #: Distributed packages.
    dist: Path

    # ---- Misc ----
    console: Path

    def __init__(self, **overrides: Path) -> None:
        """Resolve every field from the `sublime` module, lazily -- only at instantiation time.

        Class-body field defaults would run these `sb.*` calls at *import* time (as soon as
        `PathRegistry` is defined) -- exactly the eager-import problem this class used to have.
        Resolving here instead means importing this module is a no-op; only actually constructing
        a `PathRegistry` (i.e. accessing the module-level `PATHS` singleton) touches `sublime` or
        the filesystem.

        Args:
            **overrides: Explicit path overrides, keyed by field name (mainly for testing).
        """
        home = _normalize(sb.packages_path()).parent
        cache = _normalize(sb.cache_path())
        root = _normalize(sb.executable_path()).parent
        pkgs = home / 'Packages'
        data = cache.parent / 'Package Storage'
        my = data / 'my'

        resolved: dict[str, Path] = dict(
            host=_existing_or_tmp(_normalize(os.getenv('HOME', '~')), name='host'),
            home=home,
            pkgs=pkgs,
            inst=home / 'Installed Packages',
            logs=home / 'Logs',
            venv=home / 'Lib' / VER_STR,
            user=pkgs / 'User',
            base=pkgs / 'myBasis',
            cache=cache,
            data=data,
            my=my,
            root=root,
            stub=root / 'Lib' / VER_STR,
            dist=root / 'Packages',
            console=my / 'console.log',
        )
        resolved.update(overrides)
        super().__init__(**resolved)

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


_paths: PathRegistry | None = None


def __getattr__(name: str) -> PathRegistry:
    """Lazily build the shared `PATHS` singleton on first access (PEP 562).

    Defers `PathRegistry()` construction -- and therefore all `sublime`-module path resolution --
    to the first time calling code actually reaches for `PATHS`, instead of at import time.
    """
    global _paths
    if name != 'PATHS':
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
    if _paths is None:
        _paths = PathRegistry()
    return _paths

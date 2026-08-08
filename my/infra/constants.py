############
### HEAD ###
############
### STANDARD
from collections.abc import Generator, Iterator
from pathlib import Path, PosixPath, WindowsPath
from typing import TYPE_CHECKING, Self
import functools as ft
import os
from importlib.resources import files

### EXTERNAL
import regex as re
import pydantic as pyd

### INTERNAL
# NOTE: do not import anything from this package (to avoid circular imports)

if TYPE_CHECKING:
    import jinja2 as jn  # typing-only; the runtime import is deferred into `_jinja_env`

# The runtime API deliberately permits changing the default; the stub pins its initial literal.
re.DEFAULT_VERSION = re.VERSION1  # pyrefly: ignore[bad-assignment]


############
### DATA ###
############
class InfraPaths(pyd.BaseModel, arbitrary_types_allowed=True):
    """A model containing important paths within the package."""

    #: Root directory of the installed `my` package.
    my: Path = files('my')  # type: ignore

    #: The bundled resource directory, `my/data`.
    data: Path = files('my.data')  # type: ignore

    #: The bundled Jinja template directory, `my/data/templates`.
    templates: Path = data / 'templates'


#: Immutable object containing important paths within the package.
#: Use `INFRA_PATHS` to access these paths.
INFRA_PATHS: InfraPaths = InfraPaths()


#: Concrete platform path class used as the runtime base for `NOWHERE`.
_NowhereBase: type[Path] = WindowsPath if os.name == 'nt' else PosixPath

#: String-like path accepted by the stdlib `pathlib` APIs.
StrPath = str | os.PathLike[str]

#: String-or-bytes path accepted by the stdlib `pathlib` APIs.
StrOrBytesPath = str | bytes | os.PathLike[str] | os.PathLike[bytes]


#: Sentinel type returned when no usable filesystem path is available.
class _NowhereType(_NowhereBase):
    """A non-traversable filesystem sentinel.

    `NOWHERE` is the single, canonical representation of "no path" in `my`. It is a
    `Path` subclass so it passes `isinstance(..., Path)` checks and fits existing
    signatures, but every operation that would touch the filesystem fails closed:
    existence checks return ``False``, traversal yields nothing, and mutating calls
    raise `FileNotFoundError`.
    """

    _instance: Self | None = None

    def __new__(cls, *args: object, **kwargs: object) -> Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls, '.')
        return cls._instance

    def __str__(self) -> str:
        return '<NOWHERE>'

    def __repr__(self) -> str:
        return 'NOWHERE'

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _NowhereType)

    def __hash__(self) -> int:
        return hash(('<NOWHERE>',))

    def with_segments(self, *args: StrPath) -> Self:
        return self

    def resolve(self, strict: bool = False) -> Self:
        return self

    def absolute(self) -> Self:
        return self

    def expanduser(self) -> Self:
        return self

    def exists(self, *, follow_symlinks: bool = True) -> bool:
        return False

    def is_dir(self, *, follow_symlinks: bool = True) -> bool:
        return False

    def is_file(self, *, follow_symlinks: bool = True) -> bool:
        return False

    def is_symlink(self) -> bool:
        return False

    def is_mount(self) -> bool:
        return False

    def is_socket(self) -> bool:
        return False

    def is_fifo(self) -> bool:
        return False

    def is_block_device(self) -> bool:
        return False

    def is_char_device(self) -> bool:
        return False

    def iterdir(self) -> Generator[Self]:
        return
        yield  # type: ignore[unreachable]

    def glob(
        self, pattern: str, *, case_sensitive: bool | None = None, recurse_symlinks: bool = False
    ) -> Iterator[Self]:
        return iter(())

    def rglob(
        self, pattern: str, *, case_sensitive: bool | None = None, recurse_symlinks: bool = False
    ) -> Iterator[Self]:
        return iter(())

    def walk(
        self, top_down: bool = True, on_error=None, follow_symlinks: bool = False
    ) -> Generator[tuple[Self, list[str], list[str]]]:
        return
        yield  # type: ignore[unreachable]

    def read_text(self, *args: object, **kwargs: object) -> str:
        raise FileNotFoundError(self)

    def read_bytes(self, *args: object, **kwargs: object) -> bytes:
        raise FileNotFoundError(self)

    def write_text(self, *args: object, **kwargs: object) -> int:
        raise FileNotFoundError(self)

    def write_bytes(self, *args: object, **kwargs: object) -> int:
        raise FileNotFoundError(self)

    def touch(self, *args: object, **kwargs: object) -> None:
        raise FileNotFoundError(self)

    def mkdir(self, *args: object, **kwargs: object) -> None:
        raise FileNotFoundError(self)

    def unlink(self, *args: object, **kwargs: object) -> None:
        raise FileNotFoundError(self)

    def rmdir(self, *args: object, **kwargs: object) -> None:
        raise FileNotFoundError(self)

    def rename(self, target: StrPath) -> Self:
        raise FileNotFoundError(self)

    def replace(self, target: StrPath) -> Self:
        raise FileNotFoundError(self)

    def symlink_to(self, target: StrOrBytesPath, target_is_directory: bool = False) -> None:
        raise FileNotFoundError(self)

    def hardlink_to(self, target: StrOrBytesPath) -> None:
        raise FileNotFoundError(self)


#: The single canonical "no path" sentinel for the `my` package.
NOWHERE: _NowhereType = _NowhereType()


############
### BODY ###
############
# ---------
# CONSTANTS
# ---------
#: The package-wide separator used when joining rendered fragments (e.g. `Span` collections).
DELIM = ' // '


# -----
# JINJA
# -----
#: Cache for the package Jinja environment, built lazily by `_jinja_env`. Deferred so a
#: bare `import my` -- which reaches `infra` eagerly -- does not import `jinja2` or stat
#: the templates directory until a template is actually rendered.
_JINJA: 'jn.Environment | None' = None


def _jinja_env() -> 'jn.Environment':
    """Build the package Jinja environment once, on first use, and cache it.

    Reach the environment through the module-level `JINJA` attribute (kept for backward
    compatibility via `__getattr__`) or, preferably, through `get_template()`.
    """
    global _JINJA
    if _JINJA is None:
        import jinja2 as jn

        _JINJA = jn.Environment(
            loader=jn.PackageLoader('my.data', 'templates'),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    return _JINJA


@ft.lru_cache(maxsize=128)
def get_template(template_name: str) -> 'jn.Template':
    """Load and cache a Jinja2 template from the data/templates directory.

    Args:
        template_name: Name of template file.
    Returns:
        Compiled Jinja2 template.
    """
    return _jinja_env().get_template(template_name)


def __getattr__(name: str) -> object:
    """Expose the lazily-built Jinja environment as the module-level `JINJA` (PEP 562)."""
    if name == 'JINJA':
        return _jinja_env()
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')

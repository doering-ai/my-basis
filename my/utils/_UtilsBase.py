############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from types import ModuleType
from typing import ClassVar
import importlib

# I/O

### EXTERNAL

### INTERNAL
# Local imports

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..typing.Typist import Typist

############
### DATA ###
############


############
### BODY ###
############
class _UtilsBase:
    """Shared base class wiring a late-bound `Typist` instance into every utility class."""

    ty: ClassVar[Typist]

    @staticmethod
    def set_typist(ty: Typist) -> None:
        """Install the shared `Typist` instance used by every utility class."""
        _UtilsBase.ty = ty

    @staticmethod
    def typist() -> Typist:
        """Return the shared `Typist` instance, importing `my.typing` on first use.

        `my.typing` imports `utils`, so `utils` cannot import it back at load time. Instead the
        first call that needs a `Typist` (`ut.serialize()`, `ut.to_json()`, ...) imports it
        here; its last statement installs the instance through `set_typist()`. A caller that
        imports only `ut` therefore works without also importing `ty`, and `import my` stays
        cold. Every later call is a plain attribute read.

        Returns:
            The one `Typist` instance, shared by every utility class.
        Raises:
            AttributeError: If called while `my.typing` is still importing, before it has
                installed the instance (a plain error beats a silent import loop).
        """
        try:
            return _UtilsBase.ty
        except AttributeError:
            importlib.import_module('..typing', __package__)
        try:
            return _UtilsBase.ty
        except AttributeError:
            raise AttributeError(
                'The shared `Typist` is unavailable: `my.typing` is still initializing.'
            ) from None

    @staticmethod
    def _optional_import(name: str) -> ModuleType:
        """Import a `my-basis` runtime dependency on first use, naming it if absent.

        A handful of dependencies (`srsly`, `tomli_w`, `unidecode`) are declared in
        `pyproject.toml` like any other, but are imported lazily -- not as optional extras,
        rather so a bare `import my` stays usable in hosts (e.g. Sublime Text's plugin
        runtime) that provision Python packages separately from `uv`/PyPI. Every such call
        site routes through this helper so a missing dependency always raises the same,
        greppable message instead of a bare `ModuleNotFoundError` deep in a stack trace.

        Args:
            name: Importable module name (e.g. `'srsly'`).
        Returns:
            The imported module.
        Raises:
            ImportError: If the module is not installed, naming it explicitly.
        """
        try:
            return importlib.import_module(name)
        except ImportError as exc:
            raise ImportError(
                f'{name!r} is required for this feature. It is a my-basis dependency -- '
                f'install it (e.g. `uv sync`, or `pip install {name.replace("_", "-")}`).'
            ) from exc

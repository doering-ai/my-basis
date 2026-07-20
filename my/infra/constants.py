############
### HEAD ###
############
### STANDARD
from pathlib import Path
from typing import TYPE_CHECKING
import functools as ft
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

    my: Path = files('my')  # type: ignore
    data: Path = files('my.data')  # type: ignore
    templates: Path = data / 'templates'


#: Immutable object containing important paths within the package.
#: Use `INFRA_PATHS` to access these paths.
INFRA_PATHS: InfraPaths = InfraPaths()

############
### BODY ###
############
# ---------
# CONSTANTS
# ---------
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

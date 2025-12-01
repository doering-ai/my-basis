############
### HEAD ###
############
### STANDARD
from typing import TypeVar, Hashable
from collections import deque
from pathlib import Path
import functools as ft
from datetime import date, datetime, time, timedelta

### EXTERNAL
import jinja2 as jn

### INTERNAL
# NOTE: do not import anything from this package (to avoid circular imports)

############
### DATA ###
############
BASIS_DATA_DIR = Path(__file__).parent.parent / 'data'
assert BASIS_DATA_DIR.exists() and BASIS_DATA_DIR.is_dir()


############
### BODY ###
############
# ---------
# CONSTANTS
# ---------
DELIM = ' // '

# -----
# TYPES
# -----
T = TypeVar('T')
C = TypeVar('C')
Key = TypeVar('Key', bound=Hashable)
Keys = TypeVar('Keys', bound=tuple)
Value = TypeVar('Value')

Atomic = str | int | float | bool
Series = list | tuple | set | deque
MapItems = list[tuple] | tuple[tuple] | deque[tuple] | set[tuple]

AtomicType = type[str] | type[int] | type[float] | type[bool]
TimeType = date | datetime | time | timedelta

# -----
# JINJA
# -----
templates = BASIS_DATA_DIR / 'templates'
assert templates.exists() and templates.is_dir()
JINJA = jn.Environment(loader=jn.FileSystemLoader(templates), trim_blocks=True, lstrip_blocks=True)


@ft.lru_cache(maxsize=128)
def get_template(template_name: str) -> jn.Template:
    """
    Load and cache a Jinja2 template from the data/templates directory.

    Args:
        template_name: Name of template file.

    Returns:
        Compiled Jinja2 template.
    """
    return JINJA.get_template(template_name)

############
### HEAD ###
############
### STANDARD
from typing import TypeVar, Any
from collections.abc import Hashable, Iterable, Mapping, ItemsView
from collections import deque
from datetime import date, datetime, time, timedelta
from enum import Enum
from pathlib import Path
import functools as ft

### EXTERNAL
import jinja2 as jn
import regex as re

### INTERNAL
# NOTE: do not import anything from this package (to avoid circular imports)

re.DEFAULT_VERSION = re.VERSION1

############
### DATA ###
############
BASIS_ROOT_DIR = Path(__file__).parent
assert BASIS_ROOT_DIR.exists() and BASIS_ROOT_DIR.is_dir()

TEMPLATE_DIR = BASIS_ROOT_DIR / 'templates'
assert TEMPLATE_DIR.exists() and TEMPLATE_DIR.is_dir()

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
Key = TypeVar('Key', bound=Hashable)
Keys = TypeVar('Keys', bound=tuple)
Value = TypeVar('Value')

Series = list | tuple | set | deque
type _Series[V] = list[V] | tuple[V, ...] | set[V] | deque[V]

Map = Mapping[Any, Any] | Iterable[tuple[Any, Any]] | ItemsView
type _Map[K: Hashable, V] = Mapping[K, V] | list[tuple[K, V]] | ItemsView[K, V]

Time = date | datetime | time | timedelta
Atomic = str | int | float | bool | bytes | Enum | Time

# -----
# JINJA
# -----
JINJA = jn.Environment(
    loader=jn.FileSystemLoader(TEMPLATE_DIR),
    trim_blocks=True,
    lstrip_blocks=True,
)


@ft.lru_cache(maxsize=128)
def get_template(template_name: str) -> jn.Template:
    """Load and cache a Jinja2 template from the data/templates directory.

    Args:
        template_name: Name of template file.
    Returns:
        Compiled Jinja2 template.
    """
    return JINJA.get_template(template_name)

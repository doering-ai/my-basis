############
### HEAD ###
############
### STANDARD
from pathlib import Path
import functools as ft
from importlib.resources import files

### EXTERNAL
import jinja2 as jn
import regex as re
import pydantic as pyd

### INTERNAL
# NOTE: do not import anything from this package (to avoid circular imports)

re.DEFAULT_VERSION = re.VERSION1  # type: ignore


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
# To change settings, just modify the mutable object identified by this reference
JINJA = jn.Environment(
    # loader=jn.FileSystemLoader(INFRA_PATHS.templates),
    loader=jn.PackageLoader('my.data', 'templates'),
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

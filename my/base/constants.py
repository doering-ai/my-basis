############
### HEAD ###
############
### STANDARD
from pathlib import Path
import functools as ft

### EXTERNAL
import jinja2 as jn

### INTERNAL

############
### BODY ###
############
BASIS_DATA_DIR = Path(__file__).parent.parent / "data"
assert BASIS_DATA_DIR.exists() and BASIS_DATA_DIR.is_dir()

templates = BASIS_DATA_DIR / 'templates'
assert templates.exists() and templates.is_dir()
JINJA = jn.Environment(loader=jn.FileSystemLoader(templates), trim_blocks=True, lstrip_blocks=True)


@ft.lru_cache(maxsize=128)
def get_template(template_name: str) -> jn.Template:
    return JINJA.get_template(template_name)


DELIM = ' // '

############
### HEAD ###
############
### STANDARD
from pathlib import Path
from importlib import metadata

### EXTERNAL

### INTERNAL
from my import ut

############
### BODY ###
############
# https://www.sphinx-doc.org/en/master/usage/configuration.html
ROOT = Path(__file__).parent.parent.resolve()
ut.validate_dir(ROOT)

# -------
# Project
# -------
project = 'MyBasis'
author = 'Robb Doering'
# version = my.__version__
# release = '1.0.0'
version = metadata.version('MyBasis')
release = version

# -------
# General
# -------
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.napoleon', 'myst_parser']
templates_path = ['docs/_templates']
exclude_patterns = [
    '_build',
    '__pycache__',
    'Thumbs.db',
    '.DS_Store',
    '.venv',
    'node_modules',
    'build',
    'dist',
]


# ------
# APIDoc
# ------
# https://www.sphinx-doc.org/en/master/usage/extensions/apidoc.html
apidoc_modules = [
    dict(
        path='my',
        destination='docs/source',
        separate_modules=True,
        module_first=True,
    ),
]

# --------
# Napoleon
# --------
napoleon_google_docstring = True
napoleon_numpy_docstring = False
# napoleon_include_init_with_doc = False
# napoleon_include_private_with_doc = False
# napoleon_include_special_with_doc = True
# napoleon_use_admonition_for_examples = False
# napoleon_use_admonition_for_notes = False
# napoleon_use_admonition_for_references = False
# napoleon_use_ivar = False
# napoleon_use_param = True
# napoleon_use_rtype = True
# napoleon_preprocess_types = False
# napoleon_type_aliases = None
# napoleon_attr_annotations = True

# --------
# Markdown
# --------
# https://myst-parser.readthedocs.io/en/latest/syntax/optional.html
source_suffix = {
    '.rst': 'restructuredtext',
    '.my': 'markdown',
    '.md': 'markdown',
}

# ----
# HTML
# ----
html_theme = 'alabaster'
html_static_path = ['_static']

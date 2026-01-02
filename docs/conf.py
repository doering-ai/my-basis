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
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'myst_parser',
    'sphinx_last_updated_by_git',  # https://github.com/mgeier/sphinx-last-updated-by-git
    'hoverxref.extension',  # https://sphinx-hoverxref.readthedocs.io/en/latest/index.html
    'sphixext.opengraph',  # https://sphinxext-opengraph.readthedocs.io/en/latest/
    'notfound.extension',  # https://sphinx-notfound-page.readthedocs.io/en/latest/
]
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
# Python
# ------
# add_module_names = True
# modindex_common_prefix = []
python_display_short_literal_types = True
# python_maximum_signature_line_length = None
# python_trailing_comma_in_multi_line_signatures = True
python_use_unqualified_type_names = True
# trim_doctest_flags = True


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

################
### BUILDERS ###
################
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
html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

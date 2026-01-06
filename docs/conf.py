############
### HEAD ###
############
### STANDARD
from typing import Any, Literal
from pathlib import Path
from importlib import metadata

### EXTERNAL

### INTERNAL
from my import RegexStore
import my  # noqa: F401

############
### BODY ###
############
# https://www.sphinx-doc.org/en/master/usage/configuration.html
ROOT = Path(__file__).parent.parent.resolve()

DOC_DIR = '.'
SRC_DIR = './../my'
RST_DIR = './_source'
OUT_DIR = './_build'
JNJ_DIR = './_templates'
STC_DIR = './_static'


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
    'sphinx.ext.apidoc',
    'sphinx.ext.napoleon',
    # 'sphinx.ext.viewcode',
    'myst_parser',
    # 'sphinx_last_updated_by_git',  # https://github.com/mgeier/sphinx-last-updated-by-git
    # 'hoverxref.extension',  # https://sphinx-hoverxref.readthedocs.io/en/latest/index.html
    # 'sphinxext.opengraph',  # https://sphinxext-opengraph.readthedocs.io/en/latest/
    # 'notfound.extension',  # https://sphinx-notfound-page.readthedocs.io/en/latest/
]
templates_path = [str(JNJ_DIR)]
exclude_patterns = [
    '*/.git',
    '.DS_Store',
    '.venv',
    '__init__.py',
    '__pycache__',
    '_build',
    'build',
    'conf.py',
    'dist',
    'node_modules',
    'Thumbs.db',
]

# ------
# Python
# ------
# add_module_names = True
modindex_common_prefix = ['my.']
python_display_short_literal_types = True
# python_maximum_signature_line_length = None
# python_trailing_comma_in_multi_line_signatures = True
python_use_unqualified_type_names = True
# trim_doctest_flags = True

# -------
# AutoDoc
# -------

# autodoc_use_legacy_class_based =
# autoclass_content =
# autodoc_class_signature =
autodoc_member_order = 'bysource'
# autodoc_docstring_signature =
# autodoc_mock_imports =
# autodoc_typehints =
# autodoc_typehints_description_target =
# autodoc_type_aliases =
# autodoc_typehints_format =
# autodoc_preserve_defaults =
# autodoc_use_type_comments =
# autodoc_warningiserror =
# autodoc_inherit_docstrings =

autodoc_default_options = {
    # 'members': None,
    # 'undoc-members': None,
    # 'private-members': None,
    # 'special-members': None,
    # 'inherited-members': None,
    # 'imported-members': None,
    # 'exclude-members': None,
    # 'ignore-module-all': None,
    'member-order': 'bysource',
    # 'show-inheritance': None,
    # 'class-doc-from': None,
    # 'no-value': None,
    # 'no-index': None,
    # 'no-index-entry': None,
}


# ------
# APIDoc
# ------
# https://www.sphinx-doc.org/en/master/usage/extensions/apidoc.html
default = dict(
    destination=RST_DIR,
    separate_modules=True,
    module_first=True,
    exclude_patterns=[],
    # implicit_namespaces=True,
    # https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#directive-automodule
    automomdule_options=set(),
)
apidoc_modules = [
    default
    | dict(
        path=SRC_DIR,
        exclude_patterns=['*/meta'],
    )
]
# modules = [
#     dict(
#         path=f'{SRC_DIR}/utils',
#     ),
#     dict(
#         path=f'{SRC_DIR}/caches',
#     ),
#     dict(
#         path=f'{SRC_DIR}/typing',
#     ),
#     dict(
#         path=f'{SRC_DIR}/types',
#     ),
#     dict(
#         path=f'{SRC_DIR}/data',
#     ),
#     dict(
#         path=f'{SRC_DIR}/apis',
#     ),
#     dict(
#         path=f'{SRC_DIR}/regex',
#         exclude_patterns=['*/meta'],
#     ),
#     dict(
#         path=f'{SRC_DIR}/files',
#     ),
# ]
# apidoc_modules = [default | module for module in modules]

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
# myst_commonmark_only = False
# myst_disable_syntax = []
# myst_url_schemes = None
# myst_heading_anchors = None
# myst_heading_slug_func = None
# myst_substitutions = {}
# myst_html_meta = {}
# myst_footnote_transition = True
# myst_words_per_minute = 200
myst_enable_extensions = [
    'dollarmath',  # Enable parsing of dollar $ and $$ encapsulated math
    'replacements',  # Automatically convert some common typographic texts
    'html_admonition',  # Convert <div class="admonition"> elements to sphinx admonition nodes
    'html_image',  # Convert HTML <img> elements to sphinx image nodes
    'linkify',  # Automatically identify “bare” web URLs and add hyperlinks
    'deflist',  # Enable definition lists
    'fieldlist',  # Enable field lists
    # 'amsmath', # Enable direct parsing of amsmath LaTeX equations
    # 'colon_fence', # Enable code fences using ::: delimiters
    # 'smartquotes', # Automatically convert standard quotations to their opening/closing variants
    # 'substitution', # Substitute keys
    # 'tasklist', # Add check-boxes to the start of list items
]

# ----
# HTML
# ----
# html_theme = 'sphinx_rtd_theme' # The standard ReadTheDocs theme.
html_theme = 'furo'  # copied from https://more-itertools.readthedocs.io/en/stable/
pygments_style = 'sphinx'
pygments_dark_style = 'monokai'  # specific to `furo` theme
# html_theme_options=
# html_theme_path=
# html_style=
# html_title=
# html_short_title=
# html_baseurl=
# html_codeblock_linenos_style=
# html_context=
# html_logo=
# html_favicon=
# html_css_files=
# html_js_files=
html_static_path = [str(STC_DIR)]
# html_extra_path=
# html_last_updated_fmt=
# html_last_updated_use_utc=
# html_permalinks=
html_permalinks_icon = '#'
# html_sidebars=
# html_additional_pages=
# html_domain_indices=
# html_use_index=
# html_split_index=
# html_copy_source=
# html_show_sourcelink=
# html_sourcelink_suffix=
# html_use_opensearch=
# html_file_suffix=
# html_link_suffix=
html_show_copyright = False
# html_show_search_summary=
html_show_sphinx = False
# html_output_encoding=
# html_compact_lists=
# html_secnumber_suffix=
# html_search_language=
# html_search_options=
# html_search_scorer=
# html_scaled_image_link=
# html_math_renderer=

############
### MAIN ###
############
ObjType = Literal[
    'module',
    'class',
    'method',
    'function',
    'decorator',
    'attribute',
    'exception',
    'property',
    'data',
    'type',
]


_AUTODOC_SKIPS = RegexStore.new(
    skip_any=(
        '|',
        [
            r'^_.*',
            r'[[:upper:]\d_]+',
        ],
    ),
    skip_module='',
    skip_class='',
    skip_method='',
    skip_function='',
    skip_decorator='',
    skip_attribute='',
    skip_exception='',
    skip_property='',
    skip_data='',
    skip_type='',
)


def autodoc_skip_member(
    app: Any,
    obj_type: ObjType,
    name: str,
    obj: Any,
    skip: bool,
    options: Any,
) -> bool | None:
    return skip or bool(_AUTODOC_SKIPS.fullmatch(['skip_any', f'skip_{obj_type}'], name))


def autodoc_process_docstring(
    app: Any,
    obj_type: ObjType,
    name: str,
    obj: Any,
    options: Any,
    lines: list[str],
) -> None:
    pass


def autodoc_before_process_signature(app: Any, obj: Any, bound_method: bool) -> None:
    pass


def autodoc_process_signature(
    app: Any,
    obj_type: ObjType,
    name: str,
    obj: Any,
    options: Any,
    signature: str,
    return_annotation: str,
) -> tuple[str, str] | None:
    pass


def autodoc_process_bases(app: Any, name: str, obj: Any, _unused: Any, bases: list) -> None:
    pass


def setup(app: Any):
    app.connect('autodoc-skip-member', autodoc_skip_member)

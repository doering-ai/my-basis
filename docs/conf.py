############
### HEAD ###
############
### STANDARD
from typing import Any, Literal
from pathlib import Path
from importlib import metadata
import inspect

### EXTERNAL

### INTERNAL
from my import RegexStore, Buffer
import my

############
### BODY ###
############
# https://www.sphinx-doc.org/en/master/usage/configuration.html
ROOT = Path(__file__).parent.resolve()

DOC_DIR = '.'
API_DIR = './api'
OUT_DIR = './_build'

SRC_DIR = './../my'
JNJ_DIR = SRC_DIR + '/data/templates'


# -------
# Project
# -------
project = 'MyBasis'
author = 'Robb Doering'
version = metadata.version('my-basis')  # the [project].name in pyproject.toml
release = version

# -------
# General
# -------
default_role = 'literal'
extensions = [
    'sphinx.ext.autodoc',
    # 'sphinx.ext.apidoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.intersphinx',
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
    'coverage.md',  # stray coverage report, not part of the doc tree
    'DESIGN-*.md',  # design notes live alongside docs but are not built pages
    'dist',
    'node_modules',
    'Thumbs.db',
]

# myst-parser.readthedocs.io/en/latest/configuration.html#myst-warnings
suppress_warnings = [
    'myst.strikethrough',
    # Signature xrefs aren't load-bearing here (see `default_role`); without this, two documented
    # classes sharing a nested-class name (`RegexStore.Options` vs `Command.Options`) turn every
    # `Options` annotation into a fatal "more than one target" warning under --fail-on-warning.
    'ref.python',
]

# ------------
# Intersphinx
# ------------
# Resolve cross-references to stdlib/third-party types in autodoc signatures (pathlib.Path,
# datetime, collections.abc, pydantic, numpy, ...). Without these the nitpicky (`-n -W`) build
# fails: every external type in a docstring signature becomes an unresolved "target not found".
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'pydantic': ('https://docs.pydantic.dev/latest', None),
    'numpy': ('https://numpy.org/doc/stable', None),
    'more-itertools': ('https://more-itertools.readthedocs.io/en/stable', None),
}

# ------
# Python
# ------
# add_module_names = True
# modindex_common_prefix = ['my.']
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
    'class-doc-from': 'class',
    # Value reprs of data/attribute members (e.g. `RegexStore.META_RGXS`, a dict of compiled
    # patterns) are unreadable and get re-parsed as markup, spraying xref warnings. Hide them.
    'no-value': True,
    # 'no-index': None,
    # 'no-index-entry': None,
}


# ------
# APIDoc
# ------
# https://www.sphinx-doc.org/en/master/usage/extensions/apidoc.html
# default = dict(
#     destination=API_DIR,
#     separate_modules=True,
#     module_first=True,
#     exclude_patterns=[],
#     # implicit_namespaces=True,
#     # https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#directive-automodule
#     # automomdule_options=set(),
# )
# apidoc_modules = [
#     default
#     | dict(
#         path=SRC_DIR,
#         exclude_patterns=[
#             '*/meta',
#             '*/MyEnumRow.py',
#         ],
#     ),
# ]

# rstdir = (ROOT / API_DIR).absolute()
# if rstdir.exists() and rstdir.is_dir():
#     print(f'DELETING EXISTING RST FILES in {rstdir}')
#     Command.run('rm', f'{rstdir}/my.*.rst', f'{rstdir}/modules.rst')


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
myst_heading_anchors = 3
# myst_heading_slug_func = None
# myst_substitutions = {}
# myst_html_meta = {}
# myst_footnote_transition = True
# myst_words_per_minute = 200
myst_enable_extensions = [
    # 'amsmath', ## Enable direct parsing of amsmath LaTeX equations
    'attrs_inline',  # Enable inline attribute lists
    'colon_fence',  ## Enable code fences using ::: delimiters
    'deflist',  # Enable definition lists
    'dollarmath',  # Enable parsing of dollar $ and $$ encapsulated math
    'fieldlist',  # Enable field lists
    'html_admonition',  # Convert <div class="admonition"> elements to sphinx admonition nodes
    'html_image',  # Convert HTML <img> elements to sphinx image nodes
    'linkify',  # Automatically identify “bare” web URLs and add hyperlinks
    'replacements',  # Automatically convert some common typographic texts
    # 'smartquotes', ## Automatically convert standard quotations to their opening/closing variants
    'strikethrough',  # Enable strikethrough using ~~del~~ syntax
    # 'substitution', ## Substitute keys
    # 'tasklist', ## Add check-boxes to the start of list items
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
# html_static_path=
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


RGXS = RegexStore.new(
    options=dict(
        force_named_groups=True,
        lazy_load=True,
    ),
    symbol=r'\b[_[:alpha:]]\w*\b',
    envvar=r'\$[_[:upper:]]+\b',
    autodoc_skip=(
        '|:',
        [
            r'^_.*',
            r'[[:upper:]\d_]+',
        ],
    ),
    local_reference=r'(?<![\}\\])`((\.?(?P>symbol))+(?P<parens>\(\))?|(?P>envvar))`(?!`)',
)


def autodoc_skip_member(
    app: Any,
    obj_type: ObjType,
    name: str,
    obj: Any,
    skip: bool,
    options: Any,
) -> bool | None:
    """Decide whether to skip a member."""
    return skip or bool(RGXS.fullmatch('autodoc_skip', name))


def _get_symbol(container: object, container_name: str, *path: str) -> tuple[str, object] | None:
    if not path:
        return None
    elif path[0] == getattr(container, '__name__', ''):
        path = path[1:]

    obj = container
    for part in path:
        obj = getattr(obj, part, None)
        if obj is None:
            return None
    return '.'.join(path), obj


def _child_ref(obj: Any, ref_symbols: list[str]) -> object | None:
    return _get_symbol(obj, *ref_symbols)


def _sibling_ref(obj: Any, ref_symbols: list[str]) -> object | None:
    if (
        (qname := getattr(obj, '__qualname__', None))
        and '.' in qname
        and (parent := _get_symbol(my, *qname.split('.')[:-1]))
    ):
        return _get_symbol(parent, *ref_symbols)
    return None


def _mod_ref(obj: Any, ref_symbols: list[str]) -> object | None:
    if (mname := getattr(obj, '__module__', None)) and (
        module := _get_symbol(my, *mname.split('.'))
    ):
        return _get_symbol(module, *ref_symbols)
    return None


def _global_ref(ref_symbols: list[str]) -> object | None:
    return _get_symbol(my, *ref_symbols)


def _expand_reference(ref_symbols: list[str], obj: Any) -> str:
    if not (ref_symbols and all(map(str.isidentifier, ref_symbols))):
        return ''

    ref = None
    if ref := _child_ref(obj, ref_symbols) or _sibling_ref(obj, ref_symbols):
        is_member = True
    elif ref := _global_ref(ref_symbols) or _mod_ref(obj, ref_symbols):
        is_member = '.' in getattr(obj, '__qualname__', '')
    else:
        return ''

    if inspect.isclass(ref):
        role = 'class'
    elif inspect.ismethod(ref):
        role = 'meth'
    elif inspect.isfunction(ref):
        role = 'func'
    elif is_member:
        role = 'attr'
    elif ref_symbols[-1].isupper():
        role = 'const'
    else:
        role = 'data'
    return f'{{py:{role}}}`{ref}`'


def autodoc_process_docstring(
    app: Any,
    obj_type: ObjType,
    name: str,
    obj: Any,
    options: Any,
    lines: list[str],
) -> None:
    """Modifies `lines` in place."""
    for i, line in enumerate(lines):
        if '`' not in line:
            continue

        buf = Buffer.new(line)
        did_change = False
        for match in RGXS.finditer('local_reference', buf):
            if var := match.at('envvar').strip('$'):
                newtext = f'{{envvar}}`{var}`'
                buf.replace(match.span, newtext)
                did_change = True
                continue

            if newtext := _expand_reference(match['symbol'], obj):
                buf.replace(match.span, newtext)
                did_change = True

        if did_change:
            print(f'\n  DOC REF: {line} --> {buf}\n')
            lines[i] = str(buf)


# def autodoc_before_process_signature(app: Any, obj: Any, bound_method: bool) -> None:
#     pass


# def autodoc_process_signature(
#     app: Any,
#     obj_type: ObjType,
#     name: str,
#     obj: Any,
#     options: Any,
#     signature: str,
#     return_annotation: str,
# ) -> tuple[str, str] | None:
#     pass


# def autodoc_process_bases(app: Any, name: str, obj: Any, _unused: Any, bases: list) -> None:
#     pass


def setup(app: Any):
    """Register custom Sphinx event handlers."""
    # app.connect('autodoc-skip-member', autodoc_skip_member)
    # app.connect('autodoc-process-docstring', autodoc_process_docstring)

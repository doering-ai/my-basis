"""Deprecated compatibility shim for the old `my.text` subpackage.

`my.text` was split apart during the 2025-11 subpackage reorganization (commit `05e1b98`):
regex-related symbols moved to `my.regex`, `Buffer`/`Span` moved to `my.types`, and `Markdown`
moved to `my.files`. This shim re-exports the current surface under the old import path so
pre-existing downstream imports (wikiparse, arch) keep working, emitting a `DeprecationWarning`
to push migration toward the new paths. Remove once those consumers migrate off `my.text`.

Symbols intentionally NOT aliased (no unambiguous modern equivalent):
    atom: the old regex-snippet-builder helper has no modern counterpart; `RgxAtom` in
        `my.regex` is an unrelated AST node class from the meta parser.
    debug_regex: the old free function `debug_regex(store, names, text, matched, ...)` became
        the instance method `RegexDebugger(...).debug(...)`, which needs a store instance at
        call time -- there is no drop-in function form.
"""

import warnings

import my.regex as _regex
from my.files import Markdown
from my.regex import *  # noqa: F403
from my.regex import RegexStore, RegexVal
from my.types import Buffer, Span

warnings.warn(
    'my.text is deprecated and will be removed; import from my.regex instead '
    '(Buffer/Span moved to my.types, Markdown moved to my.files).',
    DeprecationWarning,
    stacklevel=2,
)

#: Unambiguous old -> new symbol aliases.
RgxVal = RegexVal
format_url = RegexStore.format_url

__all__ = [*_regex.__all__, 'Buffer', 'Span', 'Markdown', 'RgxVal', 'format_url']

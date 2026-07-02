"""Pure, Typed Functional Utilities.

The `utils` subpackage provides a comprehensive collection of utility functions organized into
specialized classes that are combined into a unified `Utils` interface and exported under the alias
`ut`. This design allows methods to be called as `ut.method()` regardless of which utility class
defines them, providing a clean, flat namespace for common operations.

Individual utility classes can still be imported for more specific use cases or when a smaller
import footprint is desired.
"""

from typing import ClassVar

import regex as re

from .IterUtils import IterUtils, iter_utils
from .SyntaxUtils import SyntaxUtils, syntax_utils  # <- iter
from .TextUtils import TextUtils, text_utils  # <- iter
from .SemanticUtils import SemanticUtils, semantic_utils  # <- text, iter
from .SystemUtils import SystemUtils, system_utils  # <- text, iter
from .MetricUtils import MetricUtils, metric_utils  # <- system (<- text <- iter)


class Utils(IterUtils, TextUtils, SystemUtils, SemanticUtils, SyntaxUtils, MetricUtils):
    """A class combining all of the the utility classes into one convenient static interface."""

    # `TextUtils` and `SystemUtils` each declare their own `RGXS` ClassVar; plain multiple
    # inheritance would let MRO order silently shadow one with the other (whichever base is
    # listed first "wins" for every subclass, including this one), leaving classmethods that
    # were written against the shadowed dict (e.g. `SystemUtils.from_file`) raising `KeyError`
    # the moment they're invoked through the combined `Utils`/`ut` facade instead of their own
    # class directly. Re-merge both dicts explicitly so every inherited method sees its keys.
    RGXS: ClassVar[dict[str, re.Pattern]] = TextUtils.RGXS | SystemUtils.RGXS


ut = Utils
utils = Utils


__all__ = [
    'Utils',
    'ut',
    'utils',
    'IterUtils',
    'iter_utils',
    'TextUtils',
    'text_utils',
    'SystemUtils',
    'system_utils',
    'SemanticUtils',
    'semantic_utils',
    'SyntaxUtils',
    'syntax_utils',
    'MetricUtils',
    'metric_utils',
]

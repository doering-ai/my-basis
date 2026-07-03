"""Internal Regex Metatypes.

This subpackage contains a variety of classes (and a few constants!) for representing, analyzing,
and modifying regular expressions in a structured manner. As opposed to the internal types within
Python's standard `re` library, these types are **not** built to support regex evaluation; instead,
they provide a more modern, ergonomic way to work with regular expressions *before* they're
evaluated.

These modules are described as "internal" because they were clearly designed with the specific
needs of `RegexStore` in mind--namely, optimizing branching expressions (e.g. `a|b`) and debugging
complex expressions of any kind--but they are made available in the public API nonetheless. If you
extend them, please consider submitting a PR so that others can benefit from your work!
"""

from .meta_rgxs import META_RGXS, FLAGS, NO_ESC, NON_ESC, QUANT
from .ParseData import ParseData
from .Quantifier import Quantifier
from .GroupKind import GroupKind
from .Atom import Atom
from .GroupAtom import GroupAtom
from .SetAtom import SetAtom
from .Regex import Regex
from .Tree import Tree

__all__ = [
    'Atom',
    'FLAGS',
    'GroupAtom',
    'GroupKind',
    'META_RGXS',
    'NO_ESC',
    'NON_ESC',
    'ParseData',
    'QUANT',
    'Quantifier',
    'Regex',
    'SetAtom',
    'Tree',
]

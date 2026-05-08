"""Optimized, Readable Regular Expressions

The `regex` subpackage provides a comprehensive framework for working with advanced regular expressions, built on top of the `regex` library (which extends Python's standard `re` module with additional features). The package is organized into two main components: high-level pattern management tools in the main directory, and low-level regex parsing and manipulation utilities in the `meta` subdirectory.
"""
from .meta import META_RGXS, ParseData, Quantifier, GroupKind, Atom, GroupAtom, SetAtom, Regex, Tree
from .MatchData import MatchData
from .RegexStore import RegexStore, RegexParser, RegexTup, RegexList, RegexVal, RegexDef
from .common_rgxs import COMMON_RGXS
from .RegexDebugger import RegexDebugger

__all__ = [
    'RegexStore',
    'RegexDebugger',
    'GroupKind',
    'Atom',
    'GroupAtom',
    'SetAtom',
    'Regex',
    'Tree',
    'Quantifier',
    'MatchData',
    'ParseData',
    'RegexParser',
    'RegexTup',
    'RegexList',
    'RegexVal',
    'RegexDef',
    'META_RGXS',
    'COMMON_RGXS',
]

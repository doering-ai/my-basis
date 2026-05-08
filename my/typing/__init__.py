"""Vibe Typists

This subpackage provides tools for advanced type operations: parsing, checking, matching, coercion, manipulation, and more, alongside some high-level functional utilities built upon those features. The vast majority of the logic is implemented within the (mostly-)static class `Typist`.

All of this is facetiously referred to as "Vibe Typing" throughout these docs (which, yes, is intended to strike fear into the hearts of men!) because of its original usecase: coercing the "tool call" outputs of intuitive LLMs to match the strict syntactical requirements of downstream tools.
Obviously most traditional programs explicitly *don't* want to silently correct mistakes in data, but if that's you, you may still find some of these functions useful on a piecemeal basis!
"""
from .MyType import MyType
from .Typist import Typist, typist, TypeArg
from .AutocastModel import AutocastModel

__all__ = [
    "MyType",
    "Typist",
    "typist",
    "TypeArg",
    "AutocastModel",
]

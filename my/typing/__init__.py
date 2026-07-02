"""Utilities for the parsing, checking, matching, coercion, and manipulation of Python types.

This subpackage provides tools for advanced type operations: parsing, checking, matching, coercion,
manipulation, and more, alongside some high-level functional utilities built upon those features.
The vast majority of the logic is implemented within the (mostly-)static class `Typist`.

I may facetiously refer to this "Vibe Typing" throughout these docs because of its original usecase:
coercing the attempts of latent models to output symbolic data, an event that occurs every time a
chatbot or agent calls a tool beyond itself.

One could use this library to add some 'just-in-case' magic to one of the many existing solutions,
but I was personally motivated by the kind of second-level flexibility only possible when working
in a system diffuse with these tools (secret, Free, open-source, or otherwise).
"""

from .MyType import MyType, TypeArg
from .match import tym, TypeMatch
from .check import tyc, TypeCheck
from .cast import tyt, TypeCast as TypeCast, CastFlags
from .Typist import Typist, typist, ty
from .AutocastModel import AutocastModel

TypeCast.setup()

__all__ = [
    'AutocastModel',
    'CastFlags',
    'MyType',
    'ty',
    'tyc',
    'tym',
    'TypeArg',
    'TypeCast',
    'TypeCheck',
    'TypeMatch',
    'Typist',
    'typist',
    'tyt',
]

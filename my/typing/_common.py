############
### HEAD ###
############
### STANDARD
from __future__ import annotations
import typing
import collections.abc as abc

### EXTERNAL

### INTERNAL
# from .MyType import MyType

# Auxiliary & Meta Types

ABSTRACT_GENERICS = dict(
    maps=(typing.Mapping, abc.Mapping, abc.MutableMapping),
    vecs=(
        typing.Iterable,
        typing.Sequence,
        typing.Collection,
        abc.Sequence,
        abc.Collection,
        abc.Iterable,
    ),
    sets=(
        typing.AbstractSet,
        abc.Set,
        abc.MutableSet,
    ),
)

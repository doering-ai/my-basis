############
### HEAD ###
############
### STANDARD
from typing import Any, TypeAlias
import typing
import collections.abc as abc

### EXTERNAL

### INTERNAL
from .MyType import MyType

# Auxiliary & Meta Types
type TypeArg[T = Any] = type[T] | MyType[T] | tuple[type[T], ...] | TypeAlias | Any | None
type AnyType[T] = type[T] | MyType[T]

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

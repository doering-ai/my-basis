############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import Any, IO
from collections.abc import (
    Callable,
    Hashable,
    Iterable,
    Mapping,
    ItemsView,
    Set,
    AsyncIterable,
)
from types import BuiltinFunctionType, FunctionType, NoneType
from collections import deque
from datetime import date, datetime, time, timedelta
from enum import Enum
from array import array
import itertools as it

### EXTERNAL
import pydantic as pyd
import more_itertools as mi

### INTERNAL

### ALIASES


############
### BODY ###
############

# ------------
# Type Aliases
# ------------
# ---- Scalars ----
Stream = bytearray | memoryview | IO
String = str | bytes | Stream

Scalar = int | float | complex | bool
Real = int | float | bool
#: The ordered subset of `Scalar` -- excludes `complex`, which has no `<`/`>`.

Time = date | time | datetime | timedelta

Atom = String | Scalar | Time | Enum

# ---- Structs ----

Vec = list | tuple | Set | deque | array | range
type _Vec[V] = list[V] | tuple[V, ...] | Set[V] | deque[V] | array | range

Map = Mapping[Hashable, Any] | Iterable[tuple[Hashable, Any]] | ItemsView
type _Map[K: Hashable, V] = Mapping[K, V] | Iterable[tuple[K, V]] | ItemsView[K, V]

Dataclass = object
Model = pyd.BaseModel | Dataclass
# No plural -- must use `my.check.is_model`

Iter = Iterable | AsyncIterable
type _Iter[T] = Iterable[T] | AsyncIterable[T]

Struct = Vec | Map | Model
type _Struct[V, K: Hashable = Any] = _Vec[V] | _Map[K, V] | _Iter[V] | Model

# ---- Misc ----
Func = FunctionType | BuiltinFunctionType
type _Func[**PSpec, R = Any] = Callable[PSpec, R]

Object = Atom | Struct | Func

# ----------------
# Type Collections
# ----------------
Streams = (bytearray, memoryview, IO)
Strings = (str, bytes, *Streams)
Scalars = (int, float, complex, bool)
Reals = (int, float, bool)
Times = (date, time, datetime, timedelta)
Enums = (Enum,)
Atoms = (*Strings, *Scalars, *Times, *Enums)
Vecs = (list, tuple, Set, deque)
Maps = (Mapping, ItemsView)  #: NOTE: Does not cover lists of (key, val) pairs.
Models = (pyd.BaseModel,)  #: NOTE: Does not cover dataclasses
Structs = (*Vecs, *Maps, *Models)
Funcs = (FunctionType, BuiltinFunctionType, Callable)
Iters = (Iterable, AsyncIterable)
Objects = (*Atoms, *Structs, *Funcs)
TYPESET = {*Atoms, *Structs, *Funcs}


# -----------
# Exploratory
# -----------
# type Pair[K: Object, T2: Object = T1] = tuple[T1, T2]
class Pair[T1: Object, T2: Object = T1](tuple[T1, T2]):
    """A pair of objects, potentially of different types."""

    @classmethod
    def __instancecheck__(cls, val: object) -> bool:
        return bool(
            (isinstance(val, tuple) and len(val) == 2)
            and all(it.starmap(isinstance, zip(val, cls._args(), strict=False)))
        )

    @classmethod
    def _args(cls) -> tuple[type, type]:
        if args := getattr(cls, '__args__', None):
            a0, a1 = mi.padded(args, Object)
        else:
            a0, a1 = Object, Object
        return (a0 if isinstance(a0, type) else NoneType), (
            a1 if isinstance(a1, type) else NoneType
        )


type Quad[T1, T2 = T1] = tuple[Pair[T1, T2], Pair[T1, T2]]
type Oct[T1, T2 = T1] = tuple[Quad[T1, T2], Quad[T1, T2]]

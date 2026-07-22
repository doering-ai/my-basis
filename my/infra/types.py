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
#: Mutable byte buffers and open file-like objects -- text that streams rather than sits.
Stream = bytearray | memoryview | IO
#: Textual data in any raw form: `str`, `bytes`, or a `Stream`.
String = str | bytes | Stream

#: Numeric leaf values, including `complex` and `bool`.
Scalar = int | float | complex | bool
#: The ordered subset of `Scalar` -- excludes `complex`, which has no `<`/`>`.
Real = int | float | bool

#: Any of the stdlib `datetime` value types.
Time = date | time | datetime | timedelta

#: Any indivisible leaf value: a `String`, `Scalar`, `Time`, or `Enum` member.
Atom = String | Scalar | Time | Enum

# ---- Structs ----

#: Ordered, index-addressable containers.
Vec = list | tuple | Set | deque | array | range
#: The generic (parametrizable) form of `Vec`, e.g. `VecT[int]`.
type VecT[V] = list[V] | tuple[V, ...] | Set[V] | deque[V] | array | range

#: Key-addressable containers, including iterables of `(key, value)` pairs.
Map = Mapping[Hashable, Any] | Iterable[tuple[Hashable, Any]] | ItemsView
#: The generic (parametrizable) form of `Map`, e.g. `MapT[str, int]`.
type MapT[K: Hashable, V] = Mapping[K, V] | Iterable[tuple[K, V]] | ItemsView[K, V]

#: Any dataclass-shaped object; a structural stand-in, since dataclasses share no base class.
Dataclass = object
#: Attribute-addressable records: pydantic models and dataclasses.
#: No plural collection exists -- use `ty.is_model` for runtime checks.
Model = pyd.BaseModel | Dataclass

#: Anything iterable, synchronously or asynchronously.
Iter = Iterable | AsyncIterable
type _Iter[T] = Iterable[T] | AsyncIterable[T]

#: Any container of other values: a `Vec`, `Map`, or `Model`.
Struct = Vec | Map | Model
#: The generic (parametrizable) form of `Struct`, e.g. `StructT[int]`.
type StructT[V, K: Hashable = Any] = VecT[V] | MapT[K, V] | _Iter[V] | Model

# ---- Misc ----
#: Plain functions, by exact type -- excludes arbitrary callables like partials and lambdas' kin.
Func = FunctionType | BuiltinFunctionType
#: The generic (parametrizable) form of a callable, e.g. `FuncT[[int, str], bool]`.
type FuncT[**PSpec, R = Any] = Callable[PSpec, R]

#: The universal alias: any `Atom`, `Struct`, or `Func`.
Object = Atom | Struct | Func

# ----------------
# Type Collections
# ----------------
# Each plural name is the `isinstance`-safe tuple counterpart of its singular alias above.
Streams = (bytearray, memoryview, IO)
Strings = (str, bytes, *Streams)
Scalars = (int, float, complex, bool)
Reals = (int, float, bool)
Times = (date, time, datetime, timedelta)
Enums = (Enum,)
Atoms = (*Strings, *Scalars, *Times, *Enums)
Vecs = (list, tuple, Set, deque)  #: NOTE: Unlike `Vec`, does not cover `array` or `range`.
Maps = (Mapping, ItemsView)  #: NOTE: Does not cover lists of (key, val) pairs.
Models = (pyd.BaseModel,)  #: NOTE: Does not cover dataclasses.
Structs = (*Vecs, *Maps, *Models)
Funcs = (FunctionType, BuiltinFunctionType, Callable)  #: NOTE: Wider than `Func` -- any callable.
Iters = (Iterable, AsyncIterable)
Objects = (*Atoms, *Structs, *Funcs)
#: The full set of leaf types the package's coercion machinery recognizes.
TYPESET = {*Atoms, *Structs, *Funcs}


# -----------
# Exploratory
# -----------
# type Pair[K: Object, T2: Object = T1] = tuple[T1, T2]
class Pair[T1: Object, T2: Object = T1](tuple[T1, T2]):
    """A pair of objects, potentially of different types."""

    @classmethod
    def __instancecheck__(cls, val: object) -> bool:
        return (isinstance(val, tuple) and len(val) == 2) and all(
            it.starmap(isinstance, zip(val, cls._args(), strict=False))
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

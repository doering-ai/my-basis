############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import Any, Generic, IO
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
# PEP 696 type-parameter defaults are 3.13 syntax, but `typing_extensions` backports the
# runtime objects to our 3.12 floor. Aliases whose defaults are load-bearing (`StructT[V]`
# and `Pred[V]` are both subscripted below their full arity, in this package and by callers)
# are therefore declared in the explicit `TypeVar`/`TypeAliasType` form rather than with the
# `type X[T = ...]` statement. Everything without a default keeps the PEP 695 syntax, which
# 3.12 supports natively.
from typing_extensions import ParamSpec, TypeAliasType, TypeVar  # noqa: UP035
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
_V = TypeVar('_V')
_K = TypeVar('_K', bound=Hashable, default=Any)
StructT = TypeAliasType(  # noqa: UP040
    'StructT', VecT[_V] | MapT[_K, _V] | _Iter[_V] | Model, type_params=(_V, _K)
)

# ---- Misc ----
#: Plain functions, by exact type -- excludes arbitrary callables like partials and lambdas' kin.
Func = FunctionType | BuiltinFunctionType
#: The generic (parametrizable) form of a callable, e.g. `FuncT[[int, str], bool]`.
_PSpec = ParamSpec('_PSpec')
_R = TypeVar('_R', default=Any)
FuncT = TypeAliasType('FuncT', Callable[_PSpec, _R], type_params=(_PSpec, _R))  # noqa: UP040

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
_T1 = TypeVar('_T1', bound=Object)
_T2 = TypeVar('_T2', bound=Object, default=_T1)


class Pair(tuple[_T1, _T2], Generic[_T1, _T2]):
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


_Q1 = TypeVar('_Q1')
_Q2 = TypeVar('_Q2', default=_Q1)
Quad = TypeAliasType('Quad', tuple[Pair[_Q1, _Q2], Pair[_Q1, _Q2]], type_params=(_Q1, _Q2))  # noqa: UP040
Oct = TypeAliasType('Oct', tuple[Quad[_Q1, _Q2], Quad[_Q1, _Q2]], type_params=(_Q1, _Q2))  # noqa: UP040

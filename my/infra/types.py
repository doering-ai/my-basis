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
from types import BuiltinFunctionType, FunctionType
from collections import deque
from datetime import date, datetime, time, timedelta
from enum import Enum, Flag, auto

### EXTERNAL
import pydantic as pyd

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

Time = date | time | datetime | timedelta

Atom = String | Scalar | Time | Enum

# ---- Structs ----
Vec = list | tuple | Set | deque
type _Vec[V] = list[V] | tuple[V, ...] | Set[V] | deque[V]

Map = Mapping[Hashable, Any] | Iterable[tuple[Hashable, Any]] | ItemsView
type _Map[K: Hashable, V] = Mapping[K, V] | Iterable[tuple[K, V]] | ItemsView[K, V]

Dataclass = object
Model = pyd.BaseModel | Dataclass
# No plural -- must use `my.check.is_model`

Iter = Iterable | AsyncIterable
type _Iter[T] = Iterable[T] | AsyncIterable[T]

Struct = Vec | Map | Iter | Model
type _Struct[T0, T1 = Any] = _Vec[T0] | _Map[T0, T1] | _Iter[T0] | Model

# ---- Funcs ----
type Func = FunctionType | BuiltinFunctionType
type _Func[**PSpec, R = Any] = Callable[PSpec, R]

# ---- Object ----
type Object = Atom | Struct | Func

# ----------------
# Type Collections
# ----------------
Streams = (bytearray, memoryview, IO)
Strings = (str, bytes, *Streams)
Scalars = (int, float, complex, bool)
Times = (date, time, datetime, timedelta)
Atoms = (*Strings, *Scalars, *Times, Enum)
Vecs = (list, tuple, Set, deque)
Maps = (Mapping, ItemsView)  #: NOTE: Does not cover lists of (key, val) pairs.
Iters = (Iterable, AsyncIterable)
Structs = (*Vecs, *Maps, *Iters, pyd.BaseModel)
Funcs = (FunctionType, BuiltinFunctionType, Callable)
Objects = (*Atoms, *Structs, *Funcs)
TYPESET = {*Atoms, *Structs, *Funcs}


# -----------------
# Type Enumerations
# -----------------
class KnownType(Flag):
    """Enum of known types for type checking and error reporting."""

    # ---- Scalars ----
    INT = auto()
    FLOAT = auto()
    COMPLEX = auto()
    BOOL = auto()
    SCALAR = INT | FLOAT | COMPLEX | BOOL

    DATE = auto()
    TIME = auto()
    DATETIME = auto()
    TIMESPAN = auto()
    TIMES = DATE | TIME | DATETIME | TIMESPAN

    STR = auto()
    BYTES = auto()

    BYTEARRAY = auto()
    MEMORYVIEW = auto()
    IO = auto()
    STREAM = BYTEARRAY | MEMORYVIEW | IO

    STRING = STR | BYTES | STREAM

    FLAG = auto()
    STR_ENUM = auto()
    INT_ENUM = auto()
    ENUM = FLAG | STR_ENUM | INT_ENUM

    # ---- Structs ----
    LIST = auto()
    TUPLE = auto()
    SET = auto()
    DEQUE = auto()
    VEC = LIST | TUPLE | SET | DEQUE

    MAPPING = auto()
    ITEMSVIEW = auto()
    MAP = MAPPING | ITEMSVIEW

    ITERABLE = auto()
    ASYNCITERABLE = auto()
    ITER = ITERABLE | ASYNCITERABLE

    BASEMODEL = auto()
    DATACLASS = auto()
    MODEL = BASEMODEL | DATACLASS

    STRUCT = VEC | MAP | ITER | MODEL

    # ---- Funcs ----
    FUNC = auto()

    OBJECT = SCALAR | TIMES | STRING | ENUM | STRUCT | FUNC


# -----------
# Exploratory
# -----------
Series = Vec | Iter
type _Series[T] = _Vec[T] | _Iter[T]
Serieses = (Vecs, Iters)

Pair = tuple[Any, Any]
type _Pair[T] = tuple[T, T]

Quad = tuple[Pair, Pair]
type _Quad[T] = tuple[tuple[T, T], tuple[T, T]]

############
### HEAD ###
############
### STANDARD
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
type Stream = bytearray | memoryview | IO
Streams = (bytearray, memoryview, IO)
type String = str | bytes | Stream
Strings = (str, bytes, *Streams)

type Scalar = int | float | complex | bool
Scalars = (int, float, complex, bool)

type Time = date | time | datetime | timedelta
Times = (date, time, datetime, timedelta)

type Atom = String | Scalar | Time | Enum
Atoms = (*Strings, *Scalars, *Times, Enum)

# ---- Structs ----
type Vec = list | tuple | Set | deque
type _Vec[V] = list[V] | tuple[V, ...] | Set[V] | deque[V]
Vecs = (list, tuple, Set, deque)

type Map = Mapping[Hashable, Any] | list[tuple[Hashable, Any]] | ItemsView
type _Map[K: Hashable, V] = Mapping[K, V] | list[tuple[K, V]] | ItemsView[K, V]
Maps = (Mapping, ItemsView)  #: NOTE: Does not cover lists of (key, val) pairs.

type Dataclass = object
type Model = pyd.BaseModel | Dataclass
# No plural -- must use `my.check.is_model`

type Iter = Iterable | AsyncIterable
type _Iter[T] = Iterable[T] | AsyncIterable[T]
Iters = (Iterable, AsyncIterable)

type Struct = Vec | Map | Iter | Model
type _Struct[T0, T1 = Any] = _Vec[T0] | _Map[T0, T1] | _Iter[T0] | Model
Structs = (*Vecs, *Maps, *Iters, pyd.BaseModel)

# ---- Funcs ----
type Func = FunctionType | BuiltinFunctionType
type _Func[**PSpec, R = Any] = Callable[PSpec, R]
Funcs = (FunctionType, BuiltinFunctionType, Callable)

# ---- Object ----
type Object = Atom | Struct | Func
Objects = (*Atoms, *Structs, *Funcs)

TYPESET = {*Atoms, *Structs, *Funcs}


class Types(Flag):
    """Convient comparison method for hierarchical types."""

    # ---- Atom----
    BUFFER = auto()
    STRING = auto() | BUFFER
    SCALAR = auto()
    TIME = auto()
    ENUM = auto()
    ATOM = STRING | SCALAR | TIME | ENUM

    # ---- Structs ----
    VEC = auto()
    MAP = auto()
    MODEL = auto()
    STRUCT = VEC | MAP | MODEL

    # ---- Other ----
    ITER = auto()
    FUNC = auto()
    OBJECT = ATOM | STRUCT | ITER | FUNC

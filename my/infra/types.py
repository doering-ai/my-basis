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
from enum import Enum

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
Streams = (bytearray, memoryview, IO)
String = str | bytes | Stream
Strings = (str, bytes, *Streams)

Scalar = int | float | complex | bool
Scalars = (int, float, complex, bool)

Time = date | time | datetime | timedelta
Times = (date, time, datetime, timedelta)

Atom = String | Scalar | Time | Enum
Atoms = (*Strings, *Scalars, *Times, Enum)

# ---- Structs ----
Vec = list | tuple | Set | deque
type _Vec[V] = list[V] | tuple[V, ...] | Set[V] | deque[V]
Vecs = (list, tuple, Set, deque)

Map = Mapping[Hashable, Any] | list[tuple[Hashable, Any]] | ItemsView
type _Map[K: Hashable, V] = Mapping[K, V] | list[tuple[K, V]] | ItemsView[K, V]
Maps = (Mapping, ItemsView)  #: NOTE: Does not cover lists of (key, val) pairs.

Dataclass = object
Model = pyd.BaseModel | Dataclass
# No plural -- must use `my.check.is_model`

Iter = Iterable | AsyncIterable
type _Iter[T] = Iterable[T] | AsyncIterable[T]
Iters = (Iterable, AsyncIterable)

Struct = Vec | Map | Iter | Model
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

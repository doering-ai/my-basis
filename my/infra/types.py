############
### HEAD ###
############
### STANDARD
from typing import TypeVar, Any, TypeGuard, overload
from collections.abc import Hashable, Iterable, Mapping, ItemsView
from collections import deque
from datetime import date, datetime, time, timedelta
from enum import Enum
from pathlib import Path
import functools as ft
from importlib.resources import files

### EXTERNAL
import jinja2 as jn
import regex as re
import pydantic as pyd

### INTERNAL
# NOTE: do not import anything from this package (to avoid circular imports)

re.DEFAULT_VERSION = re.VERSION1  # type: ignore


############
### DATA ###
############
class InfraPaths(pyd.BaseModel, arbitrary_types_allowed=True):
    """A model containing important paths within the package."""

    my: Path = files('my')  # type: ignore
    data: Path = files('data')  # type: ignore
    templates: Path = data / 'templates'


#: Immutable object containing important paths within the package.
#: Use `INFRA_PATHS` to access these paths.
INFRA_PATHS: InfraPaths = InfraPaths()

############
### BODY ###
############
# ---------
# CONSTANTS
# ---------
DELIM = ' // '

# -----
# TYPES
# -----
Key = TypeVar('Key', bound=Hashable)
Keys = TypeVar('Keys', bound=tuple)
Value = TypeVar('Value')

type Series = list | tuple | set | deque
type _Series[V] = list[V] | tuple[V, ...] | set[V] | deque[V]
Serieses = (list, tuple, set, deque)  #: A tuple of series types

type Map = Mapping[Hashable, Any] | Iterable[tuple[Hashable, Any]] | ItemsView
type _Map[K: Hashable, V] = Mapping[K, V] | list[tuple[K, V]] | ItemsView[K, V]
Maps = (Mapping, Iterable, ItemsView)  #: A tuple of map types

#: A quantity of time; a duration.
type Time = date | datetime | time | timedelta
Times = (date, datetime, time, timedelta)  #: A tuple of time types

#: A directly-serializable value.
type Atomic = str | int | float | bool | bytes
Atomics = (str, int, float, bool, bytes)  #: A tuple of atomic types

#: A single, figuratively 'first-class' value.
type Scalar = str | int | float | bool | bytes | Enum | Time
Scalars = (str, int, float, bool, bytes, Enum, *Times)  #: A tuple of scalar types
type Block = Scalar  #: an alias for `Scalar` following YAML jargon
#: A collection of values.
type Vector = Series | Map
Vectors = (*Serieses, *Maps)  #: A tuple of vector types
type Collection = Vector  #: an alias for `Vector` following YAML jargon

"""In other words, the type hierarchy is...
- _Scalar_
    - _Atomic_
    - _Time_
    - _Enum_
- _Vector_

"""

@overload
def is_atomic[T](tvar: type[T]) -> TypeGuard[type[Atomic]]: ...
@overload
def is_atomic[T](tvar: T) -> TypeGuard[Atomic]: ...


def is_atomic[T](tvar: T | type[T]) -> TypeGuard[Atomic | type]:
    """Determine if a variable is an atomic type or instance."""
    return issubclass(tvar, Atomics) if isinstance(tvar, type) else isinstance(tvar, Atomics)


@overload
def is_scalar[T](tvar: type[T]) -> TypeGuard[type[Scalar]]: ...
@overload
def is_scalar[T](tvar: T) -> TypeGuard[Scalar]: ...


def is_scalar[T](tvar: T | type[T]) -> TypeGuard[Scalar | type]:
    """Determine if a variable is a scalar type or instance."""
    return issubclass(tvar, Scalars) if isinstance(tvar, type) else isinstance(tvar, Scalars)


@overload
def is_vector[T](tvar: type[T]) -> TypeGuard[type[Vector]]: ...
@overload
def is_vector[T](tvar: T) -> TypeGuard[Vector]: ...


def is_vector[T](tvar: T | type[T]) -> TypeGuard[Vector | type]:
    """Determine if a variable is a vector type or instance."""
    return issubclass(tvar, Vectors) if isinstance(tvar, type) else isinstance(tvar, Vectors)


@overload
def is_map[T](tvar: type[T]) -> TypeGuard[type[Map]]: ...


@overload
def is_map[T](tvar: T) -> TypeGuard[Map]: ...


def is_map[T](tvar: T | type[T]) -> TypeGuard[Map | type]:
    """Determine if a variable is a map type or instance."""
    return issubclass(tvar, Maps) if isinstance(tvar, type) else isinstance(tvar, Maps)


@overload
def is_series[T](tvar: type[T]) -> TypeGuard[type[Series]]: ...
@overload
def is_series[T](tvar: T) -> TypeGuard[Series]: ...


def is_series[T](tvar: T | type[T]) -> TypeGuard[Series | type]:
    """Determine if a variable is a series type or instance."""
    return issubclass(tvar, Serieses) if isinstance(tvar, type) else isinstance(tvar, Serieses)


@overload
def is_time[T](tvar: type[T]) -> TypeGuard[type[Time]]: ...


@overload
def is_time[T](tvar: T) -> TypeGuard[Time]: ...


def is_time[T](tvar: T | type[T]) -> TypeGuard[Time | type]:
    """Determine if a variable is a time type or instance."""
    return issubclass(tvar, Times) if isinstance(tvar, type) else isinstance(tvar, Times)


@overload
def is_enum[T](tvar: type[T]) -> TypeGuard[type[Enum]]: ...


@overload
def is_enum[T](tvar: T) -> TypeGuard[Enum]: ...


def is_enum[T](tvar: T | type[T]) -> TypeGuard[Enum | type]:
    """Determine if a variable is a Enum type or instance."""
    return issubclass(tvar, Enum) if isinstance(tvar, type) else isinstance(tvar, Enum)



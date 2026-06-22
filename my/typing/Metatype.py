############
### HEAD ###
############
# ruff: noqa F401
### STANDARD
from __future__ import annotations

from types import (
    AsyncGenerator,
    BuiltinFunctionType,
    CapsuleType,
    EllipsisType,
    FunctionType,
    GenericAlias,
    NoneType,
    NotImplementedType,
    ParamSpec,
    Self,
    TypeVar,
    TypeVarTuple,
    UnionType,
)
from typing import (
    Annotated,
    Any,
    ClassVar,
    Concatenate,
    Final,
    IO,
    Literal,
    LiteralString,
    NamedTuple,
    Never,
    NewType,
    NoReturn,
    NotRequired,
    ParamSpecArgs,
    ParamSpecKwargs,
    Protocol,
    ReadOnly,
    Required,
    Self,
    Type,
    TypeAliasType,
    TypeGuard,
    TypeIs,
    TypedDict,
    Union,
    Unpack,
    Optional,
    TypeAlias,
)
from collections import deque
from collections.abc import (
    AsyncIterable,
    AsyncIterator,
    Callable,
    Generator,
    ItemsView,
    Iterable,
    Iterator,
    Mapping,
    Set,
)
from datetime import date, datetime, time, timedelta
from dataclasses import dataclass
import itertools as it
import functools as ft
import more_itertools as mi

### MODULAR
from pydantic import BaseModel

### LOCAL
from ..infra.types import (
    Object,
    Stream,
    String,
    Scalar,
    Time,
    Atom,
    Vec,
    Iter,
    Map,
    Model,
    Struct,
    Func,
    Dataclass,
)
from ..utils import ut

from enum import Flag, Enum, auto
from ._TypingBase import _TypingBase

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .Typist import Typist


############
### DATA ###
############
def _ty() -> Typist | None:
    return getattr(_TypingBase, 'TY', None)


_ATOMS: tuple[Metatype, ...] = ()
_OBJECTS: tuple[Metatype, ...] = ()
_FORMS: tuple[Metatype, ...] = ()


############
### BODY ###
############
class Metatype(Enum):
    __match_args__ = ('value',)

    # ---- Atoms ----
    STREAM = (bytearray, memoryview, IO)
    STRING = (str, bytes, *STREAM)
    SCALAR = (int, float, complex, bool)
    TIMES = (date, time, datetime, timedelta)
    ENUM = (Enum,)
    ATOM = (*STRING, *SCALAR, *TIMES, *ENUM)

    # ---- Structures ----
    VEC = (list, tuple, Set, deque)
    MAP = (Mapping, ItemsView)
    MODEL = (BaseModel, dataclass)
    STRUCT = (*VEC, *MAP, *MODEL)
    ITER = (Iterable,)
    FUNC = (FunctionType, Callable, BuiltinFunctionType)
    OBJECT = (*ATOM, *STRUCT, *ITER, *FUNC)

    # ---- Special Forms ----
    #: Simple wrapper types.
    MONO = (Annotated, ClassVar, Final, NotRequired, Required, Unpack)
    #: Wrappers of more than one type at once.
    POLY = (Union, Optional, UnionType)
    #: Types that resolve to bool at runtime.
    COND = (TypeGuard, TypeIs)
    #: Fundamental stdlib types from the `types` module.
    TYPE = (Ellipsis, EllipsisType, TypeAlias, TypeAliasType, NoneType)
    #: Iterable types (i.e. vectors, maps, and models).
    ITER = (
        AsyncGenerator,
        AsyncIterable,
        AsyncIterator,
        Generator,
        Iterator,
        TypedDict,
        NamedTuple,
    )
    #: Forms that always match.
    ALWAYS = (Any, 'Unknown')
    #: Forms that are treated as unmatchable.
    NEVER = (
        '',
        CapsuleType,
        Concatenate,
        LiteralString,
        Never,
        NewType,
        NoReturn,
        NotImplementedType,
        GenericAlias,
        ParamSpec,
        ParamSpecArgs,
        ParamSpecKwargs,
        Protocol,
        ReadOnly,
        Self,
        Type,
        TypeVar,
        TypeVarTuple,
    )

    FORM = (*ALWAYS, *NEVER, *ITER, *MONO, *POLY, *COND, *TYPE)

    @classmethod
    def __new_(cls, value: type | object | None = None) -> Metatype:
        """Return the filter that matches this name."""
        if cls._is_null(value):
            return cls.NEVER
        elif isinstance(value, Metatype):
            return value
        return next((item for item in cls if value in item), cls.NEVER)

    @property
    def val(self) -> tuple[type | object, ...]:
        """The types that this metatype matches."""
        return self.value

    @ft.lru_cache(2**10)
    @staticmethod
    def _nameset(arg: Metatype) -> set[str]:
        """The set of names associated with this metatype."""
        return set(map(Metatype._name, arg.val))

    @property
    def nameset(self) -> set[str]:
        """The set of names associated with this metatype."""
        return self._nameset(self)

    @ft.lru_cache(2**10)
    @staticmethod
    def _match(child: Metatype, parent: Metatype) -> bool:
        return any(name in child.nameset for name in parent.nameset)

    def __contains__(self, arg: type | object | None) -> bool:
        """Whether the proposed child is a compatible type, or an instance OF a compatible type."""
        match arg, self:
            # Validate
            case (None, _) | (_, self.NEVER):
                return False
            case Metatype() as child, parent:
                return Metatype._match(child, parent)
            case type() as child, parent:
                return

        return any(self.compare(arg, item) for item in self.value)

    def __bool__(self) -> bool:
        """Whether this metatype is parseable (i.e. not `NEVER`)."""
        return self is not self.NEVER

    @classmethod
    def parseable(cls, value: object | None = None) -> TypeIs[Object]:
        """Whether a given type is parseable (i.e. not `NEVER`)."""
        return cls(value) in cls.OBJECT

    @classmethod
    def values(cls) -> list[tuple[Metatype, tuple[type | object, ...]]]:
        """Return a mapping of each member to its value."""
        return [(member, member.val) for member in cls]

    @staticmethod
    def _name(val: Any) -> str:
        if val is None:
            return 'None'
        elif isinstance(val, String):
            return Metatype._ty().cast(val, str)
        elif ut.get_first(val, '_name', '__name__'):
            return str(val.__name__)
        elif hasattr(val, '__class__'):
            return str(val.__class__.__name__)
        return ''

    @classmethod
    def _is_null(cls, t: type | object | None) -> TypeIs[None | NoneType]:
        return t in (cls.NEVER, None, NoneType)

    @classmethod
    def _typy(cls, t: type | object | None) -> TypeIs[type]:
        return isinstance(t, type)

    @classmethod
    def _compare(cls, t0: object, t1: object) -> bool:
        if t0 is t1:
            return True
        elif any(falsy := (cls._is_null(t0), cls._is_null(t1))):
            return all(falsy)
        elif isinstance(t0, type) and isinstance(t1, type):
            return issubclass(t0, t1) or issubclass(t1, t0)
        elif isinstance(t0, type):
            return isinstance(t1, t0)
        elif isinstance(t1, type):
            return isinstance(t0, t1)
        return False

    @classmethod
    def compare(cls, *args: type | object | None) -> bool:
        args = tuple(mi.padded(args, None, 2, next_multiple=True))
        return any(it.starmap(cls._compare, it.pairwise(args)))

    @classmethod
    def is_form(
        cls, t0: Metatype
    ) -> TypeIs[
        Literal[
            Metatype.FORM,
            Metatype.ALWAYS,
            Metatype.NEVER,
            Metatype.ITER,
            Metatype.MONO,
            Metatype.POLY,
            Metatype.COND,
            Metatype.TYPE,
        ]
    ]:
        """Whether a type is a special form (i.e. not a normal class or instance)."""
        return cls(t0) in cls.FORM

    @classmethod
    def is_object[*Tup](
        cls, t0: Metatype
    ) -> TypeIs[
        Literal[
            Metatype.STREAM,
            Metatype.STRING,
            Metatype.SCALAR,
            Metatype.TIMES,
            Metatype.ENUM,
            Metatype.ATOM,
            Metatype.VEC,
            Metatype.MAP,
            Metatype.MODEL,
            Metatype.STRUCT,
            Metatype.ITER,
            Metatype.FUNC,
            Metatype.OBJECT,
        ]
    ]:
        return cls(t0) in cls.OBJECT


_M = Metatype

_ATOMS: tuple[Metatype, ...] = (_M.STRING, _M.SCALAR, _M.TIMES, _M.ENUM)
_OBJECTS: tuple[Metatype, ...] = (_M.ATOM, _M.STRUCT, _M.ITER, _M.FUNC)
_FORMS: tuple[Metatype, ...] = (_M.ALWAYS, _M.NEVER, _M.MONO, _M.POLY, _M.COND, _M.TYPE)

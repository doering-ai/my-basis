############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import (
    is_typeddict,
    ClassVar,
    Any,
    overload,
    IO,
    TypeVar,
    TypeVarTuple,
    ParamSpec,
    Literal,
    TYPE_CHECKING,
)
from collections.abc import (
    Callable,
    Collection,
    Iterable,
    Iterator,
    AsyncIterator,
    AsyncIterable,
    AsyncGenerator,
    ItemsView,
    Hashable,
)
from collections import Counter, defaultdict, deque
from dataclasses import is_dataclass, Field
from datetime import date, datetime, time, timedelta, UTC
from enum import Enum, Flag, auto
from io import BytesIO
from types import FunctionType
import functools as ft
import asyncio as aio
import contextlib as ctx
import itertools as it
import logging

### EXTERNAL
import pydantic as pyd
from pydantic.fields import FieldInfo
import more_itertools as mi
import regex as re
import dateutil.parser


### INTERNAL
from ..infra.types import (
    TYPESET,
    _Iter,
    _Vec,
    _Map,
    Stream,
    String,
    Scalar,
    Scalars,
    Time,
    Atom,
    Vec,
    Vecs,
    Iter,
    Map,
    Maps,
    Model,
    Struct,
    Func,
    Object,
)
from ..utils import ut
from .MyType import MyType
from ._common import ABSTRACT_GENERICS
from ._TypingBase import _TypingBase

from .match import tym
from .check import tyc

if TYPE_CHECKING:
    from my import Typist  # noqa


class Empty(Enum):
    """Sentinel value for empty arguments."""

    EMPTY = auto()


empty = Empty.EMPTY

# Empty = type[inspect.Parameter.empty]
# empty = inspect.Parameter.empty

############
### DATA ###
############
logger = logging.getLogger()
_TY = TYPESET

type TransformFn[T0 = Any, T1 = Any] = Callable[[Transform[T0, T1]], object | None]
type TransformEntry[T0 = Any, T1 = Any] = tuple[MyType[T0], MyType[T1], TransformFn[T0, T1]]
_TRANSFORMS: list[TransformEntry] = []

type CaseKey = type | Callable[[object], bool]  #:
type CaseVal = Callable[[object], Any]
type Case = tuple[CaseKey, CaseVal]


type AnyType[T] = type[T] | MyType[T]
type TypeParam = TypeVar | TypeVarTuple | ParamSpec
TypeParams = (TypeVar, TypeVarTuple, ParamSpec)


_TRQUE: deque = deque()


############
### BODY ###
############
class TypeCast(_TypingBase):
    """An ephemeral state machine that the cast defined by its inputs."""

    RGXS: ClassVar[dict[str, re.Pattern]] = ut.regex_dict(
        ### Atomic Types
        int=r'-?\d+',
        float=r'-?\d+(?:\.\d+)?',
        complex=r'-?\d+(?:\.\d+)?[jJ](?:\s*[+-]\s*\d+(?:\.\d+)?[jJ])?',
        bool=r'(?i:t(?:rue)?|y(?:es)?|no?|f(?:alse)?|enabled?|disabled?|on|off|[01])',
        bool_true=r'(?i:t(?:rue)?|y(?:es)?|enabled?|on|1)',
        datetime=r'\d\d(?:\d\d)?[-./]\d\d[-./]\d\d(?:\D\d\d:\d\d:\d\d(?:\.\d+)?)?',
        enum=r'<(?P<class>[_[:upper:]]\w*)\.(?:\|?(?P<member>[_A-Z\d]+))+: (?P<value>.+)>',
        csv=r'^(?P<w>\b\w+\b\s*)(?:(?P<d>[^\w\s]+)\s*(?P>w)(?:\g<d>(?P>w))*)?$',
        brackets=r'(?:^\w+: )?(\[(?:[^\[\\]++(?:\\.|(?1))?)*+\])',
        implicit=re.compile(
            ut.multi_rgx(
                r'^(\d+)-\1\d*',  # super->sub transformations are assumed
                r'11[12]-11[12]',  # str|byte -> str|byte is handled by internal machinery
                r'(12)\d*-\1\d*',  # Scalar -> Scalar
                r'(2[12])\d*-\1\d*',  # Vec and Map types handle intra-family conversions
            )
        ),
    )

    _SETUP: ClassVar[bool] = False

    @staticmethod
    def register[F: FunctionType](fn: F) -> F:
        """Decorator to register a function as a Cast transform based on its type parameters."""
        _TRQUE.append(fn)
        return fn

    @classmethod
    def setup(cls) -> None:
        """Register all transforms defined in this file."""
        if not cls._SETUP:
            while _TRQUE:
                cls._register_impl(_TRQUE.popleft())
            cls._SETUP = True

    @classmethod
    def _register_impl(cls, fn: TransformFn) -> None:
        """Decorator to register a function as a Cast transform based on its type parameters."""
        name = getattr(fn, '__name__', 'fn')
        ty_params = cls._get_type_params(fn)
        if len(ty_params) == 0:
            raise ValueError(
                f'Function {name} must have type parameters to register as a Cast transform.'
            )
        elif len(ty_params) == 2:
            _raw = [MyType.new(t) for _, t in ty_params]
            k0, k1 = _raw[0], _raw[1]
        else:
            _dtps = dict(ty_params)
            k0, k1 = _dtps.get('S', MyType()), _dtps.get('T', MyType())

        # Insert this just before any transform that is more general than it; drop duplicates
        cache = _TRANSFORMS
        pos = len(cache)
        for i, (_k0, _k1, _tr) in enumerate(cache):
            if _k0 == k0 and _k1 == k1:
                logger.warning(
                    f'({k0}, {k1}, {_tr.__name__}) already registered; cannot register {name}'
                )
                return
            elif _k0 in k0 or _k1 in k1:
                pos = i
                break
        cache.insert(pos, (k0, k1, fn))

    @staticmethod
    def _get_type_params[F: FunctionType](fn: F) -> list[tuple[str, MyType]]:
        """Extract type parameters from a function's `__type_params__` attribute, if present."""
        raw: list[TypeParam] = list(getattr(fn, '__type_params__', []))
        ret: list[tuple[str, MyType]] = []
        for param in raw:
            name = param.__name__
            if isinstance(param, TypeVar):
                ret.append((param.__name__, MyType.new(param.__bound__)))
            elif isinstance(param, TypeVarTuple):
                ret.extend((f'{name}_{i}', MyType.new(e)) for i, e in enumerate(param))
        return ret

    # --------------
    # `*2` Interface
    # --------------
    @overload
    @staticmethod
    def cast[A, B](data: A, target: type[B] | MyType[B], default: B) -> B: ...
    @overload
    @staticmethod
    def cast[A, B, C](data: A, target: type[B] | MyType[B], default: C) -> B | C: ...
    @overload
    @staticmethod
    def cast[A, B](data: A, target: type[B] | MyType[B]) -> B | None: ...
    @overload
    @staticmethod
    def cast[A, B](data: A, *, source: AnyType[A], target: type[B] | MyType[B]) -> B | None: ...
    @overload
    @staticmethod
    def cast[A, B](
        data: A,
        target: type[B] | MyType[B],
        *,
        source: AnyType[A] | None = None,
        flex: Literal[True],
    ) -> B | A: ...
    @staticmethod
    def cast[A, B](
        data: A,
        target: type[B] | MyType[B],
        default: B | None | Empty = empty,
        source: AnyType[A] | None = None,
        flex: bool = False,
    ) -> B | A | None:
        """Internal casting implementation that routes to specialized conversion methods.

        Args:
            data: The source data to cast.
            source: The MyType of the source data.
            default: The default value to return if casting fails.
            target: The target MyType to cast to.
            flex: Whether to use "flexcasting", which falls back to any remotely-similar input data
                rather than returning None.
        Returns:
            Cast data if successful, None otherwise.
        """
        res = Transform(data, target, source)()
        if res is not None:
            return res
        elif not isinstance(default, Empty):
            return default
        elif flex:
            return data

    @classmethod
    def multicast[B](cls, data: Iterable, target: AnyType[B]) -> list[B | None]:
        """Cast each element of an iterable to `target`, preserving None elements.

        Args:
            data: The iterable whose elements to cast.
            target: The type each (non-None) element is cast to.
        Returns:
            A list of cast elements, with None elements kept as-is.
        """
        return [None if v is None else cls.cast(v, target) for v in data]

    @classmethod
    def flexcast[A, B](cls, data: A, target: type[B] | MyType[B]) -> B | A:
        """Cast `data` to `target`, falling back to the original data when the cast fails.

        Args:
            data: The source data to cast.
            target: The type to cast to.
        Returns:
            The cast value on success, otherwise the original `data` unchanged.
        """
        return cls.cast(data, target, flex=True)

    @overload
    @classmethod
    def normalize(cls, data: String) -> str: ...
    @overload
    @classmethod
    def normalize[V](cls, data: _Vec[V] | _Iter[V]) -> list[V]: ...
    @overload
    @classmethod
    def normalize[K: Hashable, V](cls, data: _Map[K, V]) -> dict[K, V]: ...
    @overload
    @classmethod
    def normalize[V](cls, data: V) -> V: ...
    @classmethod
    def normalize(cls, data: object) -> object:
        """Normalize the input data into a more workable form for casting."""
        return ut.normalize(data)

    @overload
    @classmethod
    def read_scalars[S: Scalar](cls, data: String, tvar: type[S] | MyType[S]) -> list[S]: ...
    @overload
    @classmethod
    def read_scalars(cls, data: String) -> list[Scalar]: ...
    @classmethod
    def read_scalars[S: Scalar = Scalar](
        cls,
        data: String,
        tvar: type[S] | MyType[S] = Scalar,  # ty:ignore[invalid-parameter-default]
    ) -> list[S]:
        """Attempt to read scalar types from data using regex patterns.

        Args:
            data: The source data to read from.
            tvar: The scalar type to seek out.
        Returns:
            Scalar value if successful, None otherwise.
        """
        if not data:
            return []
        target: MyType[S] = MyType.new(tvar)
        text = tyt.normalize(data)
        targets: tuple[type[Scalar], ...] = tuple(filter(target.match, Scalars))

        counts = {
            _name: _val
            for t in targets
            if ((_name := t.__name__) and (_val := cls.RGXS[_name].findall(text)))
        }
        if not counts:
            return []

        def _calc(item: tuple[str, list[str]]) -> int:
            """Sort potential target types by their coverage of the string."""
            _, matches = item
            return int((len(text) - sum(map(len, matches))) / len(text))

        name, matches = min(counts.items(), key=_calc)
        if name == 'bool':
            return [(cls.RGXS['bool_true'].fullmatch(m)) for m in matches]

        return []


tyt = typecast = TypeCast
register = TypeCast.register


class Transform[T0, T1]:
    """An ephemeral class that represents a single attempted coercion.

    Deliberately a **plain class -- not a pydantic model.** A `Transform` is constructed on
    every single `cast()` call and never crosses a serialization boundary, so it wants none of
    pydantic's per-construction validation. It previously *fought* that machinery anyway --
    passing plain `MyType` instances to dodge the deep re-validation that recurses forever
    through the self-referential `POS` sentinel. Construction is now just a few attribute
    writes, which is all this object ever needed.
    """

    RGXS: ClassVar[dict[str, re.Pattern]] = TypeCast.RGXS

    t0: MyType
    t1: MyType
    data: T0

    # -------------------
    # `.` Initial Methods
    # -------------------
    def __init__(self, data: T0, target: AnyType[T1], source: AnyType[T0] | None = None) -> None:
        """Initialize the (highly-ephemeral) casting context."""
        normalized = tyt.normalize(data)
        self.data = normalized
        self.t0 = MyType.new(source) if source else MyType.typeof(normalized)
        # Inform concretization with the *pre-normalize* `data` -- `normalize` collapses a `set`
        # (and other non-list Vecs) down to a plain `list`, which would otherwise make an
        # abstract target like `Collection[int]` concretize to `list` instead of `set`.
        self.t1 = self.concretize(MyType.new(target), data)

    @property
    def ty(self) -> Typist:
        """The shared `Typist` facade for match/check/cast (mirrors `_TypingBase.ty`)."""
        return _TypingBase._ty()

    @property
    def _t0(self) -> type[T0]:
        ret = self.t0.root
        assert isinstance(ret, type), f'Expected root type for t0, got {ret} from {self.t0}'
        return ret

    @property
    def _t1(self) -> type[T1]:
        ret = self.t1.root
        assert isinstance(ret, type), f'Expected root type for t1, got {ret} from {self.t1}'
        return ret

    def _finalize(self, data: object) -> T1 | None:
        t1 = self.t1
        if data is None or t1 is None:
            # A transform that produced nothing is a non-match -- propagate None so the
            # candidate loop tries the next transform, rather than coercing (e.g. str(None)
            # -> the literal 'None') a failure into a bogus success.
            return None
        elif isinstance(data, str) and bytes in t1:
            data = data.encode()
        elif isinstance(data, bytes) and str in t1:
            data = data.decode()

        # Catch Key/Val mismatches
        t0 = self.t0 if self.data == data else MyType.new(data)
        if t0.keys and t1.keys and t0.keys != t1.keys:
            pass

        # Construct the concrete target type from the (already element-coerced) `data`. NOTE: call
        # `t1.main` -- the underlying type (e.g. `str`, `list`) -- NOT the `MyType` itself, which is
        # not callable.
        if t1.main is None:
            return None
        with ctx.suppress(Exception):
            return t1.main(data) if not isinstance(data, t1.main) else data  # type: ignore[bad-return]

    @ft.cached_property
    def map_items(self: Transform) -> list[tuple[Any, Any]] | None:
        """An already-typecast list of key:val pairs, or None for any non-mapping type."""
        if tyc.is_model(self.data):
            return ut.map_items(self.to(dict) or {})
        elif tyc.is_map(self.data):
            return ut.map_items(self.data)

    # -------------------
    # `-` Private Methods
    # -------------------
    @classmethod
    def _cast_members(cls, items: Iterable[tuple[str, Any]], target: type) -> dict[str, Any]:
        """Cast a mapping's members to match a target class's field types.

        Args:
            items: Key-value pairs to cast.
            target: The target class type with type annotations.
        Returns:
            Dictionary with cast values matching target's field types.
        """
        annotations = ut.instance_aliases(target)
        return {key: tyt.cast(val, annotations.get(key, Any)) for key, val in items}

    # ---------------
    # `-1` Transforms
    # ---------------
    @register
    def _stream_to_str[S: Stream, T: str](self: Transform) -> str | None:
        """``113 -> 111`` transform."""
        return b.decode() if (b := self.to(bytes)) else None

    @register
    def _stream_to_bytes[S: Stream, T: bytes](self: Transform) -> bytes | None:
        ret = self.data
        if isinstance(ret, bytearray):
            return bytes(ret)
        elif isinstance(ret, memoryview):
            return ret.tobytes()
        elif isinstance(ret, IO):
            _v = ret.read()
            return _v if isinstance(_v, bytes) else str(_v).encode()
        else:
            return self.data

    @register
    def _stream_to_string[S: Stream, T: String](self: Transform) -> str | None:
        return self.to(str)

    @register
    def _string_to_stream[S: String, T: Stream](self: Transform) -> str | bytes | None:
        if issubclass(self._t1, (bytearray, memoryview, BytesIO)):
            return tyt.cast(self.data, bytes)
        else:
            return tyt.cast(self.data, str)

    @register
    def _string_to_str[S: String, T: str](self: Transform) -> str | None:
        val = self.data
        if isinstance(val, bytes):
            val = val.decode()
        return val

    @register
    def _string_to_bytes[S: String, T: bytes](self: Transform[S, T]) -> bytes | None:
        """``'hi' -> b'hi'`` -- encode a string to bytes. `bytes` is in `String` but not
        `Stream`, so neither `_string_to_stream` nor `_stream_to_bytes` covers this edge."""
        return text.encode() if (text := self.to(str)) is not None else None

    @register
    def _string_to_scalar[S: String, T: Scalar](self: Transform[S, T]) -> Scalar | None:
        if (text := self.to(str)) is None:
            return
        elif issubclass(self._t1, bool):
            if self.RGXS['bool'].fullmatch(text):
                return self.RGXS['bool_true'].fullmatch(text) is not None
        else:
            return self.flex_deserialize(text)

    @register
    def _atom_to_scalar[S: Atom, T: Scalar](self: Transform[S, T]) -> Scalar | None:
        # Strings are handled by the more-specific `_string_to_scalar`; recursing through
        # `by(str)` here (str -> str -> scalar) would loop forever on non-numeric strings.
        if isinstance(self.data, String):
            return None
        return self.by(str)

    @register
    def _string_to_time[S: String, T: Time](self: Transform[S, T]) -> Time | None:
        # I. Normalize & analyze data
        data = self.to(str)
        if data is None:
            return None
        elif (ret := tyt.cast(data, float)) is not None:
            return tyt.cast(ret, source=float, target=self.t1)
        elif self.ty.RGXS['short_iso_date'].match(data):
            data = f'20{data}'

        def _to_timedelta(_t: type[timedelta]) -> timedelta:
            if matches := list(self.ty.RGXS['timedelta'].finditer(data)):
                return _t(
                    **{
                        key: float(val)
                        for m in matches
                        for key, val in m.groupdict().items()
                        if val
                    }
                )
            return _t()

        # II. Deserialize from iso timestamps (`yyyy-mm-dd` and/or `hh:mm:ss`)
        with ctx.suppress(ValueError):
            return self._type_branch(
                self._t1,
                _datetime=lambda _t: _t.fromisoformat(data).replace(tzinfo=UTC),
                _time=lambda _t: _t.fromisoformat(data).replace(tzinfo=UTC),
                _date=lambda _t: _t.fromisoformat(data),
                _timedelta=_to_timedelta,
            )

        # III. Fall back to an external, flexible library
        if d := dateutil.parser.parse(data):
            d = d.replace(tzinfo=UTC)
            return self._type_branch(
                self._t1,
                _datetime=lambda _t: _t.fromtimestamp(d.timestamp(), tz=UTC),
                _date=lambda _t: _t.fromordinal(d.toordinal()),
                _time=lambda _t: _t.fromisoformat(d.time().isoformat()),
                _timedelta=lambda _t: _t(days=d.day, seconds=d.second, microseconds=d.microsecond),
            )

        return None

    @register
    def _string_to_map[S: String, T: Map](self: Transform[S, T]) -> Map | None:
        if not (text := self.to(str)):
            return
        if text:
            with ctx.suppress(Exception):
                return self.proxy(ut.from_yaml(text, dict))

    @register
    def _string_to_vec[S: String, T: Vec](self: Transform[S, T]) -> Vec | None:
        if not (text := self.to(str)):
            return

        if self.ty.splits:
            if match := self.RGXS['brackets'].fullmatch(text.strip()):
                # I. Split json/yaml-like flow sequences
                with ctx.suppress(Exception):
                    return ut.from_yaml(match[0], list[str], cast=False)
            elif '\n' in text:
                lines = text.splitlines()
                if self.t1.vals and String not in self.t1.vals:
                    lines = ut.condense(map(str.strip, lines))

            elif char := next(filter(text.__contains__, [',', '//', ':', '.']), ''):
                # II. Split on common delimiters in order of preference
                #     e.g. one.oneA:two splits on colons, but one.oneA splits on periods
                return list(filter(bool, map(str.strip, text.split(char))))

        if self.ty.wraps:
            return [text]

    @register
    def _scalar_to_string[S: Scalar, T: String](self: Transform) -> str | None:
        """``5 -> '5'`` -- serialize a scalar into its plain string form."""
        return str(self.data)

    @register
    def _scalar_to_scalar[S: Scalar, T: Scalar](self: Transform) -> Scalar | None:
        """``20.0 -> 20`` -- convert between numeric scalar types via the target constructor."""
        with ctx.suppress(TypeError, ValueError):
            return self._t1(self.data)

    @register
    def _scalar_to_time[S: Scalar, T: Time](self: Transform) -> Time | None:
        """``1700000000 -> datetime(...)`` -- treat a scalar as a POSIX timestamp / ordinal."""
        with ctx.suppress(TypeError, ValueError, OverflowError, OSError):
            return self._num_to_time(float(self.data), self._t1)

    @register
    def _time_to_string[S: Time, T: String](self: Transform[S, T]) -> String | None:
        if isinstance(self.data, datetime | time):
            # All times are UTC unless stated otherwise, so the offset is implicit: serialize
            # the bare wall-clock form (`...T10:20:30`, not `...T10:20:30+00:00`).
            return self.data.replace(tzinfo=None).isoformat()
        elif isinstance(self.data, date):
            return self.data.isoformat()
        elif isinstance(self.data, timedelta):
            return str(self.data)

    @register
    def _time_to_scalar[S: Time, T: Scalar](self: Transform[S, T]) -> Time | Scalar | None:
        d = self.data
        if isinstance(d, datetime):
            return d.timestamp()
        elif isinstance(d, date):
            return d.toordinal()
        elif isinstance(d, time):
            return 60 * ((60 * d.hour) + d.minute) + d.second
        elif isinstance(d, timedelta):
            return d.total_seconds()
        return d

    @register
    def _time_to_struct[S: Time, T: Struct](self: Transform[S, T]) -> object | None:
        return None

    @register
    def _datetime_to_time[S: datetime, T: Time](self: Transform[S, T]) -> Time | None:
        if issubclass(self._t1, time):
            return self.data.time().replace(tzinfo=UTC)
        elif issubclass(self._t1, date):
            return self.data.date()
        elif issubclass(self._t1, timedelta):
            return tyt.cast(self.data.timestamp(), source=float, target=self._t1)
        return self.data

    @register
    def _date_to_time[S: date, T: Time](self: Transform[S, T]) -> Time | None:
        ret = self.data
        if issubclass(self._t1, time):
            return time()
        elif issubclass(self._t1, datetime):
            return datetime.combine(self.data, time(0, 0), tzinfo=UTC)
        elif issubclass(self._t1, timedelta):
            return tyt.cast(self.data.toordinal(), source=int, target=self._t1)
        return ret

    @register
    def _time_to_time[S: time, T: Time](self: Transform[S, T]) -> T | None:
        if issubclass(self._t1, datetime):
            pass
        elif issubclass(self._t1, date):
            pass
        elif issubclass(self._t1, time):
            pass

    @register
    def _timedelta_to_time[S: timedelta, T: Time](self: Transform[S, T]) -> T | None:
        return self.by(int)

    @register
    def _enum_to_string[S: Enum, T: String](self: Transform[S, T]) -> object | None:
        if ret := self.ty.try_method(self._t1, 'write', _tvar=str):
            return ret

        name, value = self.data.name, self.data.value
        return value if isinstance(value, str) else name.lower()

    @register
    def _enum_to_scalar[S: Enum, T: Scalar](self: Transform[S, T]) -> T | None:
        value = self.data.value
        if value and isinstance(value, (String, Scalar)):
            return tyt.cast(value, self._t1)

    @register
    def _enum_to_time[S: Enum, T: Time](self: Transform[S, T]) -> T | None:
        value = self.data.value
        if value and isinstance(value, (String, Scalar)):
            return tyt.cast(value, self._t1)

    @register
    def _enum_to_enum[S: Enum, T: Enum](self: Transform[S, T]) -> T | None:
        # I. If the enum has it's own read method, try that on the name and value
        name, value = self.data.name, self.data.value
        for val in (name, value):
            if ret := self.ty.try_method(self._t1, 'read', val, _tvar=self._t1):
                return ret

        if name in self._t1.__members__:
            return self._t1[name]
        elif key := ut.find_key(self._t1.__members__, value):
            return self._t1[key]

        if (ret := self._t1.__members__.get(name, None)) is not None:
            return ret
        elif ret := next(
            (m for m in self._t1 if m.value == value),
            None,
        ):
            return ret

    @register
    def _enum_to_vec[S: Enum, T: Vec](self: Transform[S, T]) -> T | None:
        return None

    @register
    def _enum_to_map[S: Enum, T: Map](self: Transform[S, T]) -> T | None:
        return None

    @register
    def _enum_to_iter[S: Enum, T: Iter](self: Transform[S, T]) -> T | None:
        return None

    @register
    def _enum_to_model[S: Enum, T: Model](self: Transform[S, T]) -> T | None:
        return None

    @register
    def _object_to_enum[S: Object, T: Enum](self: Transform[S, T]) -> T | None:
        target, data = self._t1, self.data
        # 0. Already a member of the target enum
        if isinstance(data, target):
            return data
        # I. A custom `read` constructor takes precedence
        if (ret := self.ty.try_method(target, 'read', data, _tvar=target)) is not None:
            return ret
        # II. By value (the enum's own lookup, e.g. Color(1) or Status('active'))
        with ctx.suppress(ValueError):
            return target(data)
        # III. By name (exact, then case-insensitive)
        if isinstance(data, str):
            if data in target.__members__:
                return target[data]
            if member := next(
                (m for n, m in target.__members__.items() if n.lower() == data.lower()), None
            ):
                return member
        # IV. By coerced value (e.g. the string '1' -> the int value 1)
        for member in target:
            with ctx.suppress(TypeError, ValueError):
                if member.value == data or type(member.value)(data) == member.value:
                    return member
        return None

    @register
    def _string_to_flag[S: String, T: Flag](self: Transform[S, T]) -> T | None:
        if not (text := self.to(str)):
            return
        elif match := self.RGXS['csv'].fullmatch(text.strip()):
            raw_members = match.captures('w')
            members = ut.condense(map(self.proxy, raw_members))
            if len(members) == len(raw_members):
                _head, *_rest = members
                ret = _head
                for member in _rest:
                    ret |= member
                return ret  # type: ignore[bad-return]

    @register
    def _scalar_to_enum[S: Scalar, T: Enum](self: Transform[S, T]) -> T | None:
        return self._t1(self.data)

    @register
    def _string_to_enum[S: String, T: Enum](self: Transform[S, T]) -> str | Enum | None:
        if not (text := self.to(str)):
            return
        text = text.strip()
        members = dict(self._t1.__members__)
        if (
            self.t1.vals
            and (val := tyt.cast(text, self.t1.vals)) is not None
            and (ret := ut.find_key(members, val))
        ):
            # Get by value
            pass
        elif ret := members.get(text.upper()):
            # Get by name
            pass

        return ret

    @register
    def _atom_to_vec[S: Atom, T: Vec](self: Transform[S, T]) -> list | None:
        if self.ty.wraps and self.data and self.t1.vals:
            with ctx.suppress(TypeError):
                return [self.to(self.t1.vals)]

    @register
    def _flag_to_vec[S: Flag, T: Vec](self: Transform[S, T]) -> list | None:
        return [self._t0(member.value) for member in self._t0 if member in self.data]

    @register
    def _flag_to_map[S: Flag, T: Map](self: Transform[S, T]) -> dict | None:
        return {member.name: member.value for member in self._t0 if member in self.data}

    @register
    def _atom_to_map[S: Atom, T: Map](self: Transform[S, T]) -> dict | None:
        return None

    @register
    def _atom_to_struct[S: Atom, T: Struct](self: Transform[S, T]) -> list | dict | Model | None:
        return None

    @register
    def _vec_to_flag[S: Vec, T: Flag](self: Transform[S, T]) -> T | None:
        ret = self._t1(0)
        for member in self.data:
            if (_new := tyt.cast(member, self._t1)) is not None:
                ret |= _new
        return ret

    @register
    def _vec_to_time[S: Vec, T: Time](self: Transform[S, T]) -> Time | list | None:

        if not (d := list(self.data)):
            pass
        elif len(d) == 1 and (_vt := self.t0.vals) and tym.is_atom_type(_vt):
            # I. Unwrap monotomic lists
            return self.proxy(d[0])
        elif len(d) >= 3:
            # II. it's a sequence of 3 or more values, try interpreting the first 3 as time
            # components
            with ctx.suppress(Exception):
                return self._type_branch(
                    self._t1,
                    _datetime=lambda _t: _t(*d, tzinfo=UTC),
                    _date=lambda _t: _t(*d),
                    _time=lambda _t: _t(*d).replace(tzinfo=UTC),
                )
        return d

    @register
    def _vec_to_string[S: Vec, T: String](self: Transform[S, T]) -> str | None:
        """``[] -> '[]'`` -- serialize a sequence into its plain string form."""
        return str(self.data)

    @register
    def _vec_to_atom[S: Vec, T: Atom](self: Transform[S, T]) -> T | None:
        if not self.data:
            return None
        # A multi-element series needs `firsts`; a single-element one needs `atomics`.
        multi = len(self.data) > 1
        if (multi and not self.ty.firsts) or (not multi and not self.ty.atomics):
            return None
        return self.proxy(mi.first(self.data))

    @register
    def _vec_to_vec[S: Vec, T: Vec](self: Transform[S, T]) -> list | None:
        data = self.to(list)
        if data is not None and self.t1.vals and self.t0.vals != self.t1.vals:
            # Element types differ -> coerce each element, don't cast the whole list.
            return self.ty.multicast(data, self.t1.vals)
        return data

    @register
    def _vec_to_map[S: Vec, T: Map](self: Transform[S, T]) -> dict | Counter | None:
        data = self.data
        if (
            self.ty.is_map_type(self.t1)
            and data
            and all(not isinstance(p, String) and tyc.is_vec(p) and len(p) == 2 for p in data)
        ):
            # I. A list of 2-element pairs -> map items. `normalize` listifies tuples, so
            #    `is_map` (which wants tuple pairs) misses these -- detect them structurally.
            #    Re-cast as a dict so the map->map path coerces keys/values to the target types.
            #    Gated on `is_map_type(t1)` -- a `Model` also iterates to pairs (pydantic's
            #    dict-like `__iter__`) but isn't itself map-shaped; without the gate, recasting
            #    a model instance recurses through `_object_to_model` -> `try_method('new', ...)`
            #    -> `normalize` -> pairs -> here, forever.
            return self.proxy(dict(map(tuple, data)))

        elif issubclass(self.t1.main, Counter):
            # II. Cast counters, the only map type that takes an iter of single items: coerce
            #     each item to the key type (e.g. 'a.b.c' -> ('a', 'b', 'c')), then count.
            if (kt := self.t1.keys) and kt.main:
                return Counter(self.ty.multicast(self.data, kt))
            return Counter(self.data)

    @register
    def _vec_to_iter[S: Vec, T: Iter](self: Transform[S, T]) -> Iterator | AsyncIterator | None:
        if isinstance(self.data, AsyncIterable):

            async def _gen() -> AsyncGenerator:
                async for item in self.data:
                    yield item

            return _gen()
        else:
            return iter(self.data)

    @register
    def _vec_to_model[S: Vec, T: Model](self: Transform[S, T]) -> T | None:

        if issubclass(self._t1, pyd.BaseModel):
            return self._object_to_model()
        return None

    @register
    def _map_to_string[S: Map, T: String](self: Transform[S, T]) -> str | None:
        """``{} -> '{}'`` -- serialize a mapping into its plain string form."""
        return str(self.to(dict) if not isinstance(self.data, dict) else self.data)

    @register
    def _map_to_scalar[S: Map, T: Scalar](self: Transform[S, T]) -> Scalar | None:
        """A mapping coerces to a scalar only by its length (e.g. truthiness / count)."""
        with ctx.suppress(TypeError, ValueError):
            return self._t1(len(self.to(dict) or {}))

    @register
    def _map_to_time[S: Map, T: Time](self: Transform[S, T]) -> Time | None:
        """Build a Time object from a mapping of its components (e.g. ``{'year': 2026, ...}``)."""
        if not (items := self.map_items):
            return None
        with ctx.suppress(TypeError, ValueError):
            return self._t1(**dict(items))

    @register
    def _map_to_enum[S: Map, T: Enum](self: Transform[S, T]) -> T | None:
        return None

    @register
    def _map_to_vec[S: Map, T: Vec](self: Transform[S, T]) -> list | T | None:
        v0, v1 = self.t0.vals, self.t1.vals
        if not self.map_items or not v1:
            # I. Without guidance, skip casting altogether
            return self.map_items
        elif tym.is_string_type(v1):
            return [f'{k}: {v}' for k, v in self.map_items]
        elif tym.is_map_type(v1) and self.ty.wraps:
            # II. Wrap objects in lists
            return [self.map_items]
        elif tym.is_map_item_type(v1):
            # III. Cast items as tuples of (key, value) pairs
            return self.proxy(self.map_items)
        elif tym.is_atom_type(v1):
            # IV. Just take values or keys if either matches
            if tym.match(v0, v1):
                return [v for _, v in self.map_items]
            elif tym.match(self.t0.keys, self.t1.vals):
                return [k for k, _ in self.map_items]

        return self.proxy(self.map_items)

    @register
    def _map_to_map[S: Map, T: Map](self: Transform[S, T]) -> Map | None:
        if not (items := ut.map_items(self.data)):
            return None if items is None else dict()

        keys, values = map(list, mi.unzip(items))
        # Coerce against the *full* key/value MyType (not `.rtype`, which flattens a nested
        # container type like `dict[str, int]` down to its first arg) so nested maps recurse.
        if self.t1.keys:
            keys = self.ty.multicast(keys, self.t1.keys)
        if self.t1.vals:
            values = self.ty.multicast(values, self.t1.vals)
        data = dict(zip(keys, values, strict=True))

        # Construct the target mapping, handling a couple of special constructors. Use the
        # concrete origin (`.main`, e.g. `dict`), not `._t1` -- a parametrized target like
        # `dict[str, int]` has a generic-alias `root` that isn't a usable constructor/class.
        cls = self.t1.main
        if issubclass(cls, defaultdict):
            return cls(self.t1.vals.main, data) if self.t1.vals else cls(None, data)
        elif issubclass(cls, ItemsView):
            return data.items()
        return cls(data)

    @register
    def _iter_to_vec[S: Iter, T: Vec](self: Transform[S, T]) -> list | None:
        data: Iterable | AsyncIterable = self.data
        if isinstance(data, AsyncIterable):

            async def _coalesce() -> list:
                _ret = []
                async for item in data:
                    _ret.append(item)  # noqa: PERF401
                return _ret

            ret = aio.run(_coalesce())
        else:
            ret = list(data)

        if self.t1.vals:
            return self.ty.multicast(ret, self.t1.vals)
        return ret

    @register
    def _iter_to_object[S: Iter, T: object](self: Transform[S, T]) -> T | None:
        """Hailmary fallback that materializes a *lazy* iterator to a list first.

        Restricted to genuine iterators: a str/bytes or an already-concrete sequence is
        also `Iterable`, but re-listing it and re-casting to the same broad target would
        recurse forever (and a string would be exploded into characters).
        """
        if isinstance(self.data, Iterator) and not isinstance(self.data, (str, bytes)):
            return self.by(list)
        return None

    @register
    def _object_to_iter[S: Map, T: Iter](self: Transform[S, T]) -> T | None:
        # A Mapping is itself an Iterable, so this would fire for map->map targets and explode
        # the dict into a list of keys (then loop). Leave map targets to the map transforms.
        if tym.is_map_type(self.t1):
            return None
        return self.by(list)

    def _model_fields(
        self: Transform, model: type[Model] | None
    ) -> dict[str, FieldInfo] | dict[str, Field] | dict[str, Any]:
        """Return a map of field names to their annotations, if available."""
        if not model:
            pass
        elif issubclass(model, pyd.BaseModel):
            return model.model_fields
        elif pyd.dataclasses.is_pydantic_dataclass(model):
            return model.__pydantic_fields__
        elif is_dataclass(model):
            return model.__dataclass_fields__
        elif is_typeddict(model):
            return model.__annotations__
        return {}

    @register
    def _model_to_map[S: Model, T: Map](self: Transform[S, T]) -> T | dict | None:
        # Only genuine model sources convert here. A loose target like `MutableSet` matches the
        # `Map` bound, so without this guard the dict produced below would `proxy()` straight back
        # into this transform and recurse forever.
        if not tym.is_model_type(self.t0):
            return None

        ret: dict[str, Any]
        if isinstance(self.data, pyd.BaseModel):
            ret = self.data.model_dump()
        elif result := self.ty.try_method(self.data, 'to_dict', _tvar=dict):
            ret = result
        else:
            ret = {
                f: val
                for f in self._model_fields(self._t1)
                if (val := getattr(self.data, f, empty) is not empty)
            }

        return self.proxy(ret)

    @register
    def _model_to_model[S: Model, T: Model](self: Transform[S, T]) -> T | None:
        f0, f1 = self._model_fields(self._t0), self._model_fields(self._t1)
        if f0 and f1 and (shared := set(f0.keys()) & set(f1.keys())):
            return self.proxy({f: getattr(self.data, f) for f in shared})

    @register
    def _model_to_object[S: Model, T: Object](self: Transform[S, T]) -> T | None:
        fields = self._model_fields(self._t0)
        if 'root' in fields:
            return self.proxy(getattr(self.data, 'root'))
        elif fields:
            return self.proxy({f: getattr(self.data, f) for f in fields})

    @register
    def _object_to_model[S: Any, T: Model](self: Transform[S, T]) -> T | None:
        """Cast data to a class instance using various instantiation strategies.

        Args:
            data: The source data to instantiate from.
            target: The target class type.
        Returns:
            Class instance if successful, None otherwise.
        """
        # I. First, try to use the semi-standard `new()` method if available
        if (ret := self.ty.try_method(self._t1, 'new', self.data, _tvar=self._t1)) is not None:
            return ret
        elif tyc.is_map(self.data):
            kwargs = self._cast_members(ut.map_items(self.data), self._t1)
            return self.ty.invoke(self._t1, **kwargs)
        else:
            return self.ty.invoke(self._t1, self.data)

    @register
    def _func_to_str[S: Func, T: str](self: Transform[S, str]) -> str | None:
        return self.data.__name__ if self.data else None

    @register
    def _func_to_atom[S: Func, T: Atom](self: Transform[S, T]) -> T | None:
        args, rets = tyc.describe_func(self.data)
        if len(rets) == 1 and len(args) == 0 and tyc.is_atom_type(rets[0]):
            return self.proxy(self.data())

    # ----------------------------------
    # `-2` Non-registered helper methods
    # ----------------------------------
    @classmethod
    def _derive_container(cls, old: MyType, new_origin: type[Collection]) -> MyType:
        """Create a new container type based on an existing one with a different origin.

        Args:
            old: The original MyType to derive from.
            new_origin: The new origin type to use.
        Returns:
            New MyType with the new origin but preserving args from old.
        """
        if old.origin and old.args:
            new_args = (arg.root for arg in old.args)
            new_src = new_origin[*new_args]  # type: ignore
        else:
            new_src = new_origin

        return MyType.parse(new_src)

    # -------------------
    # `+` Primary Methods
    # -------------------
    def to_union(self) -> T1 | None:
        """Cast data to a union (split) target.

        Returns the data unchanged if it already satisfies any member of the union (a NOOP,
        e.g. a str passed to `int | str`); otherwise coerces it to a member, trying the
        last-listed first (later members are treated as higher-preference targets). Casting
        to the NoneType member naturally yields None and is skipped over.

        Returns:
            The (possibly coerced) data, or None if no member could be satisfied.
        """
        if self.t1.check(self.data):
            return self.data
        for arg in reversed(self.t1.args):
            if (ret := tyt.cast(self.data, arg)) is not None:
                return ret
        return None

    def to_literal(self) -> T1 | None:
        """Cast data to a literal type or literal tuple.

        Fails silently if the passed data is a sequence that differs in length from the target
        type's expectations.

        Args:
            data: The source data to cast.
            target: The target literal MyType.
        Returns:
            Cast data if it matches the literal, None otherwise.
        """
        data = self.data
        origin: type[T1] | None = self.t1.origin
        if not self.t1.literal_members or origin is None or data is None:
            return

        ret: Any | None = None
        if origin is Literal:
            # I. Cast Literals
            if any(vals.check(data) for vals in self.t1.args):
                ret = data
            else:
                ret = next(
                    (
                        ret
                        for vals in self.t1.args
                        if (ret := tyt.cast(data, vals)) is not None and tyc.check(ret, self.t1)
                    ),
                    None,
                )

        elif isinstance(origin, type) and issubclass(origin, tuple):
            # II. Cast literally-positioned tuples
            data = tyt.cast(data, list)
            if data is None or len(data) != len(self.t1.args):
                return
            cast_values = tuple(it.starmap(tyt.cast, zip(data, self.t1.args, strict=True)))
            ret = origin(cast_values)

        else:
            raise TypeError(f'Unsupported literal origin: {origin}')

        # III. Validate and return
        if ret is not None and tyc.check(ret, self.t1):
            return ret

    @classmethod
    def flex_deserialize(cls, text: str) -> Scalar | None:
        """Parse text as whichever scalar type's pattern it matches, or None if none match."""
        # Numeric parsers own their whitespace: surrounding pad is insignificant when the
        # output is a number (`Scalars` is int/float/complex/bool -- never `str`), so strip
        # before matching. This is the "parsers handle whitespace" half of the no-strip rule.
        text = text.strip()
        for stype in Scalars:
            name = stype.__name__
            if name in cls.RGXS and cls.RGXS[name].fullmatch(text):
                return stype(text)

    @classmethod
    def _cast_branch[T](
        cls,
        data: object,
        *,
        _datetime: Callable[[datetime], T] | None = None,
        _time: Callable[[time], T] | None = None,
        _timedelta: Callable[[timedelta], T] | None = None,
        _date: Callable[[date], T] | None = None,
        _str: Callable[[str], T] | None = None,
        _bytes: Callable[[bytes], T] | None = None,
        _int: Callable[[int], T] | None = None,
        _float: Callable[[float], T] | None = None,
        _bool: Callable[[bool], T] | None = None,
        _enum: Callable[[Enum], T] | None = None,
        _vec: Callable[[Vec], T] | None = None,
        _map: Callable[[Map], T] | None = None,
        **kwargs: Callable[[type], T],
    ) -> T | None:
        pairs = [
            (datetime, _datetime),
            (time, _time),
            (timedelta, _timedelta),
            (date, _date),
            (str, _str),
            (bytes, _bytes),
            (int, _int),
            (float, _float),
            (bool, _bool),
            (Enum, _enum),
            (Vecs, _vec),
            (Maps, _map),
        ]

        for tvar, handler in pairs:
            if handler and isinstance(data, tvar):
                return handler(data)  # type: ignore
        return None

    @classmethod
    def _type_branch[T](
        cls,
        target: type[T],
        *,
        _datetime: Callable[[type[datetime]], datetime] | None = None,
        _time: Callable[[type[time]], time] | None = None,
        _timedelta: Callable[[type[timedelta]], timedelta] | None = None,
        _date: Callable[[type[date]], date] | None = None,
        _str: Callable[[type[str]], str] | None = None,
        _bytes: Callable[[type[bytes]], bytes] | None = None,
        _int: Callable[[type[int]], int] | None = None,
        _float: Callable[[type[float]], float] | None = None,
        _bool: Callable[[type[bool]], bool] | None = None,
        _enum: Callable[[type[Enum]], Enum] | None = None,
        _vec: Callable[[type[Vec]], Vec] | None = None,
        _map: Callable[[type[Map]], Map] | None = None,
        **kwargs: Callable[[type], T],
    ) -> T | None:
        pairs = [
            (datetime, _datetime),
            (time, _time),
            (timedelta, _timedelta),
            (date, _date),
            (str, _str),
            (bytes, _bytes),
            (int, _int),
            (float, _float),
            (bool, _bool),
            (Enum, _enum),
            (Vecs, _vec),
            (Maps, _map),
        ]

        for tvar, handler in pairs:
            if handler and issubclass(target, tvar):
                return handler(target)  # type: ignore
        return None

    def _num_to_time[T: Time](self, data: int | float, target: type[T]) -> T | None:
        """Convert a number to a Time object treating it as a timestamp or ordinal.

        Args:
            data: The numeric value to convert.
            target: The target Time type (datetime, date, time, or timedelta).
        Returns:
            Converted Time object if successful, None otherwise.
        """
        return self._type_branch(
            target,
            _datetime=lambda t: t.fromtimestamp(data, tz=UTC),
            _date=lambda d: d.fromordinal(int(data)),
            _time=lambda t: t.fromisoformat(
                datetime.fromtimestamp(data, tz=UTC).time().isoformat()
            ).replace(tzinfo=UTC),
            _timedelta=lambda t: t(seconds=float(data)),
        )

    @classmethod
    def concretize(cls, target: MyType, data: object) -> MyType:
        """Convert abstract container types to concrete ones based on data.

        Args:
            target: The target MyType.
            data: The source data to inform concretization.
        Returns:
            Tuple of (potentially modified MyType, potentially modified main type).
        """
        main = target.main
        if main is None:
            return target

        new_main = None
        if main in ABSTRACT_GENERICS['maps']:
            new_main = _dt.main if tyc.is_map(data) and (_dt := MyType(type(data))) else dict
        elif main in ABSTRACT_GENERICS['sets']:
            new_main = set
        elif main in ABSTRACT_GENERICS['vecs']:
            new_main = _dt.main if tyc.is_vec(data) and (_dt := MyType(type(data))) else list

        if new_main is not None:
            return cls._derive_container(target, new_main)
        return target

    # ------------------
    # `*` Public Methods
    # ------------------
    @classmethod
    def _try_read_enum[T: Enum](cls, data: object, target: type[T]) -> object | None:
        if read_method := cls._ty().get_method(target, 'read'):
            if (ret := cls._ty().invoke(read_method, data)) is not None:
                return ret

    def to[B](self, t1: AnyType[B]) -> B | None:
        """Shorthand for casting our current data to an interim type."""
        return tyt.cast(self.data, source=self.t0, target=t1)

    def proxy(self, data: Any) -> T1 | None:
        """Shorthand for casting new data to our target type."""
        return tyt.cast(data, self.t1)

    def by(self, *args: AnyType) -> T1 | None:
        """Shorthand casting to the target type through one or more intermediary types.

        Each intermediate is an actual cast *target* in turn (the source of each hop is
        inferred from the running value), so `by(list)` truly materializes a list before
        casting onward -- which also stops hailmary fallbacks from re-selecting themselves.
        """
        cur: Any = self.data
        for t1 in (*args, self._t1):
            cur = tyt.cast(cur, target=t1)
            if cur is None:
                break
        return cur

    def __call__(self, new_data: T0 | None = None) -> T1 | None:
        """Main entrypoint for casting a value to a new type."""
        # I. Normalize data
        if new_data:
            self.data = tyt.normalize(new_data)

        # II. Branch immediately for special cases
        if self.t1.literal_members:
            return self.to_literal()
        elif self.t1.is_split:
            return self.to_union()
        elif not self.t1.main or self.data is None:
            return None
        elif self.t1.check(self.data):
            return self.data

        # Get a list of relevant transformations, sorted from most- to least-specific. Specificity
        # is a *partial* order (subset of bounds), so a plain `.sort()` on `MyType.__lt__` scrambles
        # it -- e.g. letting `object`-bound hailmary transforms beat `_scalar_to_string`. Use an
        # explicit comparator that puts strictly-narrower (subset) bounds first instead.
        def _by_specificity(a: TransformEntry, b: TransformEntry) -> int:
            (a0, a1, _), (b0, b1, _) = a, b
            a_sub = (a0 == b0 or a0 in b0) and (a1 == b1 or a1 in b1)  # a's bounds ⊆ b's bounds
            b_sub = (b0 == a0 or b0 in a0) and (b1 == a1 or b1 in a1)  # b's bounds ⊆ a's bounds
            return int(b_sub) - int(a_sub)  # the narrower (more-specific) entry sorts first

        candidates = [(k0, k1, tr) for k0, k1, tr in _TRANSFORMS if self.t0 in k0 and self.t1 in k1]
        candidates.sort(key=ft.cmp_to_key(_by_specificity))

        # Try each of the candidates in turn, returning the first successful cast (if any). A
        # transform that raises is treated as a non-match -- the next (more general) candidate is
        # tried -- rather than aborting the whole cast.
        for *_, tr in candidates:
            with ctx.suppress(Exception):
                if (ret := self._finalize(tr(self))) is not None:
                    return ret

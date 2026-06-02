############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import (
    NamedTuple,
    ClassVar,
    Any,
    overload,
    IO,
    TypeVar,
    TypeVarTuple,
    ParamSpec,
    Literal,
)
from collections.abc import (
    Callable,
    Iterable,
    Iterator,
    AsyncIterator,
    AsyncIterable,
)
from io import BytesIO
from types import FunctionType, UnionType
from datetime import date, datetime, time, timedelta, UTC
from enum import Enum, Flag
from collections import Counter, defaultdict
import logging
import contextlib as ctx
import asyncio as aio
import itertools as it

### EXTERNAL
import pydantic as pyd
import more_itertools as mi
import regex as re
import dateutil.parser

### INTERNAL
from ..infra.types import (
    TYPESET,
    Stream,
    _Vec,
    _Map,
    Streams,
    String,
    Strings,
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

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from my import Typist  # noqa

Dtim = datetime
Delt = timedelta
Scal = Scalar

type AnyType[T] = type[T] | MyType[T]
type TypeParam = TypeVar | TypeVarTuple | ParamSpec
TypeParams = (TypeVar, TypeVarTuple, ParamSpec)

############
### DATA ###
############
logger = logging.getLogger()
_TY = TYPESET

type Transform[T0 = Any, T1 = Any] = Callable[[Cast[T0, T1]], T1 | None]
type TransformEntry[T0 = Any, T1 = Any] = tuple[MyType[T0], MyType[T1], Transform[T0, T1]]
_TRANSFORMS: list[TransformEntry] = []


type _Transform[T0 = Any, T1 = Any] = (
    Callable[[Cast[T0, T1]], T1 | None]
    # Callable[[type[Cast], T0, type[T1]], T1 | None]
    # | Callable[[type[Cast], T0, type[T1], Typist], T1 | None]
    # | Callable[[type[Cast], T0, type[T0], type[T1]], T1 | None]
)


def get_type_params[F: FunctionType](fn: F) -> list[tuple[str, MyType]]:
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


############
### BODY ###
############
class Cast[T0, T1](pyd.BaseModel):
    """An ephemeral state machine that the cast defined by its inputs."""

    TRANSFORMS: ClassVar[list[TransformEntry]] = _TRANSFORMS
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
    )
    ctx: ClassVar[Typist]

    t0: MyType[T0]
    t1: MyType[T1]
    data: T0
    _orig_data: Any | None = None

    @pyd.model_validator(mode='before')
    def _val_cast(self) -> Cast:
        if self._orig_data is None:
            self._orig_data = self.data
            self.data = self._normalize(self.data)
            self.t0 = MyType.metaparse(self.data)
        return self

    @staticmethod
    def _register[F: FunctionType](fn: F) -> F:
        """Decorator to register a function as a Cast transform based on its type parameters."""
        name = getattr(fn, '__name__', 'fn')
        tps = get_type_params(fn)
        if len(tps) == 0:
            raise ValueError(
                f'Function {name} must have type parameters to register as a Cast transform.'
            )
        elif len(tps) == 2:
            _raw = list(map(MyType, tps))
            k0, k1 = _raw[0], _raw[1]
        else:
            _dtps = dict(tps)
            k0, k1 = _dtps.get('S', MyType()), _dtps.get('T', MyType())

        # Insert this just before any transform that is more general than it
        pos = len(cache := Cast.TRANSFORMS)
        for i, (_k0, _k1, _tr) in enumerate(cache):
            if _k0 == k0 and _k1 == k1:
                logger.warning(
                    f'({k0}, {k1}, {_tr.__name__}) already registered; cannot register {name}'
                )
                break
            elif _k0.within(k0) or _k1.within(k1):
                pos = i
                break
        cache.insert(pos, (k0, k1, fn))

        return fn

    # -------------------
    # `.` Initial Methods
    # -------------------
    def __init__(self, data: T0, target: AnyType[T1], source: AnyType[T0] | None = None, **kwargs):
        """Initialize the (highly-ephemeral) casting context."""
        if not hasattr(Cast, 'ctx'):
            from .Typist import Typist

            Cast.ctx = Typist()

        self.t0 = MyType.new(source) if source else MyType.new(data)
        self.t1 = MyType.new(target)
        super().__init__(data=data, **kwargs)

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

    @overload
    @staticmethod
    def cast[Tt0, Tt1](data: Tt0, target: type[Tt1] | MyType[Tt1]) -> Tt1 | None: ...
    @overload
    @staticmethod
    def cast[Tt0, Tt1](
        data: Tt0, *, source: AnyType[Tt0], target: type[Tt1] | MyType[Tt1]
    ) -> Tt1 | None: ...
    @staticmethod
    def cast[Tt0, Tt1](
        data: Tt0, target: type[Tt1] | MyType[Tt1], *, source: AnyType[Tt0] | None = None
    ) -> Tt1 | None:
        """Internal casting implementation that routes to specialized conversion methods.

        Args:
            data: The source data to cast.
            source: The MyType of the source data.
            target: The target MyType to cast to.
        Returns:
            Cast data if successful, None otherwise.
        """
        return Cast(data, target, source)()

    def __call__(self, new_data: T0 | None = None) -> T1 | None:
        """Main entrypoint for casting a value to a new type."""
        # I. Normalize data
        if new_data:
            self.data = self._normalize(new_data)

        # II. Branch immediately for special cases
        if self.t1.literal_members:
            return self.to_literal()
        elif self.t1.is_split or not self.t1.main or self.data is None:
            return None
        elif self.t1.check(self.data):
            return self.data

        # Get a list of relevant transformations, sorted from most- to least-specific.
        candidates = [
            (k0, k1, tr) for k0, k1, tr in _TRANSFORMS if k0.within(self.t0) and k1.within(self.t1)
        ]
        candidates.sort()

        # Try each of the candidates in turn, returning the first successful cast (if any)
        for *_, tr in candidates:
            if (ret := self._finalize(tr(self))) is not None:
                return ret

    def _finalize(self, data: object) -> T1 | None:
        t1 = self.t1
        if t1 is None:
            return None
        elif isinstance(data, str) and bytes in t1:
            data = data.encode()
        elif isinstance(data, bytes) and str in t1:
            data = data.decode()

        # Catch Key/Val mismatches
        t0 = self.t0 if self.data == data else MyType.new(data)
        if t0.keys and t1.keys and t0.keys != t1.keys:
            pass

        with ctx.suppress(Exception):
            return t1(data)  # type: ignore[bad-return]

    @overload
    @classmethod
    def _normalize[C](cls, data: Iterator[C] | AsyncIterator[C]) -> list[C]: ...
    @overload
    @classmethod
    def _normalize(cls, data: String) -> str: ...
    @overload
    @classmethod
    def _normalize[C](cls, data: C) -> C: ...
    @classmethod
    def _normalize(cls, data: object) -> object:
        if isinstance(data, (type, UnionType, str)):
            return data
        elif isinstance(data, AsyncIterator):

            async def async_gen() -> list:
                ret = []
                async for item in data:
                    ret.append(item)  # noqa: PERF401
                return ret

            return aio.run(async_gen())
        elif isinstance(data, Iterator):
            return list(mi.spy(data)[1])
        elif isinstance(data, bytes):
            return data.decode()
        elif isinstance(data, Streams):
            return Cast.cast(data, str)
        elif isinstance(data, Iterable) and not isinstance(data, (*Vecs, *Maps)):
            return list(data)
        elif isinstance(data, datetime) and data.tzinfo != UTC:
            return data.astimezone(UTC)
        elif isinstance(data, time) and data.tzinfo != UTC:
            return data.replace(tzinfo=UTC)
        return data

    # -------------------
    # `-` Private Methods
    # -------------------
    @classmethod
    def get_transform[Tt0, Tt1](
        cls, _t0: AnyType[Tt0], _t1: AnyType[Tt1]
    ) -> Transform[Tt0, Tt1] | None:
        """Lookup a registered transform function for the given source and target MyTypes."""
        t0, t1 = MyType.new(_t0), MyType.new(_t1)
        for k0, k1, transform in _TRANSFORMS:
            if k0.within(t0) and k1.within(t1):
                return transform

    def _cast_members(self, items: Iterable[tuple[str, Any]], target: type) -> dict[str, Any]:
        """Cast a mapping's members to match a target class's field types.

        Args:
            items: Key-value pairs to cast.
            target: The target class type with type annotations.
        Returns:
            Dictionary with cast values matching target's field types.
        """
        annotations = ut.instance_aliases(target)
        return {key: self.ctx.flexcast(val, annotations.get(key, None)) for key, val in items}

    # -------------------
    # `+` Primary Methods
    # -------------------
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
        origin = self.t1.origin
        ret: T1 | None = None
        if not self.t1.literal_members or origin is None or data is None:
            return ret

        if origin is Literal:
            # I. Cast Literals
            if any(vals.check(data) for vals in self.t1.args):
                ret = data  # type: ignore
            else:
                ret = next(
                    (
                        ret
                        for vals in self.t1.args
                        if (ret := Cast.cast(data, vals)) and self.t1.literal_check(ret)
                    ),
                    None,
                )
        elif isinstance(origin, type) and issubclass(origin, tuple):
            # II. Cast literally-positioned tuples
            if not isinstance(data, Vecs):
                data = self.cast(data, tuple)

            if data is not None and len(data) == len(self.t1.args):
                cast_values = list(it.starmap(Cast.cast, zip(data, self.t1.args, strict=True)))
                # Use the parent type's actual class constructor directly via this handle
                ret = origin(cast_values)  # type: ignore

        return ret if ret is not None and self.t1.literal_check(ret) else None

    def _str_to_times[T: Time](self, data: str, target: type[T]) -> T | None:
        """Convert a string to a Time object using various parsing strategies.

        Args:
            data: The string to parse.
            target: The target Time type (datetime, date, time, or timedelta).
        Returns:
            Parsed Time object if successful, None otherwise.
        """

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
            ),
            _timedelta=lambda t: t(seconds=float(data)),
        )

    # ------------------
    # `*` Public Methods
    # ------------------

    @classmethod
    def _try_read_enum[T: Enum](cls, data: object, target: type[T], ctx: Typist) -> object | None:
        if read_method := ctx.get_method(target, 'read'):
            if (ret := ctx.invoke(read_method, data)) is not None:
                return ret

    def to[Tt1](self, t1: AnyType[Tt1]) -> Tt1 | None:
        """Shorthand for casting our current data to an interim type."""
        return self.cast(self.data, source=self.t0, target=t1)

    def proxy(self, data: Any) -> T1 | None:
        """Shorthand for casting new data to our target type."""
        return self.cast(data, self.t1)

    # --------------------------------------------------------------------------------------------
    # --------------------------------------------------------------------------------------------
    # --------
    # NEW LIST
    # --------
    # --------------------------------------------------------------------------------------------
    # --------------------------------------------------------------------------------------------
    @_register
    def _stream_to_str[S: Stream, T: str](self: Cast) -> object | None:
        """``113 -> 111`` transform."""
        return self.to(bytes)

    @_register
    def _stream_to_bytes[S: Stream, T: bytes](self: Cast) -> object | None:
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

    @_register
    def _stream_to_string[S: Stream, T: String](self: Cast) -> object | None:
        return self.to(str)

    @_register
    def _string_to_stream[S: String, T: Stream](self: Cast) -> object | None:
        if issubclass(self._t1, (bytearray, memoryview, BytesIO)):
            return self.cast(self.data, bytes)
        else:
            return self.cast(self.data, str)

    @_register
    def _string_to_str[S: String, T: str](self: Cast) -> object | None:
        val = self.data
        if isinstance(val, bytes):
            val = val.decode()
        return val

    @_register
    def _string_to_string[S: String, T: String](self: Cast) -> object | None:
        if isinstance(self.data, Streams):
            return self.cast(self.data, str)

    def _to_str(self) -> str | None:
        return self.cast(self.data, source=self.t0, target=str)

    @_register
    def _string_to_scalar[S: String, T: Scalar](self: Cast[S, T]) -> object | None:
        if (val := self._to_str()) is None:
            pass
        elif issubclass(self._t1, bool) and self.RGXS['bool'].fullmatch(val):
            return self.RGXS['bool_true'].fullmatch(val) is not None
        else:
            return self._try_to_deserialize(val)

    @classmethod
    def _try_to_deserialize(cls, text: str) -> Scalar | None:
        for stype in Scalars:
            name = stype.__name__
            if name in cls.RGXS and cls.RGXS[name].fullmatch(text):
                return stype(text)

    @_register
    def _string_to_time[S: String, T: Time](self: Cast[S, T]) -> object | None:
        # I. Normalize & analyze data
        data = self._to_str()
        if data is None:
            return None
        elif (ret := self.cast(data, float)) is not None:
            return self.cast(ret, source=float, target=self.t1)
        elif self.RGXS['short_iso_date'].match(data):
            data = f'20{data}'

        def _to_timedelta(_t: type[timedelta]) -> timedelta:
            if matches := list(Typist.RGXS['timedelta'].finditer(data)):
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

    @_register
    def _string_to_map[S: String, T: Map](self: Cast[S, T]) -> object | None:
        data = Cast.cast(self.data, str)
        if data:
            with ctx.suppress(Exception):
                return ut.from_yaml(data, dict)

    @_register
    def _string_to_vec[S: String, T: Vec](self: Cast[S, T]) -> object | None:
        if text := self.to(str):
            do_split, do_wrap = self.ctx.options.splits, self.ctx.options.wraps
            if do_split and text:
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

            if do_wrap:
                return [text]

    @_register
    def _string_to_struct(self: Cast[String, Struct]) -> T1 | None:
        return None

    @_register
    def _scalar_to_string(self: Cast[Scalar, String]) -> T1 | None:
        return None

    @_register
    def _scalar_to_scalar(self: Cast[Scalar, Scalar]) -> T1 | None:
        return None

    @_register
    def _scalar_to_time(self: Cast[Scalar, Time]) -> T1 | None:
        return None

    @_register
    def _time_to_string[S: Time, T: String](self: Cast[S, T]) -> T | None:
        ret: String | None = None
        if isinstance(self.data, datetime | date | time):
            ret = self.data.isoformat()
        elif isinstance(self.data, timedelta):
            ret = str(self.data.total_seconds())
        return self._ret(ret)

    @_register
    def _time_to_scalar[S: Time, T: Scalar](self: Cast[S, T]) -> T | None:
        ret = None
        d = self.data
        if isinstance(d, datetime):
            ret = d.timestamp()
        elif isinstance(d, date):
            ret = d.toordinal()
        elif isinstance(d, time):
            ret = 60 * ((60 * d.hour) + d.minute) + d.second
        elif isinstance(d, timedelta):
            ret = d.total_seconds()
        return self._ret(ret)

    @_register
    def _time_to_struct[S: Time, T: Struct](self: Cast[S, T]) -> T | None:
        return None

    @_register
    def _datetime_to_time[S: datetime, T: Time](self: Cast[S, T]) -> T | None:
        ret = self.data
        if issubclass(self._t1, time):
            ret = self.data.time().replace(tzinfo=UTC)
        elif issubclass(self._t1, date):
            ret = self.data.date()
        elif issubclass(self._t1, timedelta):
            return self.cast(self.data.timestamp(), source=float, target=self._t1)
        return self._ret(ret)

    @_register
    def _date_to_time[S: date, T: Time](self: Cast[S, T]) -> T | None:
        ret = self.data
        if issubclass(self._t1, time):
            ret = time()
        elif issubclass(self._t1, datetime):
            ret = datetime.combine(self.data, time(0, 0), tzinfo=UTC)
        elif issubclass(self._t1, timedelta):
            ret = self.cast(self.data.toordinal(), source=int, target=self._t1)
        return self._ret(ret)

    @_register
    def _stdtime_to_time[S: time, T: Time](self: Cast[S, T]) -> T | None:
        if issubclass(self._t1, datetime):
            pass
        elif issubclass(self._t1, date):
            pass
        elif issubclass(self._t1, time):
            pass

    @_register
    def _timedelta_to_time[S: timedelta, T: Time](self: Cast[S, T]) -> T | None:
        num = Cast.cast(self.data, source=self.t0, target=int)
        return Cast.cast(num, source=int, target=self.t1)

    @_register
    def _enum_to_string[S: Enum, T: String](self: Cast[S, T]) -> T | None:
        ret = self.ctx.try_method(self._t1, 'write', _tvar=str)
        if ret is None:
            name, value = self.data.name, self.data.value
            ret = value if isinstance(value, str) else str(name).lower()
        return self._ret(ret)

    @_register
    def _enum_to_scalar[S: Enum, T: Scalar](self: Cast[S, T]) -> T | None:
        value = self.data.value
        if value and isinstance(value, (*Strings, *Scalars)):
            return Cast.cast(value, self._t1)

    @_register
    def _enum_to_time[S: Enum, T: Time](self: Cast[S, T]) -> T | None:
        value = self.data.value
        if value and isinstance(value, (*Strings, *Scalars)):
            return Cast.cast(value, self._t1)

    @_register
    def _enum_to_enum[S: Enum, T: Enum](self: Cast[S, T]) -> T | None:
        # I. If the enum has it's own read method, try that on the name and value
        name, value = self.data.name, self.data.value
        for val in (name, value):
            if ret := self.ctx.try_method(self._t1, 'read', val, _tvar=self._t1):
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

    @_register
    def _enum_to_vec[S: Enum, T: Vec](self: Cast[S, T]) -> T | None:
        return None

    @_register
    def _enum_to_map[S: Enum, T: Map](self: Cast[S, T]) -> T | None:
        return None

    @_register
    def _enum_to_iter[S: Enum, T: Iter](self: Cast[S, T]) -> T | None:
        return None

    @_register
    def _enum_to_model[S: Enum, T: Model](self: Cast[S, T]) -> T | None:
        return None

    @_register
    def _object_to_enum[S: Object, T: Enum](self: Cast[S, T]) -> T | None:
        ret = self.ctx.try_method(self._t1, 'read', self.data, _tvar=self._t1)
        return ret if ret is not None else None

    @_register
    def _string_to_flag[S: String, T: Flag](self: Cast[S, T]) -> T | None:
        text = self._to_str()
        if text is None:
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

    @_register
    def _scalar_to_enum[S: Scalar, T: Enum](self: Cast[S, T]) -> T | None:
        return self._t1(self.data)

    @_register
    def _string_to_enum[S: String, T: Enum](self: Cast[S, T]) -> T | None:
        text = (self._to_str() or '').strip()
        if not text:
            return
        members = dict(self._t1.__members__)
        if (
            self.t1.vals
            and (val := self.cast(text, self.t1.vals)) is not None
            and (ret := ut.find_key(members, val))
        ):
            # Get by value
            pass
        elif ret := members.get(text.upper()):
            # Get by name
            pass

        return self._ret(ret)

    @_register
    def _iter_to_vec[S: Iter, T: Vec](self: Cast[S, T]) -> T | None:
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
            ret = self.ctx.multicast(ret, self.t1.vals, skip=False)
        return self._ret(ret)

    @_register
    def _iter_to_object[S: Iter, T: object](self: Cast[S, T]) -> T | None:
        """Convert iterables by proxing them into simple lists."""
        return self.proxy(self.to(list))

    @_register
    def _atom_to_vec[S: Atom, T: Vec](self: Cast[S, T]) -> T | None:
        if self.data and self.t1.vals:
            with ctx.suppress(TypeError):
                return self._ret([self.to(self.t1.vals)])

    @_register
    def _flag_to_vec[S: Flag, T: Vec](self: Cast[S, T]) -> T | None:
        data = [self._t0(member.value) for member in self._t0 if member in self.data]
        return self._ret(data)

    @_register
    def _flag_to_map[S: Flag, T: Map](self: Cast[S, T]) -> T | None:
        ret = {member.name: member.value for member in self._t0 if member in self.data}
        return self._ret(ret)

    @_register
    def _atom_to_map[S: Atom, T: Map](self: Cast[S, T]) -> T | None:
        return None

    @_register
    def _atom_to_struct[S: Atom, T: Struct](self: Cast[S, T]) -> T | None:
        return None

    @_register
    def _vec_to_flag[S: Vec, T: Flag](self: Cast[S, T]) -> T | None:
        ret = self._t1(0)
        for member in self.data:
            if (_new := self.cast(member, self._t1)) is not None:
                ret |= _new
        return ret

    @_register
    def _vec_to_time[S: Vec, T: Time](self: Cast[S, T]) -> T | None:
        ret = list(self.data)
        if not ret:
            pass
        elif len(ret) == 1 and (_vt := self.t0.vals) and MyType.is_atom_type(_vt):
            # I. Unwrap monotomic lists
            ret = self.proxy(ret[0])
        elif len(ret) >= 3:
            # II. it's a sequence of 3 or more values, try interpreting the first 3 as time
            # components
            with ctx.suppress(Exception):
                ret = self._type_branch(
                    self._t1,
                    _datetime=lambda _t: _t(*ret, tzinfo=UTC),
                    _date=lambda _t: _t(*ret),
                    _time=lambda _t: _t(*ret).replace(tzinfo=UTC),
                )
        return self._ret(ret)

    @_register
    def _vec_to_atom[S: Vec, T: Atom](self: Cast[S, T]) -> T | None:
        return

    @_register
    def _vec_to_vec[S: Vec, T: Vec](self: Cast[S, T]) -> T | None:
        ret = self.data
        if self.t0.vals and self.t0.vals != self.t1.vals:
            ret = self.ctx.multicast(self.data, self.t1.vals, skip=False)
        return self._ret(ret)

    @_register
    def _vec_to_map[S: Vec, T: Map](self: Cast[S, T]) -> T | None:
        ret = None
        if MyType.is_map(self.data):
            # I. Cast item lists
            ret = dict(self.data)

        elif issubclass(self._t1, Counter):
            # II. Cast counters, the only map type that takes an iter of single items
            if _kt := self.t1.keys:
                ret = self.ctx.multicast(self.data, _kt, skip=False)
            ret = self.data

        return self._ret(ret)

    @_register
    def _vec_to_iter[S: Vec, T: Iter](self: Cast[S, T]) -> T | None:
        return None

    @_register
    def _vec_to_model[S: Vec, T: Model](self: Cast[S, T]) -> T | None:
        return None

    @_register
    def _map_to_string[S: Map, T: String](self: Cast[S, T]) -> T | None:
        return None

    @_register
    def _map_to_scalar[S: Map, T: Scalar](self: Cast[S, T]) -> T | None:
        return None

    @_register
    def _map_to_time[S: Map, T: Time](self: Cast[S, T]) -> T | None:
        return None

    @_register
    def _map_to_enum[S: Map, T: Enum](self: Cast[S, T]) -> T | None:
        return None

    @_register
    def _map_to_vec[S: Map, T: Vec](self: Cast[S, T]) -> T | None:
        if not self.t1.vals or self.t1.vals.is_map_item():
            return self._ret(ut.map_items(self.data))

    @_register
    def _map_to_iter[S: Map, T: Vec](self: Cast[S, T]) -> T | None:
        if not self.t1.vals or self.t1.vals.is_map_item():
            return self._ret(iter(ut.map_items(self.data)))

    @_register
    def _map_to_map[S: Map, T: Map](self: Cast[S, T]) -> T | None:
        """Doc Case."""
        ret = None
        if items := ut.map_items(self.data):
            keys, values = mi.unzip(items)
            if self.t1.keys:
                keys = self.ctx.multicast(keys, self.t1.keys, skip=False)
            if self.t1.vals:
                values = self.ctx.multicast(values, self.t1.vals, skip=False)
            ret = dict(zip(keys, values, strict=True))

            if issubclass(self._t1, defaultdict) and self.t1.vals:
                return self._t1(self.t1.vals.main, ret)  # type: ignore
        return self._ret(ret)

    @_register
    def _map_to_iter[S: Map, T: Iter](self: Cast[S, T]) -> T | None:
        return None

    @_register
    def _map_to_model[S: Map, T: Model](self: Cast[S, T]) -> T | None:
        return None

    @_register
    def _iter_to_atom[S: Iter, T: Atom](self: Cast[S, T]) -> T | None:
        return None

    @_register
    def _iter_to_struct[S: Iter, T: Struct](self: Cast[S, T]) -> T | None:
        return None

    @_register
    def _model_to_map[S: Model, T: Atom](self: Cast[S, T]) -> T | None:
        return None

    @_register
    def _model_to_model[S: Model, T: Model](self: Cast[S, T]) -> T | None:
        return None

    @_register
    def _model_to_object[S: Model, T: Map](self: Cast[S, T]) -> T | None:
        return None

    # def _to_class[C](self, data: object, target: type[C]) -> C | None:
    @_register
    def _to_model[S: Any, T: Model](self: Cast[S, T]) -> T | None:
        """Cast data to a class instance using various instantiation strategies.

        Args:
            data: The source data to instantiate from.
            target: The target class type.
        Returns:
            Class instance if successful, None otherwise.
        """
        data = self.data
        # I. First, try to use the semi-standard `new()` method if available
        if (ret := self.ctx.try_method(self._t1, 'new', data, _tvar=self._t1)) is not None:
            return ret

        if ut.is_map(data):
            kwargs = self._cast_members(ut.map_items(data), self._t1)
            ret = self.ctx.invoke(self._t1, **kwargs)
        else:
            ret = self.ctx.invoke(self._t1, data)

        return self._ret(ret)

    @_register
    def _model_to_struct[S: Model, T: Struct](self: Cast[S, T]) -> T | None:
        return None

    @_register
    def _struct_to_atom[S: Struct, T: Atom](self: Cast[S, T]) -> T | None:
        return None

    @_register
    def _struct_to_struct[S: Struct, T: Struct](self: Cast[S, T]) -> T | None:
        return None

    @_register
    def _func_to_atom[S: Func, T: Atom](self: Cast[S, T]) -> T | None:
        return None

    @_register
    def _vec_to_atom[S: Vec, T: Atom](self: Cast[S, T]) -> T | None:
        # 0. Take the first element of a series, if configured to
        if not issubclass(self._t1, Flag) and isinstance(self.data, Vecs) and self.data:
            item = mi.first(self.data)
            return self.proxy(item)

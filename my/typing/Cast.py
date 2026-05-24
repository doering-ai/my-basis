############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import ClassVar, Literal, Any
from collections import Counter, defaultdict
from collections.abc import (
    Callable,
    Iterable,
    Mapping,
    Sequence,
)
import typing as ty
from datetime import date, datetime, time, timedelta, UTC
from enum import Enum, Flag
import inspect
import logging
import itertools as it

### EXTERNAL
import pydantic as pyd
import dateutil.parser
import regex as re

### INTERNAL
from ..infra import (
    Atomic,
    Time,
    Series,
    Scalar,
    Map,
    Maps,
    Serieses,
    is_scalar,
    is_series,
    is_time,
    is_enum,
)
from ..utils import ut
from .MyType import MyType

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from my import Typist  # noqa

logger = logging.getLogger()


############
### BODY ###
############
class Cast[T0, T1](pyd.BaseModel):
    """An ephemeral state machine that the cast defined by its inputs."""

    CACHE: ClassVar[dict[tuple[MyType, MyType], Cast]] = {}
    RGXS: ClassVar[dict[str, re.Pattern]] = ut.regex_dict(
        ### Atomic Types
        int=r'-?\d+',
        float=r'-?\d+(?:\.\d+)?',
        bool=r'(?i:t(?:rue)?|y(?:es)?|no?|f(?:alse)?|enabled?|disabled?|on|off|[01])',
        bool_true=r'(?i:t(?:rue)?|y(?:es)?|enabled?|on|1)',
        datetime=r'\d\d(?:\d\d)?[-./]\d\d[-./]\d\d(?:\D\d\d:\d\d:\d\d(?:\.\d+)?)?',
        enum=r'<(?P<class>[_[:upper:]]\w*)\.(?:\|?(?P<member>[_A-Z\d]+))+: (?P<value>.+)>',
    )

    ctx: Typist
    t0: MyType
    t1: MyType

    @classmethod
    def new(cls, ctx: Typist, data: T0, target: type[T1]) -> T1 | None:
        """Factory method to both create and invoke a Cast instance in a single call."""
        return cls(ctx=ctx, t0=MyType.metaparse(data), t1=MyType.parse(target))(data)

    def __call__(self, data: T0) -> T1 | None:
        """Internal casting implementation that routes to specialized conversion methods.

        Args:
            data: The source data to cast.
            source: The MyType of the source data.
            target: The target MyType to cast to.
        Returns:
            Cast data if successful, None otherwise.
        """
        # I. Handle literals as a very special case
        if self.t1.literal_members:
            return self.to_literal(data)

        # II. Reject casts to unhandled or split types -- that should be handled by the caller.
        if (main := self.t1.main_type) is None or self.t1.is_split:
            return None

        # III. Handle all other data types in their own methods
        if is_scalar(data):
            return self.to_scalar(data, main)
        elif issubclass(main, Maps):
            return self._to_map(data, main, self.t1)  # type: ignore
        elif is_series(main):
            return self._to_series(data, main, self.t1)  # type: ignore
        elif inspect.isclass(main):
            return self._to_class(data, main)
        else:
            logger.warning(f'Unknown main type for casting: {main}')
        return None

    # -------------------
    # `.` Initial Methods
    # -------------------

    # -------------------
    # `-` Private Methods
    # -------------------
    def _enum_to_atomic[A: Atomic](self, data: Enum, target: type[A]) -> A | None:
        """Convert an Enum to an atomic type (str, int, float, bool, bytes).

        Args:
            data: The Enum value to convert.
            target: The target atomic type.
        Returns:
            Converted atomic value if successful, None otherwise.
        """
        val = None
        if issubclass(target, str | bytes):
            ret = self.ctx.try_method(target, 'write', _tvar=str)
            if ret is None:
                ret = data.value if isinstance(data.value, str) else str(data.name).lower()
            ty.assert_type(ret, str)
            val = ret.encode() if issubclass(target, bytes) else ret
        elif issubclass(target, int | float):
            if isinstance(data.value, int | float):
                val = data.value
        elif issubclass(target, bool):
            val = data.value

        return target(val) if val is not None else None

    def _time_to_atomic[A: Atomic](self, data: Time, target: type[A]) -> A | None:
        """Convert a Time object to an atomic type (str, int, float, bool, bytes).

        Args:
            data: The Time value (datetime, date, time, or timedelta) to convert.
            target: The target atomic type.
        Returns:
            Converted atomic value if successful, None otherwise.
        """
        # 0. Clean up timezones
        if isinstance(data, datetime) and data.tzinfo != UTC:
            data = data.astimezone(UTC)
        elif isinstance(data, time) and data.tzinfo != UTC:
            data = data.replace(tzinfo=UTC)
        assert is_time(data), f'Invalid time passed: {data}'

        val = None
        # I. Write raw text or bytes
        if issubclass(target, str):
            if isinstance(data, datetime | date | time):
                val = data.isoformat().split('+', 1)[0]
            else:
                val = data
        elif issubclass(target, bytes):
            if (res := self._time_to_atomic(data, str)) is not None:
                val = res.encode()

        # II. Cast to posix timestamps
        elif issubclass(target, int | float):
            if isinstance(data, datetime):
                val = data.timestamp()
            elif isinstance(data, date):
                val = data.toordinal()
            elif isinstance(data, time):
                val = 60 * ((60 * data.hour) + data.minute) + data.second
            else:
                val = data.total_seconds()

        # III. Case non-zero values to `True`
        elif issubclass(target, bool):
            if isinstance(data, datetime):
                val = data.timestamp() > 0
            if isinstance(data, date):
                val = data.toordinal() > 0
            elif isinstance(data, time):
                val = data.hour > 0 or data.minute > 0 or data.second > 0
            else:
                val = data.total_seconds() > 0

        return target(val) if val is not None else None

    def _str_to_atomic[A: Atomic](self, data: str, target: type[A]) -> A | None:
        """Convert a string to an atomic type using regex pattern matching.

        Args:
            data: The string to convert.
            target: The target atomic type.
        Returns:
            Converted atomic value if pattern matches, None otherwise.
        """
        data = data.strip()
        val = None
        if (issubclass(target, int) and self.RGXS['int'].fullmatch(data)) or (
            issubclass(target, float) and self.RGXS['float'].fullmatch(data)
        ):
            val = data

        elif issubclass(target, bool) and self.RGXS['bool'].fullmatch(data):
            val = self.RGXS['bool_true'].fullmatch(data)

        elif issubclass(target, time):
            return self._str_to_time(data, target)

        elif issubclass(target, bytes):
            val = data.encode()

        return target(val) if val is not None else None

    def _chain[R](self, data: object, target: type[R]) -> R | None:
        return Cast.new(self.ctx, data, target)

    # -------------------
    # `+` Primary Methods
    # -------------------
    def to_literal(self, data: object) -> T1 | None:
        """Cast data to a literal type or literal tuple.

        Fails silently if the passed data is a sequence that differs in length from the target
        type's expectations.

        Args:
            data: The source data to cast.
            target: The target literal MyType.
        Returns:
            Cast data if it matches the literal, None otherwise.
        """
        if not self.t1.literal_members or self.t1.origin is None or data is None:
            return None

        if self.t1.origin is Literal:
            # I. Cast Literals
            if any(val_type.check(data) for val_type in self.t1.args):
                ret = data
            else:
                ret = next(
                    (
                        ret
                        for val_type in self.t1.args
                        if (ret := Cast(ctx=self.ctx, t0=self.t0, t1=val_type))
                        and self.t1.literal_check(ret)
                    ),
                    None,
                )
        elif isinstance(self.t1.origin, type) and issubclass(self.t1.origin, tuple):
            # II. Cast literally-positioned tuples
            if not isinstance(data, Sequence):
                data = self._to_series(data, tuple)

            if data is not None and len(data) == len(self.t1.args):
                cast_values = it.starmap(self._chain, zip(data, self.t1.args, strict=True))
                # Use the parent type's actual class constructor directly via this handle
                ret = self.t1.origin(cast_values)
            else:
                return None
        else:
            return None

        return ret if self.t1.literal_check(ret) else None

    def to_scalar[A: Scalar](self, data: object, target: type[A]) -> A | None:
        """Cast data to an atomic type (str, int, float, bool, Enum, or Time).

        Args:
            data: The source data to cast.
            target: The target atomic type.
        Returns:
            Cast atomic value if successful, None otherwise.
        """
        # 0. Take the first element of a series, if configured to
        if not issubclass(target, Flag) and is_series(data):
            if (n := len(data)) and (self.firsts or (self.atomics and n == 1)):
                data = mi.first(data)

        ret = None
        if isinstance(data, target):
            return data

        # I. Create new scalars
        elif is_enum(target):
            ret = self._to_enum(data, target)
        elif is_time(target):
            ret = self._to_times(data, target)

        # II. Convert complex scalars into atomics
        elif is_enum(data):
            ret = self._enum_to_scalar(data, target)
        elif is_time(data):
            ret = self._time_to_scalar(data, target)

        # III. Read and write raw strings
        elif isinstance(data, str):
            ret = self._str_to_atomic(data, target)
        elif issubclass(target, str) and (fn := self.get_str_method(data)):
            ret = self.invoke(fn)

        if ret is None or not isinstance(ret, target):
            with ctx.suppress(ValueError, TypeError):
                ret = target(data if ret is None else ret)  # type: ignore
        return ret  # type: ignore

    def _to_class[C](self, data: object, target: type[C]) -> C | None:
        """Cast data to a class instance using various instantiation strategies.

        Args:
            data: The source data to instantiate from.
            target: The target class type.
        Returns:
            Class instance if successful, None otherwise.
        """
        # I. First, try to use the semi-standard `new()` method if available
        if (ret := self.try_method(target, 'new', data, _tvar=target)) is not None:
            return ret

        if ut.is_map(data):
            kwargs = self._cast_members(ut.map_items(data), target)
            ret = self.invoke(target, **kwargs)
        else:
            ret = self.invoke(target, data)

        if isinstance(ret, target):
            return ret
        return None

    def _cast_members(self, items: Iterable[tuple[str, Any]], target: type) -> dict[str, Any]:
        """Cast a mapping's members to match a target class's field types.

        Args:
            items: Key-value pairs to cast.
            target: The target class type with type annotations.
        Returns:
            Dictionary with cast values matching target's field types.
        """
        annotations = ut.instance_aliases(target)
        return {key: self.typist.flexcast(val, annotations.get(key, None)) for key, val in items}

    def _to_enum[E: Enum](self, data: object, target: type[E]) -> E | None:
        """Cast data to an Enum or Flag type.

        Args:
            data: The source data (int, str, series, or another Enum).
            target: The target Enum or Flag type.
        Returns:
            Enum instance if successful, None otherwise.
        """
        # I. If the enum has it's own read method, try that first on any datatype
        if read_method := self.get_method(target, 'read'):
            if (ret := self.invoke(read_method, data)) is not None:
                return ret

        # II. Next, try some Flag-specific transformations
        if issubclass(target, Flag):
            members = []
            if is_series(data):
                members = data
            elif isinstance(data, str) and '|' in data:
                members = re.split(r' *\| *', data.strip())

            if members:
                ret = target(0)
                for member in members:
                    if _new := self._to_enum(member, target):
                        ret |= _new
                return ret  # type: ignore[bad-return]

        if isinstance(data, int):
            # int_to_enum
            return target(data)
        elif isinstance(data, str):
            # str_to_enum
            data = data.strip()
            if data.isdigit():
                return target(int(data))
            elif ret := target.__members__.get(data.upper(), None):
                return ret
        elif is_enum(data):
            if read_method:
                if (ret := self.invoke(read_method, data.value)) is not None:
                    return ret
                if (ret := self.invoke(read_method, str(data.name))) is not None:
                    return ret

            if data.name in target.__members__:
                return target[data.name]
            elif key := ut.find_key(target.__members__, data.value):
                return target[key]

        return None

    TYPES: ClassVar[dict] = dict()

    def _enum_to_times[Te: Time](self, data: Enum, target: type[Te]) -> Te:
        if (ret := self._to_times(data.value, target)) is not None:
            return ret
        elif (ret := self._to_times(data.name, target)) is not None:
            return ret
        raise ValueError(f'Cannot convert Enum {data} to time')

    def _datetime_to_time[Tt: time](self, data: datetime, target: type[Tt]) -> Tt:
        return self._time_to_time(data.replace(tzinfo=UTC).time(), target)

    def _time_to_time[Tt: time](self, data: time, target: type[Tt]) -> Tt:
        _raw = data.replace(tzinfo=UTC)
        return target(
            hour=_raw.hour,
            minute=_raw.minute,
            second=_raw.second,
            microsecond=_raw.microsecond,
            tzinfo=UTC,
        )

    def _to_times[T: Time](self, data: object, target: type[T]) -> T | None:
        """Convert a string or number to a datetime or timedelta object, if possible."""
        # 0. Normalize non-scalar data to strings
        if not is_scalar(data):
            data = str(data)
        # metaparse
        transforms = {
            ('str', 'times'): self._str_to_time,
            ('int', 'times'): self._num_to_time,
            ('float', 'times'): self._num_to_time,
            ('bool', 'times'): lambda _data, _target: None,
            ('enum', 'times'): self._enum_to_times,
            ('time', 'time'): self._time_to_time,
        }

    def _str_to_time[T: Time](self, data: str, target: type[T]) -> T | None:
        """Convert a string to a Time object using various parsing strategies.

        Args:
            data: The string to parse.
            target: The target Time type (datetime, date, time, or timedelta).
        Returns:
            Parsed Time object if successful, None otherwise.
        """
        # . I. Normalize & analyze data
        data = data.strip()
        if data.isdigit():
            return self._to_times(int(data), target)
        elif self.RGXS['float'].fullmatch(data):
            return self._to_times(float(data), target)
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
                target,
                _datetime=lambda _t: _t.fromisoformat(data).replace(tzinfo=UTC),
                _time=lambda _t: _t.fromisoformat(data).replace(tzinfo=UTC),
                _date=lambda _t: _t.fromisoformat(data),
                _timedelta=_to_timedelta,
            )

        # III. Fall back to an external, flexible library
        if d := dateutil.parser.parse(data):
            d = d.replace(tzinfo=UTC)
            return self._type_branch(
                target,
                _datetime=lambda _t: _t.fromtimestamp(d.timestamp(), tz=UTC),
                _date=lambda _t: _t.fromordinal(d.toordinal()),
                _time=lambda _t: _t.fromisoformat(d.time().isoformat()),
                _timedelta=lambda _t: _t(days=d.day, seconds=d.second, microseconds=d.microsecond),
            )

        return None

    def _branch[T](
        self,
        data: object,
        target: type[T],
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
        _series: Callable[[Series], T] | None = None,
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
            (Serieses, _series),
            (Maps, _map),
        ]

        for tvar, handler in pairs:
            if handler and isinstance(data, tvar):
                return handler(data)  # type: ignore
        return None

    def _type_branch[T](
        self,
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
        _series: Callable[[type[Series]], Series] | None = None,
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
            (Serieses, _series),
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

    def _to_map[M: dict](
        self, data: object, tvar: type[M], details: MyType | None = None
    ) -> M | None:
        """Cast data to a mapping type (dict, Counter, etc.).

        Args:
            data: The source data to cast.
            tvar: The target mapping type.
            details: Pre-parsed MyType details (will be parsed if None).
        Returns:
            Cast mapping if successful, None otherwise.
        """
        # I.i. Parse details if none were given
        if details is None:
            details = MyType.parse(tvar)
            tvar = details.main_type  # type: ignore
            assert tvar is not None, f'Cannot parse series type from {tvar}'

        # I.ii. Pre-cast strings by parsing JSON or YAML content
        if data and isinstance(data, str) and data[0] == '{' and data[-1] == '}':
            with ctx.suppress(Exception):
                return ut.from_yaml(data, tvar)

        # II.i. Main Case: cast maps and map-ready lists of 2-tuples ("items")
        ret = None
        if ut.is_map(data) and (items := ut.map_items(data)):
            kvar, vvar = details.key_type, details.val_type
            keys, values = mi.unzip(items)
            if kvar:
                keys = self.multicast(keys, kvar, skip=False)
            if vvar:
                values = self.multicast(values, vvar, skip=False)
            new_data = dict(zip(keys, values, strict=True))

            if issubclass(tvar, defaultdict):
                ret = tvar(vvar.main_type if vvar else None, new_data)
            else:
                ret = tvar(new_data)

        # II.ii. Cast counters, the only map type that takes an iter of single items
        elif issubclass(tvar, Counter) and is_series(data):
            if details.key_type:
                data = self.multicast(data, details.key_type, skip=False)
            ret = tvar(data)

        return ret  # type: ignore

    def _to_series[S: Series](
        self, data: object, tvar: type[S], details: MyType | None = None
    ) -> S | None:
        """Cast data to a series type (list, tuple, set, deque), splitting strings.

        Args:
            data: The source data to cast.
            tvar: The target series type.
            details: Pre-parsed MyType details (will be parsed if None).
        Returns:
            Cast series if successful, None otherwise.
        """
        # I. Parse details if none were given
        if details is None:
            details = MyType.parse(tvar)
            tvar = details.main_type  # type: ignore
            assert tvar is not None, f'Cannot parse series type from {tvar}'

        # II. Preprocess data into an iterable form
        if isinstance(data, str):
            # II.i. Split strings if configured to do so
            data = self._split_str(data)
        elif isinstance(data, Mapping):
            # II.ii. Split maps into two-tuples if possible, otherwise fail early
            #        This is to avoid unintentional parsing of just a map's keys
            if (items := ut.map_items(data)) and (
                not details.val_type or details.val_type.is_map_item()
            ):
                data = items
            else:
                return None
        elif isinstance(data, Flag):
            # II.iii. Split Flags into their member names
            dt = type(data)
            data = [dt(member.value) for member in dt if member in data]
        elif not isinstance(data, Iterable) and self.wraps:
            # II.iv. Wrap all other non-iterables to at least give them a shot
            data = [data]

        # III. Perform the actual casting -- first the values, then the container itself
        with ctx.suppress(TypeError):
            if data and is_series(data) and details.val_type:
                data = self.multicast(data, details.val_type, skip=False)
            return tvar(data)  # type: ignore
        return None

    def _split_str(self, data: str) -> list[str] | None:
        """Split a string into a list using various delimiters.

        Args:
            data: The string to split.
        Returns:
            List of split strings if delimiters found, None otherwise.
        """
        if self.splits and data:
            if data[0] == '[' and data[-1] == ']' and data.count('[') == 1:
                # II. Split yaml-like flow sequences
                with ctx.suppress(Exception):
                    return ut.from_yaml(data, list[str], cast=False)
            elif char := next(filter(data.__contains__, [',', '//', ':', '.']), ''):
                # III. Split on common delimiters in order of preference
                #       e.g. one.oneA:two splits on colons, but one.oneA splits on periods
                return list(filter(bool, map(str.strip, data.split(char))))

        return [data] if self.wraps else None

    # ------------------
    # `*` Public Methods
    # ------------------

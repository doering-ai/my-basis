############
### HEAD ###
############
### STANDARD
from typing import (
    Any,
    ClassVar,
    Collection,
    Iterable,
    Iterator,
    Literal,
    Mapping,
    Sequence,
    TypeGuard,
    TypeVar,
    Hashable,
)
from pathlib import Path
from collections import Counter, deque
import collections.abc as abc
from types import UnionType
import regex as re
import functools as ft
import itertools as it
import more_itertools as mi
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from copy import deepcopy
import json

### EXTERNAL
import logfire as fire
import pydantic as pyd
import dateutil.parser

## YAML
import yaml

### INTERNAL
from ..base import utilities as ut
from ..perf import Cache, NestedCache

############
### DATA ###
############
# Initialize generic type variable
T = TypeVar('T')
C = TypeVar('C')

# Specific type helpers
Key = TypeVar('Key')
Value = TypeVar('Value')

# Type Aliases
Series = list | tuple | set | deque
MapItems = list[tuple] | tuple[tuple] | deque[tuple] | set[tuple]
Atomic = str | int | float | bool
AtomicType = type[str] | type[int] | type[float] | type[bool]
TimeType = date | datetime | time | timedelta

TypeArg = type | tuple[type, ...] | None
ParsedType = tuple[type | None, TypeArg, TypeArg]

DEBUG = True


############
### BODY ###
############
class Typist(pyd.BaseModel):
    # Static Global Members
    ### Types
    SPECIAL_TYPES: ClassVar[tuple[str, ...]] = (
        "Any", "object", "NoReturn", "TypeGuard", "Concatenate", "Callable", "Coroutine",
        "Generator", "NoneType"
    )
    WRAPPER_TYPES: ClassVar[tuple[str, ...]] = (
        'Literal', 'Union', 'Annotated', 'Final', 'ClassVar', 'TypeAlias', 'Generic', 'Protocol',
        'Optional'
    )

    ### RGXS (can't use RegexStore since they depend on this class)
    RGXS: ClassVar[dict[str, re.Pattern]] = ut.regex_dict(
        dict(
            # Types
            int=r'-?\d+',
            float=r'-?\d+(?:\.\d+)?',
            bool=r'(?i:true|y(?:es)?|no?|false)',
            bool_true=r'(?i:true|y(?:es)?)',
            datetime=r'\d\d(?:\d\d)?[-./]\d\d[-./]\d\d(?:\D\d\d:\d\d:\d\d(?:\.\d+)?)?',

            # Others
            splitter=r' *(?:[,]|\/\/) *',
            no_space_splitter=r'(?<=\w)[.:](?=\w)',
            yaml=r'(?sm)^```yaml *\n(?P<content>.+?)\n``` *$',
            timedelta=r'(?i)' + ut.multi_rgx(
                r'(?P<weeks>\d+) ?(?:w|weeks?)(?![a-z])',
                r'(?P<days>\d+) ?(?:d|days?)(?![a-z])',
                r'(?P<hours>\d+) ?(?:h|hours?)(?![a-z])',
                r'(?P<minutes>\d+) ?(?:m|mins?|minutes?)(?![a-z])',
                r'(?P<seconds>\d+) ?(?:s|secs?|seconds?)(?![a-z])',
                r'(?P<milliseconds>\d+) ?(?:ms|milliseconds?)(?![a-z])',
                r'(?P<microseconds>\d+) ?(?:us|microseconds?)(?![a-z])',
                r'(?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d+(?:\.\d+)?)\b',
                branching=True,
            ),
            short_iso_date=r'\d\d[-./]\d\d[-./]\d\d',
            encoding=r'&#?\w+;',
        )
    )
    DESERIALIZE_RGXS: ClassVar[dict[str, re.Pattern]] = dict(
        int=RGXS['int'],
        float=RGXS['float'],
        bool=RGXS['bool'],
        datetime=RGXS['datetime'],
    )
    ATOMIC_TYPES: ClassVar[dict[str, type]] = dict(
        int=int,
        float=float,
        bool=bool,
        str=str,
        datetime=datetime,
    )

    # Dynamic Global Members
    PARSE_CACHE: ClassVar[Cache[str, ParsedType]] = Cache()
    MATCH_CACHE: ClassVar[NestedCache[tuple[str, str], bool]] = NestedCache(signature=(str, str))

    # Instance Members (for changing CASTING behavior only)
    atomics: bool = False
    firsts: bool = False
    splits: bool = False

    # -------------------
    # `0` Initial Methods
    # -------------------
    @classmethod
    def setup(cls) -> None:
        if getattr(cls, 'YAML_CONFIG', None):
            return

    def __repr__(self) -> str:
        return f'Typist(atomics={self.atomics}, firsts={self.firsts}, splits={self.splits})'

    # -------------------
    # `-` Private Methods
    # -------------------
    @staticmethod
    def _parseable(target: TypeArg) -> TypeGuard[type | tuple[type, ...]]:
        if target is None:
            return False
        elif isinstance(target, tuple):
            return any(Typist._parseable(child) for child in target)
        else:
            return getattr(target, '__name__', '') not in Typist.SPECIAL_TYPES

    @staticmethod
    def _read(typevar: type | None) -> tuple[str, type | None, tuple[type | None, ...]]:
        if typevar is None:
            return '', None, tuple()
        return (
            str(getattr(typevar, '__name__', '')),
            getattr(typevar, '__origin__', None),
            tuple(
                arg if (not isinstance(arg, tuple) and Typist._parseable(arg)) else None
                for arg in getattr(typevar, '__args__', [])
            ),
        )

    def _cast_model_members(self, items: Iterable[tuple[Any, Any]],
                            target: type[pyd.BaseModel]) -> dict[str, Any]:
        annotations = ut.instance_aliases(target)
        return {key: typist.flexcast(val, annotations.get(key, None)) for key, val in items}

    def _sorter(self, origin: type, tvar: TypeArg) -> int:
        ret = 10
        if origin == tvar:
            return -99

        for t0, t1 in filter(all, zip(*map(self.parse, (origin, tvar)))):
            ret -= 1
            if self.match(t0, t1):
                ret -= 2
        return ret

    def _tuple_is(self, value: tuple, tvar: type) -> bool:
        """
        Check if a tuple matches a type variable, considering its arguments.
        """
        args = list(getattr(tvar, '__args__', []))
        n_vals, n_args = len(value), len(args)

        if n_args == 0:
            # I. Without args, we assume called checked the container's tuple-ness
            return True
        elif args[-1] is Ellipsis:
            # II. Handle ellipses
            if n_args == 1:
                return True
            else:
                args += [args[-2]] * (n_vals - n_args + 1)
        elif n_vals != n_args:
            # III. The lengths must match exactly
            return False

        return all(it.starmap(isinstance, zip(value, args)))

    def _cast(self, data: object, target: type, ktype: TypeArg, vtype: TypeArg) -> Any:
        # 0. Pick one value out of series data, if configured to
        if issubclass(target, Atomic | TimeType) and isinstance(data, Series):
            if self.firsts or (self.atomics and len(data) == 1):
                data = mi.first(data)

        # I. Cast atomics
        if issubclass(target, Atomic):
            data = self._cast_to_atomic(data, target)

        # II. Cast objects
        elif issubclass(target, Enum):
            data = self._cast_to_enum(data, target)
        elif issubclass(target, TimeType):
            data = self._cast_to_time(data, target)
        elif issubclass(target, pyd.BaseModel):
            data = self._cast_to_model(data, target)

        # III. Cast containers
        elif issubclass(target, Mapping):
            data = self._cast_to_map(data, target, ktype, vtype)
        elif issubclass(target, Series):
            data = self._cast_to_series(data, target, ktype, vtype)

        # IV. Finally, attempt to perform the actual (top-level) casting
        if not isinstance(data, target):
            try:
                data = target(data)  # type:ignore
            except Exception as e:
                fire.error(f'Failed to convert {data} (type={type(data)}) to type={target}')
                if DEBUG:
                    print(e)
                raise
        return data

    def _cast_to_atomic(self, data: object, target: type[Atomic]) -> object:
        if isinstance(data, Enum):
            return self._cast_from_enum(data, target)
        elif isinstance(data, TimeType):
            return self._cast_from_time(data, target)
        else:
            if isinstance(data, str):
                if issubclass(target, bool):
                    return bool(self.RGXS['bool_true'].match(data.strip()))
                return data.strip()
            elif issubclass(target, str):
                if hasattr(data, 'write') and callable(data.write):
                    return data.write()
                elif hasattr(data, 'to_string') and callable(data.to_string):
                    return data.to_string()
                return str(data)
        return data

    def _cast_from_enum(self, data: Enum, target: type[Atomic]) -> object:
        if issubclass(target, str):
            if hasattr(data, 'write') and callable(data.write):
                return data.write()
            elif isinstance(data.value, str):
                return data.value
            else:
                return data.name.lower()
        elif issubclass(target, int | float):
            if isinstance(data.value, int | float):
                return target(data.value)
            elif hasattr(data, 'index') and callable(data.index):
                return target(data.index)
            else:
                return 0
        else:
            return bool(data.value)

    def _cast_from_time(self, data: TimeType, target: type[Atomic]) -> object:
        # 0. Clean up datetime objects in particular
        if isinstance(data, datetime) and data.tzinfo != timezone.utc:
            data = data.astimezone(timezone.utc)
        elif isinstance(data, time) and data.tzinfo != timezone.utc:
            data = data.replace(tzinfo=timezone.utc)
        assert isinstance(data, TimeType), f'Invalid time passed: {data}'

        if issubclass(target, str):
            # I. Cast to string
            if isinstance(data, datetime | date | time):
                return data.isoformat().split('+', 1)[0]
            else:
                return str(data)

        elif issubclass(target, int | float):
            # II. Cast to posix timestamps
            if isinstance(data, datetime):
                return data.timestamp()
            elif isinstance(data, date):
                return data.toordinal()
            elif isinstance(data, time):
                return 60 * ((60 * data.hour) + data.minute) + data.second
            else:
                return data.total_seconds()

        elif issubclass(target, bool):
            # III. Check for non-zero values
            if isinstance(data, datetime):
                return data.timestamp() > 0
            if isinstance(data, date):
                return data.toordinal() > 0
            elif isinstance(data, time):
                return data.hour > 0 or data.minute > 0 or data.second > 0
            else:
                return data.total_seconds() > 0

        return ''

    def _cast_to_model(self, data: object, target: type[pyd.BaseModel]) -> object:
        if hasattr(target, 'new') and callable(target.new):
            # I. Shortcut to the "new" function, assuming it's ready to handle a basic data arg
            return target.new(data)
        elif items := ut.map_items(data):
            # II. Else, cast all the data and then pass it in to the normal pydantic constructor
            return target(**self._cast_model_members(items, target))
        return data

    def _cast_to_enum(self, data: object, target: type[Enum]) -> object:
        if hasattr(target, 'read'):
            return target.read(data)
        elif isinstance(data, str):
            return target.__members__.get(data.upper(), data)
        elif isinstance(data, int):
            return target(data)
        return data

    def _cast_to_time(self, data: object, target: type[TimeType]) -> TimeType | None:
        """ Convert a string or number to a datetime or timedelta object, if possible. """
        if not isinstance(data, Atomic):
            data = str(data)
        # 0. Clean data
        if isinstance(data, str):
            if data.isdigit():
                data = int(data)
            elif Typist.RGXS['float'].fullmatch(data):
                data = float(data)
            elif Typist.RGXS['short_iso_date'].match(data):
                data = f'20{data}'

        try:
            if isinstance(data, str):
                # I. Deserialize from iso timestamps (`yyyy-mm-dd` and/or `hh:mm:ss`)
                try:
                    if target is datetime:
                        return datetime.fromisoformat(data).replace(tzinfo=timezone.utc)
                    elif target is date:
                        return date.fromisoformat(data)
                    elif target is time:
                        return time.fromisoformat(data).replace(tzinfo=timezone.utc)
                    elif matches := list(Typist.RGXS['timedelta'].finditer(data)):
                        return timedelta(
                            **{
                                key: float(val)
                                for m in matches
                                for key, val in m.groupdict().items()
                                if val
                            }
                        )
                except ValueError:
                    if d := dateutil.parser.parse(data):
                        d = d.replace(tzinfo=None)
                        if target is datetime:
                            return d
                        elif target is date:
                            return d.date()
                        elif target is time:
                            return d.time()
                        elif target is timedelta:
                            return timedelta(
                                days=d.day, seconds=d.second, microseconds=d.microsecond
                            )

            elif isinstance(data, int | float):
                if target is datetime:
                    return datetime.fromtimestamp(data, tz=timezone.utc)
                elif target is date:
                    return date.fromordinal(int(data))
                elif target is time:
                    return datetime.fromtimestamp(data, tz=timezone.utc).time().replace(
                        tzinfo=timezone.utc
                    )
                else:
                    return timedelta(seconds=data)
        except ValueError as e:
            fire.error(f'Cannot cast from {type(data)} to time; {e}')
        return None

    def _cast_to_map(
        self, data: object, target: type[Mapping], ktype: TypeArg, vtype: TypeArg
    ) -> object:
        # III. Handle maps
        if items := ut.map_items(data):
            keys, values = mi.unzip(items)
            return dict(zip(self.flexcast_all(keys, ktype), self.flexcast_all(values, vtype)))
        elif issubclass(target, Counter) and isinstance(data, Series) and ktype:
            return self.flexcast_all(data, ktype)

        # if issubclass(target, defaultdict):
        #     return target(self.parse(vtype)[0] or dict, data)  # type:ignore

        return data

    def _cast_to_series(
        self, data: object, target: type[Series], ktype: TypeArg, vtype: TypeArg
    ) -> object:
        """ Handle series (lists, tuples, deques, and sets) """
        # I. Prepare the data
        if isinstance(data, str) and self.splits:
            if '.' in data and not ut.has_any(data, ' ', ','):
                data = list(filter(bool, self.RGXS['no_space_splitter'].split(data)))
            else:
                data = list(filter(bool, self.RGXS['splitter'].split(data)))
        elif isinstance(data, Mapping) and (items := ut.map_items(data)):
            data = items
        elif not isinstance(data, Collection):
            data = list(data) if isinstance(data, Iterator) else [data]
        assert isinstance(data, Collection)

        # II. Perform the actual casting
        if issubclass(target, tuple) and isinstance(ktype, tuple):
            assert len(data) == len(ktype), f'Cannot cast {data} to tuple {target}.'
            return tuple(self.flexcast(item, itype) for item, itype in zip(data, ktype))
        elif vtype:
            return self.flexcast_all(data, vtype)
        return data

    # @classmethod
    # def yamlfix(cls, text: str, src_type: type | None = None) -> str:
    #     """ Fix the YAML code to ensure it is properly formatted. """
    #     # I. Do the actual fixing based on our pyproject.toml settings
    #     text = fix_code(text, config=cls.YAML_CONFIG).strip('\n')

    #     # II. Fix odd bug where root-level lists have extra indentation
    #     if src_type and issubclass(src_type, list) and '\n' in text:
    #         lines = text.splitlines()
    #         if all(line.startswith('  ') for line in lines[1:]):
    #             text = '\n'.join([lines[0]] + [line[2:] for line in lines[1:]])
    #     return text

    @staticmethod
    def _is_split(tvar: TypeArg) -> TypeGuard[tuple | UnionType | type]:
        return isinstance(tvar, UnionType | tuple) or getattr(tvar, '__name__', '') == 'Union'

    @staticmethod
    def _read_file(file: str | bytes | pyd.FilePath | None) -> str:
        """ Read a file and return its contents as a string. """
        if isinstance(file, bytes):
            return file.decode('utf-8')
        elif isinstance(file, Path):
            ut.validate_file(file)
            return file.read_text()
        elif not file:
            return ''
        else:
            return str(file)

    # -------------------
    # `+` Primary Methods
    # -------------------
    @staticmethod
    def parse(typevar: TypeArg) -> ParsedType:
        cls = Typist
        fullname = str(typevar)
        if cached := cls.PARSE_CACHE[fullname]:
            return cached

        # I. Initial checks for nullity and unions
        ret: ParsedType
        if not cls._parseable(typevar):
            ret = None, None, None
        elif isinstance(typevar, UnionType):
            ret = next(filter(any, map(cls.parse, typevar.__args__)), (None, None, None))
        elif isinstance(typevar, tuple):
            ret = next(filter(any, map(cls.parse, typevar)), (None, None, None))

        else:
            main_type: type | None = typevar
            key_type: TypeArg = None
            val_type: TypeArg = None

            # II. Read the types' basic fields up front, if present
            name, origin, args = cls._read(main_type)
            if name in cls.WRAPPER_TYPES:
                # II. Catch Wrappers (e.g. Union, ClassVar, Annotated, etc.)
                if origin is Literal:
                    args = tuple(map(type, args))
                main_type, key_type, val_type = next(
                    filter(any, map(cls.parse, args)), (None, None, None)
                )
            elif origin:
                # III. Catch Generics (e.g. dict[str, int])
                main_type = origin
                if (n_args := len(args)) > 0:
                    if issubclass(main_type, tuple):
                        # III.i. Parse tuples
                        if args[-1] is Ellipsis:
                            args = args[:-1]
                        if len(set(args)) == 1:
                            val_type = args[0]  # homo
                        else:
                            key_type = val_type = tuple(a if a else object for a in args)
                    elif issubclass(main_type, Counter):
                        # III.ii. Parse counters, the only map w/ one arg
                        key_type = args[0]
                        val_type = int
                    elif n_args == 1:
                        # III.iii. Parse other sequences
                        val_type = args[0]
                    elif n_args == 2:
                        # III.iv. Parse maps
                        key_type, val_type = args[:2]
            elif main_type and issubclass(main_type, Counter):
                # Niche case: Counters imply int values
                val_type = int

            # V. Don't return invalid types
            ret = (
                main_type,
                key_type if cls._parseable(key_type) else None,
                val_type if cls._parseable(val_type) else None,
            )

        cls.PARSE_CACHE[fullname] = ret
        return ret

    @staticmethod
    def _decompose_union(tvar: TypeArg) -> tuple[type | None, ...]:
        if isinstance(tvar, tuple):
            return tvar
        elif isinstance(tvar, UnionType) or getattr(tvar, '__name__', '') == 'Union':
            return tuple(getattr(tvar, '__args__', []))
        else:
            return tuple()

    @staticmethod
    def match(t0: TypeArg, t1: TypeArg, recurse: bool = False) -> TypeGuard[T]:
        """ Check if two types are equivelent. """
        if t0 is Any or t0 is None or t1 is Any or t1 is None:
            return True

        # 0. Create a unique ID for these arguments
        n0, n1 = str(t0), str(t1)
        if recurse:
            n1 = n1.upper()

        # I. Check cache
        cls = Typist
        if (cached := cls.MATCH_CACHE[n0, n1]) is not None:
            return cached

        recur = ft.partial(cls.match, recurse=recurse)
        ret = False

        # II. Decompose unions
        u0, u1 = map(cls._decompose_union, (t0, t1))
        if u0 and u1:
            ret = any(recur(i0, i1) for i0 in u0 for i1 in u1 if i0 and i1)
        elif u0:
            ret = any(recur(i0, t1) for i0 in u0 if i0)
        elif u1:
            ret = any(recur(t0, i1) for i1 in u1 if i1)
        else:
            # III. Main case: parse and check for subtype intersection
            c0, c0k, c0v = cls.parse(t0)
            c1, c1k, c1v = cls.parse(t1)
            if not c0 or not c1:
                # III.i. One or both is unparseable
                ret = False
            elif issubclass(c0, c1):
                # III.ii. If the base types match, check that the subtypes do as well
                ret = recur(c0k, c1k) and recur(c0v, c1v)
            elif recurse:
                # III.iii. If the main types don't match, either recurse or give up here
                if issubclass(c1, pyd.BaseModel):
                    # III.ii.a. Recurse into Pydantic models
                    ret = any(recur(t0, ann) for ann in ut.instance_fields(c1).values())
                elif c1v:
                    # III.ii.b. Recurse into the value field
                    ret = recur(t0, c1v)

        cls.MATCH_CACHE[n0, n1] = ret
        return ret

    def match_instances(self, inst0: object, inst1: object, recurse: bool = False) -> bool:
        return self.match(type(inst0), type(inst1), recurse)

    def flex_deserialize(self, values: Sequence[str]) -> Sequence[Atomic]:
        """
        Convert a list of strings to their most appropriate atomic types (int / float / bool).
        """
        if isinstance(values, str):
            values = [values]
        elif not isinstance(values, list):
            values = list(values)

        target_names = [
            ut.find_key(self.DESERIALIZE_RGXS, lambda rgx: bool(rgx.fullmatch(val)))
            for val in values
        ]
        if any(target_names):
            targets = [self.ATOMIC_TYPES.get(name, None) if name else None for name in target_names]
            return [
                self._cast(val, target, None, None) if target else val
                for val, target in zip(values, targets)
            ]
        else:
            return values

    def normalize_text(
        self,
        text: str,
        text_map: dict[str, str] = {},
        code_map: dict[str, str] = {},
    ) -> str:
        # Perform manual replacements of abnormal characters
        for old, new in text_map.items():
            text = text.replace(old, new)

        # Find and replace unicode & special WikiText HTML characters
        replacements = {}
        for match in self.RGXS['encoding'].finditer(text):
            code = match[0][1:-1]
            if code[0] == '#':
                try:
                    newtext = chr(int(code[1:]))
                except ValueError:
                    newtext = ''
            else:
                newtext = ut.get_any(code_map, code, code.lower()) or ''

            replacements[match[0]] = newtext

        for old, new in replacements.items():
            text = text.replace(old, new)

        return text

    # ------------------
    # `x` Public Methods
    # ------------------
    def check(self, data: object, tvar: type[T] | tuple[type[T], ...]) -> TypeGuard[T]:
        """
        Check if a data matches a type variable, recursively checking the values of containers.
        """
        if tvar is Any:
            return True
        elif isinstance(tvar, UnionType | tuple) or getattr(tvar, '__name__', '') == 'Union':
            # I. Recurse if given a union
            options = tvar if isinstance(tvar, tuple) else tvar.__args__  # type:ignore
            return any(self.check(data, option) for option in options)

        target, ktype, vtype = self.parse(tvar)
        if not target or not isinstance(data, target):
            # II. Fail invalid/unparseable types, or if base types don't match
            return False

        # II. Check structures
        if isinstance(data, tuple) and ktype and isinstance(ktype, tuple):
            # IV. Handle heterogenous tuple types
            return (len(data) == len(ktype)) and all(it.starmap(isinstance, zip(data, ktype)))
        elif ktype and vtype and (items := ut.map_items(data)):  #type: ignore
            # V. Handle maps
            keys, values = mi.unzip(items)
            return self.all_are(keys, ktype) and self.all_are(values, vtype)
        elif vtype and isinstance(data, Iterable):
            # VI. Handle all other iterables
            return self.all_are(data, vtype)

        return True

    def all_are(
        self,
        iterable: Iterable,
        tvar: type[T] | tuple[type[T], ...],
    ) -> TypeGuard[Iterable[T]]:
        """ Check if all values in an iterable match a type variable. """
        return all(self.check(value, tvar) for value in list(iterable))

    def any_are(self, iterable: Iterable, tvar: type[T]) -> TypeGuard[Iterable[T]]:
        """ Check if any value in an iterable matches a type variable. """
        return any(self.check(value, tvar) for value in list(iterable))

    @staticmethod
    def type_partition(container: Iterable, t0: type[C], t1: type[T]) -> tuple[list[C], list[T]]:
        return tuple( #  type:ignore
            map(list, mi.partition(lambda x: isinstance(x, type), container))
        )

    # -----------------------
    # Distilling and Merging
    # -----------------------
    def assemble(self, base: dict, *args: dict, copy: bool = True) -> dict:
        """
        Combines dictionaries, keeping the keys from the left-hand side and overwriting them
        with the values from the right-hand side.
        """
        if copy:
            base = deepcopy(base)
        # 0. Ensure that we have at least two dictionaries to merge
        if not args:
            return base
        other = args[0]

        # I. Partition fields on the second dict based on presence in the base
        unique, shared = mi.partition(lambda item: item[0] in base, other.items())

        # II. Unique fields overwrite completely
        base |= dict(unique)

        # III. Shared fields are recursively merged
        for key, value in shared:
            if self.match_instances(value, base[key]):
                tvar = type(value)
                if issubclass(tvar, dict):
                    base[key] = tvar(self.assemble(base[key], value, copy=False))
                    continue
                elif issubclass(tvar, Series):
                    base[key] = tvar(sorted(set(base[key] + value)))
                    continue
            base[key] = value

        # IV. Recursively merge other models into the result if present
        if len(args) > 1:
            return self.assemble(base, *args[1:], copy=False)
        return base

    def distill(self, models: list[dict], exclude: set[str] = set()) -> dict:
        """
        Finds and removes all the key/val pairs that are common to all the given models, returning them
        as a new partial model.
        """
        assert len(models) > 1, f'At least two models are required to distill, got {len(models)}.'

        base, *rest = models
        distillate: dict = {}
        for key in set(base.keys()):
            if key in exclude or not ut.all_has_all(rest, key):
                continue

            _type = type(base[key])
            restvals = [model[key] for model in rest]

            if set(map(type, filter(bool, restvals))) != {_type}:
                # I. Skip inconsistently-typed fields
                continue

            elif issubclass(_type, list | deque | set):
                # II. Handle series, removing the shared values
                if shared := set(filter(lambda item: ut.all_has_all(restvals, item), base[key])):
                    for model in models:
                        if model[key]:
                            model[key] = _type(it.filterfalse(shared.__contains__, model[key]))
                        if not model[key]:
                            del model[key]
                    distillate[key] = _type(sorted(set(distillate.get(key, [])) | shared))

            elif issubclass(_type, dict):
                # III. Recurse into maps
                if _ret := self.distill([base[key], *restvals], exclude=exclude):
                    distillate[key] = _ret
                    for model in models:
                        if not model[key]:
                            del model[key]

            elif issubclass(_type, Hashable) and set(restvals) == {base[key]}:
                # IV. Finally, handle atomic types by looking for a single shared value
                distillate[key] = base[key]
                for model in models:
                    del model[key]

        # V. If there's existing data, add it to the result before returning
        return distillate

    # --------------
    # Serializing Data
    # --------------
    def serialize(self, data: object, **kwargs) -> Any:
        """ Recursively transform the given object into serialization-ready, standardized types. """
        # I. Immediately return atomic values as-is
        if isinstance(data, Atomic):
            return data

        # II. Cast special types (times, enums, etc.) to strings
        elif isinstance(data, Enum | TimeType):
            return self._cast_to_atomic(data, str)

        # III. Look for familiar functions on models, else treat them as dictionaries
        if isinstance(data, pyd.BaseModel):
            cases = kwargs.get('cases', {})
            if handler := next((fn for k, fn in cases.items() if isinstance(data, k)), None):
                # II.i. If the caller specified a special handler, call that instead
                return handler(data)
            elif hasattr(data, 'serialize') and callable(data.serialize):
                # II.ii. Shortcut to a model-specific `serialize()` function
                return data.serialize()
            else:
                # II.iii. Rely on the model's serializers and treat the result as a dict
                if kwargs.get('_dump_all', False):
                    data = data.model_dump()
                else:
                    data = data.model_dump(
                        exclude_none=True, exclude_unset=True, exclude_defaults=True
                    )

        # IV. Handle collections by recursing over their elements
        if isinstance(data, Collection):
            _recur = ft.partial(self.serialize, **kwargs)
            if isinstance(data, Series):
                return list(map(_recur, data))
            elif isinstance(data, Mapping):
                return ut.val_map(_recur, data)

        return data

    def from_json(self, data: str | bytes | pyd.FilePath | None) -> dict:
        data = self._read_file(data)
        try:
            return json.loads(data) or {}
        except Exception:
            fire.error(f'Failed to parse JSON data: {data}')
            return {}

    def from_yaml(self, data: str | bytes | pyd.FilePath | None) -> dict:
        # I. Pre-parse data, extracting the text content of files
        data = self._read_file(data)
        # II. Strip yaml wrapping syntax if present
        if data.strip().startswith('```yaml'):
            data = '\n\n'.join(self.RGXS['yaml'].findall(data))

        # III. Attempt to parse the YAML data
        if data:
            try:
                return yaml.load(data, Loader=yaml.FullLoader)
            except Exception:
                pass
        return {}

    def to_yaml(
        self,
        data: Sequence | set | dict | pyd.BaseModel,
        fix: bool = True,
        wrap: bool = False,
    ) -> str:
        obj = self.serialize(data)
        text = yaml.dump(obj, sort_keys=False)
        # if fix:
        #     text = self.yamlfix(text, type(obj))
        if wrap:
            text = f'```yaml\n{text}\n```'
        return text

    # -------
    # Casting
    # -------
    def cast(self, data: object, tvar: type[Value]) -> Value | None:
        if data is None or tvar is None or not self._parseable(tvar):
            # 0. Return null if the target is invalid
            return None
        elif self.check(data, tvar):
            # I. Return the data as-is if it already matches the target type
            return data

        # II. Return a no-op for unparseable targets
        target, ktype, vtype = self.parse(tvar)
        if not target:
            return None

        # III. When given abstract classes, arbitrarily choose a concrete type
        elif target in [abc.Mapping, Mapping]:
            if isinstance(data, Mapping) and (_t := self.parse(type(data))[0]):
                target = _t
            else:
                target = dict
        elif target in [abc.Sequence, abc.Collection, Iterable, Sequence, Collection]:
            if isinstance(data, Collection) and (_t := self.parse(type(data))[0]):
                target = _t
            else:
                target = list

        # IV. Perform the actual casting
        ret = self._cast(data, target, ktype, vtype)
        return ret if isinstance(ret, target) else None  # type:ignore[return-value]

    def flexcast(self, data: object, tvar: TypeArg) -> Any | None:
        if data is None or tvar is None or not self._parseable(tvar):
            pass
        elif self._is_split(tvar):
            # I. If we're given options, choose the most appropriate one
            if args := tvar if isinstance(tvar, tuple) else getattr(tvar, '__args__', []):
                is_optional = None in args
                args = tuple(filter(self._parseable, args))
                origin = type(data)
                for option in sorted(args, key=lambda a: self._sorter(origin, a)):
                    try:
                        if (ret := self.cast(data, option)) is not None:
                            return ret
                    except Exception:
                        pass
                if is_optional:
                    return None
        elif (ret := self.cast(data, tvar)) is not None:  # type:ignore
            return ret

        return data

    def cast_all(self, values: Iterable[Any], tvar: type[Value]) -> Iterator[Value]:
        for value in values:
            if (result := self.cast(value, tvar)) is not None:
                yield result

    def flexcast_all(self, values: Iterable[Any], tvar: TypeArg) -> Iterator[Any]:
        for value in values:
            if (result := self.flexcast(value, tvar)) is not None:
                yield result

    def setattr(self, obj: pyd.BaseModel, key: str, value: Any, tvar: TypeArg = None) -> bool:
        """ Set an attribute on an object, casting it to the appropriate type if necessary. """
        # I. Infer the type to cast to, when possible
        if tvar is None:
            tvar = ut.instance_fields(type(obj)).get(key, None)

        # II. When we have a parseable type, cast the value before setting
        if tvar is not None and self._parseable(tvar):
            value = self.flexcast(value, tvar)
            if not self.check(value, tvar):
                fire.error(f'Cannot setattr {type(obj).__name__}.{value} by casting to {tvar}.')
                return False

        # III. Directly set the value attribute on the object
        setattr(obj, key, value)
        return True


Typist.setup()
typist = Typist(atomics=True, splits=True)


class AutocastModel(pyd.BaseModel):
    @pyd.model_validator(mode='before')
    @classmethod
    def _auto_validate(cls, data: dict) -> dict:
        return typist._cast_model_members(data.items(), cls)

    @pyd.model_serializer(mode='wrap')
    def _auto_serialize(self, handler) -> dict[str, Any]:
        """ Serialize the Issue instance to a dictionary. """
        return typist.serialize(handler(self))

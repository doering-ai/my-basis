############
### HEAD ###
############
### STANDARD
from typing import Any, ClassVar, Literal, TypeGuard, TypeVar, overload
import types
import typing
from collections.abc import (
    Collection,
    Callable,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
    Hashable,
)
from collections import Counter, deque
from copy import deepcopy
from datetime import date, datetime, time, timedelta, UTC
from enum import Enum, Flag
from pathlib import Path
import contextlib as ctx
import functools as ft
import inspect
import itertools as it
import more_itertools as mi
import pickle
import regex as re
import textwrap
import tomllib

### EXTERNAL
import dateutil.parser
import logfire as fire
import pydantic as pyd
import srsly
from srsly._yaml_api import CustomYaml
import tomli_w

### INTERNAL
from ..infra import T, C, Value, Series, Atomic, Time
from ..utils import ut
from ..caches import NestedCache
from .MyType import MyType

############
### DATA ###
############
# Type Aliases
TypeArg = type | tuple[type, ...] | None | MyType

# Misc aliases
File = pyd.FilePath
Directory = pyd.DirectoryPath

TupleType = TypeVar('TupleType', bound=tuple)
EnumType = TypeVar('EnumType', bound=Enum)
AtomicType = TypeVar('AtomicType', bound=Atomic)
TimeType = TypeVar('TimeType', bound=Time)
SeriesType = TypeVar('SeriesType', bound=Series)
MapType = TypeVar('MapType', bound=dict)
ClassType = TypeVar('ClassType')

FileParam = str | bytes | File | None
RawJsonData = str | int | float | bool | list | dict | None
FileData = Atomic | Series | dict | pyd.BaseModel
F = TypeVar('F', bound=FileData)
Ft = TypeVar('Ft', bound=type[F], default=type[dict])

ABSTRACT_MAPS = [typing.Mapping, Mapping]
ABSTRACT_SEQS = [
    typing.Iterable,
    typing.Sequence,
    typing.Collection,
    Iterable,
    Sequence,
    Collection,
]


############
### BODY ###
############
class Typist(pyd.BaseModel):
    """Semi-singleton interface for building systems that are resilient to slight inconsistencies.

    Specifically, this class provides runtime type introspection, parsing, and coercion capabilities
    that extend Python's static type hints into the runtime domain.

    This class was originally built as an extension of a Minksian Frame data structure, which needed
    to flexibly translate between untyped LLM outputs and strongly-typed in-memory data structures.
    It contains a large variety of functionality-for and examples-of working with types at runtime,
    but I suspect that this sort of **"Vibe Typing"** usecase will remain its shining capability.

    ```{tip}
    Typist is written as an instanced class only for situations where configuration differs across a
    single project. If that's not you, just use the global instance `typist`!
    ```


    ##### Parsing
    The features of Typist that most diverge from what's capable with the standard library rely
    on the `parse()` method, which decomposes a given type so that other methods can intelligently
    handly each part in turn. By far the most likely usecase is for containers such as
    `dict[str, int]` (which becomes the tuple `(dict, str, int)`) and `list[int]` (which becomes
    `(list, int, None)`), but it's useful for other generics, unions (e.g. `string | int`),
    and special non-type forms (e.g. `Annotated` and `Literal`).

    That said, not all possible type annotations are covered -- see the `Typist.SPECIAL_TYPES`
    attribute for a ~~complete~~ best-effort list of unhandled annotations.

    ##### Coercion
    The core functionality is **intelligent type coercion via `cast()` and `flexcast()`,**  which
    both try their absolute hardest to find a reasonable mapping between any two types. Obviously
    this is definitionally impossible to do perfectly for all possible types, but it has been tested
    extensively on the types that make up the vast majority of usecases (AI or otherwise):

    - Atomic types: `str`, `int`, `float`, and `bool`
    - Series: `list`, `tuple`, `set`, `deque`, etc.
    - Maps: `dict`, `Counter`, `Predicate`, etc.
    - Pydantic models: any subclass of `pyd.BaseModel`
    - Times: `datetime`, `date`, `time`, and `timedelta`
    - Enums: standard Python `Enum` types
    - And, most importantly: nested combinations of the above!

    Some of the decisions made within this class are arbitrary, but if the system is used
    consistently for both reading and writing, the implied instability/inconsistency can be
    minimized.

    ##### Comparison
    ###### Type Comparison ("matching")
    Type matching (mostly via `match()`) determines whether a value or type is a valid subset of
    another type. As opposed to the stdlib's `issubclass()`, Typist handles subtypes of generics
    recursively; for example, `dict[str, int]` matches `Mapping[str, int]` and
    `Collection[Sequence, int]`, but not `Mapping[str, str]` or `Collection[int]`.

    Matching results are cached using a `NestedCache` for performance.

    A small number of non-atomic yet common types are handled with custom logic:
    `tuple[int, str, float]` only matches another tuple with the same length and member types,
    whereas `tuple[int, ...]` matches any-length tuples of ints.

    ###### Object Comparison ("checking")
    Runtime data can be compared to other data using `match_instances()`, but obviously the primary
    usecase is to bring type-checking functionality into runtime in an ergonomic, idiomatic way.
    For this, Typist publishes `check()` for individual object/type pairs, and `all_are()` for
    asserting the types of the contents of containers.

    All of these methods use the TypeGuard protocol to enable type-narrowing in conditional
    statements, complementing static type-checkers like mypy or ty.

    ##### Transformation
    Typist provides more than just type coercion, which is ideally a minimally-semantic process.
    Namely, the `serialize()`, `assemble()` and `distill()` methods are built to flatten, combine
    together, and split apart complex nested data structures composed of sequences, mappings, and
    even Pydantic objects.

    ##### Persistence
    For reading and writing typed data to and from disk, Typist provides `to_file()` and
    `from_file()`. In just one short statement, users can interface with three file
    formats--**YAML, JSON, and Pickle**--using the very highly performant [`srsly`](https://github.com/explosion/srsly)
    library.

    ##### Invocation
    Finally, `invoke()` provides safe function calling with automatic type casting of arguments
    and return values. It inspects function signatures to determine expected types, casts provided
    arguments accordingly, and casts the return value to the annotated return type. This enables
    seamless integration of typed functions into dynamic workflows.
    """

    # Static Global Members
    ### Metatypes
    ATOMIC_TYPES: ClassVar[dict[str, type]] = dict(
        str=str,
        int=int,
        float=float,
        bool=bool,
        datetime=datetime,
        enum=Enum,
    )

    ### Regular Expressions (can't use RegexStore because it depends on this class)
    RGXS: ClassVar[dict[str, re.Pattern]] = ut.regex_dict(
        dict(
            # Types
            ### Atomic Types
            int=r'-?\d+',
            float=r'-?\d+(?:\.\d+)?',
            bool=r'(?i:t(?:rue)?|y(?:es)?|no?|f(?:alse)?|enabled?|disabled?|on|off|[01])',
            bool_true=r'(?i:t(?:rue)?|y(?:es)?|enabled?|on|1)',
            datetime=r'\d\d(?:\d\d)?[-./]\d\d[-./]\d\d(?:\D\d\d:\d\d:\d\d(?:\.\d+)?)?',
            enum=r'<(?P<class>[_[:upper:]]\w*)\.(?:\|?(?P<member>[_A-Z\d]+))+: (?P<value>.+)>',
            # Others
            splitter=r' *(?:[,]|\/\/) *',
            no_space_splitter=r'(?<=\w)[.:](?=\w)',
            yaml=r'(?sm)^```yaml *\n(?P<content>.+?)\n``` *$',
            timedelta=r'(?i)'
            + ut.multi_rgx(
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

    # YAML Config
    YAML_CONFIG: ClassVar[CustomYaml] = CustomYaml()
    RAISE: ClassVar[bool] = True

    # Dynamic Global Members
    MATCH_CACHE: ClassVar[NestedCache[tuple[str, str], bool]] = NestedCache(signature=(str, str))

    # Instance Members (for changing CASTING behavior only)
    atomics: bool = False
    firsts: bool = False
    splits: bool = False
    wraps: bool = False

    # -------------------
    # `.` Initial Methods
    # -------------------
    @classmethod
    def _setup(
        cls,
        mapping: int = 4,
        sequence: int = 6,
        offset: int = 4,
        sort_keys: bool = False,
    ) -> None:
        """Configure the YAML formatting library's defaults up front.

        See the [yaml docs](https://yaml.readthedocs.io/en/latest/detail.html?highlight=indentation#indentation-of-block-sequences)
        for guidance on the meaning of these parameters.

        All of these options can be overriden when calling `to_yaml()`.

        Args:
            mapping: Indentation delta between a parent mapping and its keys.
            sequence: Indentation delta between a parent sequence and a child sequence's contents.
            offset: Indentation delta between a parent and a child sequence's bullet points.
            sort_keys: Whether to sort mapping keys on output.
        """
        cls.YAML_CONFIG.indent(mapping=4, sequence=6, offset=4)
        cls.YAML_CONFIG.sort_base_mapping_type_on_output = sort_keys

    # -------------------
    # `-` Private Methods
    # -------------------
    @classmethod
    def sort_options(cls, data: object, *options: MyType) -> list[MyType]:
        """Sort type options by how well they fit the given data for coercion.

        Args:
            data: The source data to be cast.
            *options: Type options to sort by fitness.
        Returns:
            List of MyType options sorted by fitness score (best first).
        """
        return list(sorted(options, key=lambda opt: cls._score_option(data, opt), reverse=True))

    @classmethod
    def _score_option(cls, data: object, option: MyType) -> int:
        """Score how well a type option fits the given data for coercion.

        Args:
            data: The source data to be cast.
            option: The type option to score.
        Returns:
            Integer score where higher values indicate better fit.
        """
        if not option.main_type:
            return -10
        elif option.check(data):
            return 10
        elif option.is_split:
            return max(*(cls._score_option(data, subopt) for subopt in option.args))

        def check_both(tvar: type | types.UnionType) -> tuple[bool, bool]:
            return isinstance(data, tvar), issubclass(option.main_type or object, tvar)

        c0, c1 = check_both(Collection)

        score = 0
        if isinstance(data, option.main_type):
            score += 3
        else:
            a0, a1 = check_both(Atomic)
            if a0 and a1:
                score += 2
            elif a0 or a1 or c0 or c1:
                score -= 2

        if c0 and c1:
            score += 2
            m0, m1 = check_both(Mapping)
            s0, s1 = check_both(Series)
            if m1 and ((items := ut.map_items(data)) or m0):
                score += 2
                if option.key_type is None:
                    score += 1
                if option.val_type is None:
                    score += 1
                if items:
                    keys, vals = mi.unzip(items)
                    if cls.match(tuple(set(map(type, keys))), option.key_type):
                        score += 2
                    if cls.match(tuple(set(map(type, vals))), option.val_type):
                        score += 2
            elif s0 and s1:
                score += 2

                if option.val_type is None:
                    score += 1
                elif (
                    data
                    and isinstance(data, Iterable)
                    and cls.match(tuple(set(map(type, data))), option.val_type)
                ):
                    score += 2

        return score

    @staticmethod
    def _read_file(file: str | bytes | File | None) -> str:
        """Read a file and return its contents as a string."""
        if isinstance(file, bytes):
            return file.decode('utf-8')
        elif isinstance(file, Path):
            ut.validate_file(file)
            return file.read_text()
        elif not file:
            return ''
        else:
            return str(file)

    @classmethod
    def _derive_container(cls, old: MyType, new_origin: type[types.GenericAlias]) -> MyType:
        """Create a new container type based on an existing one with a different origin.

        Args:
            old: The original MyType to derive from.
            new_origin: The new origin type to use.
        Returns:
            New MyType with the new origin but preserving args from old.
        """
        if old.origin and old.args:
            assert hasattr(new_origin, '__class_getitem__'), (
                f'Type {new_origin} is not subscriptable'
            )
            new_src = new_origin[typing.Unpack[*tuple(arg.src_type for arg in old.args)]]
        else:
            new_src = new_origin

        return MyType.parse(new_src)

    @staticmethod
    def _clean_data(data: object) -> object | None:
        """Clean and normalize data for processing.

        Args:
            data: The data to clean.
        Returns:
            Cleaned data with iterators converted to lists and strings stripped.
        """
        if isinstance(data, Iterator):
            return list(data)
        elif isinstance(data, str):
            return data.strip()
        elif isinstance(data, bytes):
            return data.decode().strip()
        return data

    def _cast(self, data: object, target: MyType) -> Any | None:
        """Internal casting implementation that routes to specialized conversion methods.

        Args:
            data: The source data to cast.
            target: The target MyType to cast to.
        Returns:
            Cast data if successful, None otherwise.
        """
        data = self._clean_data(data)
        # I. Handle literals as a very special case
        if target.literal_check is not None:
            return self._to_literal(data, target)

        # II. Reject casts to unhandled or split types
        if (main := target.main_type) is None or target.is_split:
            return None

        # III. Handle all other data types in their own methods
        if issubclass(main, Atomic):
            return self._to_atomic(data, main)
        elif issubclass(main, Mapping):
            return self._to_map(data, main, target)
        elif issubclass(main, Series):
            return self._to_series(data, main, target)
        elif inspect.isclass(main):
            return self._to_class(data, main)
        else:
            fire.warning(f'Unknown main type for casting: {main}')
        return None

    def _to_literal(self, data: object, target: MyType) -> object | None:
        """Cast data to a literal type or literal tuple.

        Args:
            data: The source data to cast.
            target: The target literal MyType.
        Returns:
            Cast data if it matches the literal, None otherwise.
        """
        if target.literal_check is None or target.origin is None or data is None:
            return None

        if target.origin is Literal:
            # I. Cast Literals
            if any(val_type.check(data) for val_type in target.args):
                ret = data
            else:
                for val_type in target.args:
                    ret = self.cast(data, val_type)
                    if ret is not None and target.literal_check(ret):
                        return ret
        elif isinstance(target.origin, type) and issubclass(target.origin, tuple):
            # II. Cast literally-positioned tuples
            if not isinstance(data, Sequence):
                data = self._to_series(data, tuple)
            if data is not None and len(data) == len(target.args):
                ret = target.origin(it.starmap(self.cast, zip(data, target.args, strict=True)))

        return ret if target.literal_check(ret) else None

    def _to_atomic(self, data: object, target: type[AtomicType]) -> AtomicType | None:
        """Cast data to an atomic type (str, int, float, bool, Enum, or Time).

        Args:
            data: The source data to cast.
            target: The target atomic type.
        Returns:
            Cast atomic value if successful, None otherwise.
        """
        # 0. Take the first element of a series, if configured to
        if (
            isinstance(data, Series)
            and not issubclass(target, Flag)
            and ((self.firsts and len(data) > 0) or (self.atomics and len(data) == 1))
        ):
            data = mi.first(data)

        if issubclass(target, Enum):
            return self._to_enum(data, target)
        elif issubclass(target, Time):
            return self._to_time(data, target)
        elif isinstance(data, Enum):
            return self._enum_to_atomic(data, target)
        elif isinstance(data, Time):
            return self._time_to_atomic(data, target)
        elif isinstance(data, str):
            return self._str_to_atomic(data, target)
        elif issubclass(target, str) and (fn := self.get_str_method(data)):
            success, result = self.invoke(fn)
            if success:
                return result
        return None

    def _enum_to_atomic(self, data: Enum, target: type[AtomicType]) -> AtomicType | None:
        """Convert an Enum to an atomic type (str, int, float, bool, bytes).

        Args:
            data: The Enum value to convert.
            target: The target atomic type.
        Returns:
            Converted atomic value if successful, None otherwise.
        """
        if issubclass(target, str | bytes):
            if fn := self.get_str_method(data):
                ret = fn()
            elif isinstance(data.value, str):
                ret = data.value
            else:
                ret = data.name.lower()
            return ret if issubclass(target, str) else target(ret.encode())
        elif issubclass(target, int | float):
            if isinstance(data.value, int | float):
                return target(data.value)
        elif issubclass(target, bool):
            return target(data.value)

        return None

    def _time_to_atomic(self, data: Time, target: type[AtomicType]) -> AtomicType | None:
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
        assert isinstance(data, Time), f'Invalid time passed: {data}'

        if issubclass(target, str):
            # I. Cast to string
            if isinstance(data, datetime | date | time):
                return target(data.isoformat().split('+', 1)[0])
            else:
                return target(data)

        elif issubclass(target, bytes):
            # IV. Serialize to bytes
            if (res := self._time_to_atomic(data, str)) is not None:
                return target(res.encode())

        elif issubclass(target, int | float):
            # II. Cast to posix timestamps
            if isinstance(data, datetime):
                return target(data.timestamp())
            elif isinstance(data, date):
                return target(data.toordinal())
            elif isinstance(data, time):
                return target(60 * ((60 * data.hour) + data.minute) + data.second)
            else:
                return target(data.total_seconds())

        elif issubclass(target, bool):
            # III. Check for non-zero values
            if isinstance(data, datetime):
                return target(data.timestamp() > 0)
            if isinstance(data, date):
                return target(data.toordinal() > 0)
            elif isinstance(data, time):
                return target(data.hour > 0 or data.minute > 0 or data.second > 0)
            else:
                return target(data.total_seconds() > 0)

        return None

    def _str_to_atomic(self, data: str, target: type[AtomicType]) -> AtomicType | None:
        """Convert a string to an atomic type using regex pattern matching.

        Args:
            data: The string to convert.
            target: The target atomic type.
        Returns:
            Converted atomic value if pattern matches, None otherwise.
        """
        data = data.strip()
        if (issubclass(target, int) and self.RGXS['int'].fullmatch(data)) or (
            issubclass(target, float) and self.RGXS['float'].fullmatch(data)
        ):
            return target(data)
        elif issubclass(target, bool) and self.RGXS['bool'].fullmatch(data):
            return target(self.RGXS['bool_true'].fullmatch(data))
        elif issubclass(target, Time):
            return self._str_to_time(data, target)
        return None

    def _to_class(self, data: object, target: type[ClassType]) -> ClassType | None:
        """Cast data to a class instance using various instantiation strategies.

        Args:
            data: The source data to instantiate from.
            target: The target class type.
        Returns:
            Class instance if successful, None otherwise.
        """
        # I. First, try to use the semi-standard `new()` method if available
        if fn := self.get_method(target, 'new'):
            success, ret = self.invoke(fn, data)
            if success:
                return ret

        if items := ut.map_items(data):
            kwargs = self._cast_members(items, target)
            success, ret = self.invoke(target.__init__, **kwargs)
            if success:
                return ret

        success, ret = self.invoke(target.__init__, data)
        if success:
            return ret

        return None

    @staticmethod
    def _cast_members(items: Iterable[tuple[str, Any]], target: type) -> dict[str, Any]:
        """Cast a mapping's members to match a target class's field types.

        Args:
            items: Key-value pairs to cast.
            target: The target class type with type annotations.
        Returns:
            Dictionary with cast values matching target's field types.
        """
        annotations = ut.instance_aliases(target)
        return {key: typist.flexcast(val, annotations.get(key, None)) for key, val in items}

    def _to_enum(self, data: object, target: type[EnumType]) -> EnumType | None:
        """Cast data to an Enum or Flag type.

        Args:
            data: The source data (int, str, series, or another Enum).
            target: The target Enum or Flag type.
        Returns:
            Enum instance if successful, None otherwise.
        """
        # I. If the enum has it's own read method, try that first on any datatype
        success, res, _ = self.try_method(target, 'read', data)
        if success:
            return res

        if issubclass(target, Flag):
            # series_to_enum
            if isinstance(data, Series):
                members = data
            elif isinstance(data, str) and '|' in data:
                members = re.split(r' *\| *', data.strip())

            ret = target(0)
            for member in members:
                if res := self._to_enum(member, target):
                    ret |= res
            return ret
        elif isinstance(data, int):
            # int_to_enum
            return target(data)
        elif isinstance(data, str):
            data = data.strip()
            # str_to_enum
            if data.isdigit():
                return target(int(data))
            elif ret := target.__members__.get(data.upper(), None):
                return ret
        elif isinstance(data, Enum):
            if fn := self.get_method(target, 'read'):
                success, ret = self.invoke(fn, data.value)
                if success:
                    return ret
                success, ret = self.invoke(fn, data.name)
                if success:
                    return ret
            if data.name in target.__members__:
                return target[data.name]
            elif key := ut.find_key(target.__members__, data.value):
                return target[key]

        return None

    def _to_time(self, data: object, target: type[TimeType]) -> TimeType | None:
        """Convert a string or number to a datetime or timedelta object, if possible."""
        if not isinstance(data, Atomic):
            data = str(data)

        try:
            if isinstance(data, str):
                return self._str_to_time(data, target)
            elif isinstance(data, int | float):
                return self._num_to_time(data, target)
            elif isinstance(data, bool):
                return None
            elif isinstance(data, Enum):
                if (ret := self._to_time(data.value, target)) is not None:
                    return ret
                elif (ret := self._to_time(data.name, target)) is not None:
                    return ret
            elif isinstance(data, Time):
                if isinstance(data, datetime) and issubclass(target, time):
                    _raw = data.time().replace(tzinfo=UTC)
                    return target(
                        hour=_raw.hour,
                        minute=_raw.minute,
                        second=_raw.second,
                        microsecond=_raw.microsecond,
                        tzinfo=UTC,
                    )
        except ValueError as e:
            fire.error(f'Cannot cast from {type(data)} to time; {e}')
        return None

    def _str_to_time(self, data: str, target: type[TimeType]) -> TimeType | None:
        """Convert a string to a Time object using various parsing strategies.

        Args:
            data: The string to parse.
            target: The target Time type (datetime, date, time, or timedelta).
        Returns:
            Parsed Time object if successful, None otherwise.
        """
        data = data.strip()
        if data.isdigit():
            return self._to_time(int(data), target)
        elif Typist.RGXS['float'].fullmatch(data):
            return self._to_time(float(data), target)
        elif Typist.RGXS['short_iso_date'].match(data):
            data = f'20{data}'

        # I. Deserialize from iso timestamps (`yyyy-mm-dd` and/or `hh:mm:ss`)
        with ctx.suppress(ValueError):
            if issubclass(target, datetime):
                return target.fromisoformat(data).replace(tzinfo=UTC)
            elif issubclass(target, date):
                return target.fromisoformat(data)
            elif issubclass(target, time):
                return target.fromisoformat(data).replace(tzinfo=UTC)
            elif issubclass(target, timedelta):
                if matches := list(Typist.RGXS['timedelta'].finditer(data)):
                    return target(
                        **{
                            key: float(val)
                            for m in matches
                            for key, val in m.groupdict().items()
                            if val
                        }
                    )
        # II. Fall back to an external, flexible library
        if d := dateutil.parser.parse(data):
            d = d.replace(tzinfo=UTC)
            if issubclass(target, datetime):
                return target.fromtimestamp(d.timestamp(), tz=UTC)
            elif issubclass(target, date):
                return target.fromordinal(d.toordinal())
            elif issubclass(target, time):
                return
            elif issubclass(target, timedelta):
                return target(days=d.day, seconds=d.second, microseconds=d.microsecond)
        return None

    def _num_to_time(self, data: int | float, target: type[TimeType]) -> TimeType | None:
        """Convert a number to a Time object treating it as a timestamp or ordinal.

        Args:
            data: The numeric value to convert.
            target: The target Time type (datetime, date, time, or timedelta).
        Returns:
            Converted Time object if successful, None otherwise.
        """
        if issubclass(target, datetime):
            return target.fromtimestamp(data, tz=UTC)
        elif issubclass(target, date):
            return target.fromordinal(int(data))
        elif issubclass(target, time):
            total_seconds = int(data)
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            microseconds = int((data - total_seconds) * 1_000_000)
            return target(
                hour=hours % 24,
                minute=minutes % 60,
                second=seconds % 60,
                microsecond=microseconds,
                tzinfo=UTC,
            )
        elif issubclass(target, timedelta):
            return target(total_seconds=data)
        return None

    def _to_map(
        self, data: object, tvar: type[MapType], details: MyType | None = None
    ) -> MapType | None:
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
                data = self.from_yaml(data, tvar)

        # II. Main Case: cast maps and map-ready lists of 2-tuples ("items")
        if items := ut.map_items(data):
            keys, values = mi.unzip(items)
            key_data = self.multicast(keys, details.key_type, skip=False)
            val_data = self.multicast(values, details.val_type, skip=False)
            return tvar(zip(key_data, val_data, strict=True))

        # II. Cast counters, the only map type that takes an iter of single items
        if issubclass(tvar, Counter) and isinstance(data, Series) and details.key_type:
            key_data = self.multicast(data, details.key_type, skip=False)
            return tvar(key_data)

        return None

    def _to_series(
        self, data: object, tvar: type[SeriesType], details: MyType | None = None
    ) -> SeriesType | None:
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
        if isinstance(data, str) and self.splits:
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
            if data and isinstance(data, Series) and details.val_type:
                data = self.multicast(data, details.val_type, skip=False)
            return tvar(data)
        return None

    def _split_str(self, data: str) -> list[str] | None:
        """Split a string into a list using various delimiters.

        Args:
            data: The string to split.
        Returns:
            List of split strings if delimiters found, None otherwise.
        """
        # I. Null/invalid cases
        if not data:
            return None
        elif (data[0] == '[' and data[-1] == ']') or ', ' in data:
            # II. Split yaml-like flow sequences
            with ctx.suppress(Exception):
                return self.from_yaml(data, list[str], cast=False)
        elif char := next(filter(data.__contains__, [',', '//', ':', '.']), ''):
            # III. Split on common delimiters in order of preference
            #       e.g. one.oneA:two splits on colons, but one.oneA splits on periods
            return list(filter(bool, map(str.strip, data.split(char))))

        return None

    @staticmethod
    def type_partition(container: Iterable, t0: type[C], t1: type[T]) -> tuple[list[C], list[T]]:
        """Partition a container into two lists based on type.

        Args:
            container: The iterable to partition.
            t0: First type (for type objects).
            t1: Second type (for non-type objects).
        Returns:
            Tuple of two lists: (type objects, non-type objects).
        """
        return tuple(map(list, mi.partition(lambda x: isinstance(x, type), container)))

    @classmethod
    def _concretize(cls, target: MyType, main: type, data: object) -> tuple[MyType, type]:
        """Convert abstract container types to concrete ones based on data.

        Args:
            target: The target MyType.
            main: The main type from target.
            data: The source data to inform concretization.
        Returns:
            Tuple of (potentially modified MyType, potentially modified main type).
        """
        orig = target, main
        new_main = None
        if main in ABSTRACT_MAPS:
            if isinstance(data, Mapping) and (_dt := MyType.parse(type(data))):
                new_main = _dt.main_type
            else:
                new_main = dict
        elif main in ABSTRACT_SEQS:
            if isinstance(data, Series) and (_dt := MyType.parse(type(data))):
                new_main = _dt.main_type
            else:
                new_main = list

        if new_main is not None:
            assert isinstance(new_main, types.GenericAlias)
            return cls._derive_container(target, new_main), new_main
        return orig

    @classmethod
    def _param_is_positional(cls, param: inspect.Parameter) -> bool:
        """Check if a parameter can accept positional arguments.

        Args:
            param: The parameter to check.
        Returns:
            True if the parameter accepts positional arguments.
        """
        return param.kind in {
            param.POSITIONAL_ONLY,
            param.POSITIONAL_OR_KEYWORD,
            param.VAR_POSITIONAL,
        }

    @classmethod
    def _param_is_keyword(cls, param: inspect.Parameter) -> bool:
        """Check if a parameter can accept keyword arguments.

        Args:
            param: The parameter to check.
        Returns:
            True if the parameter accepts keyword arguments.
        """
        return param.kind in {
            param.KEYWORD_ONLY,
            param.POSITIONAL_OR_KEYWORD,
            param.VAR_KEYWORD,
        }

    @classmethod
    def _match_literals(cls, t0: MyType, t1: MyType, intersect: bool) -> bool:
        """Check if two literal types match according to subset or intersection logic.

        Args:
            t0: First MyType with literal members.
            t1: Second MyType with literal members.
            intersect: If True, check for intersection; if False, check for subset.
        Returns:
            True if types match according to the specified logic.
        """
        # 0. Setup
        lit0, lit1 = t0.literal_members, t1.literal_members
        o0, o1 = t0.origin, t1.origin

        _recur = ft.partial(cls.match, intersect=intersect)

        if lit0 and lit1:
            assert o0 and o1, "Found literal without an origin, which doesn't make sense."
            if o0 is Literal and o1 is Literal:
                # I.i. Two literals are basically the same as container types, just with objects
                fn = ut.has_any if intersect else ut.has_all
                return fn(t1.literal_members, *t0.literal_members)

            elif issubclass(o0, o1) and issubclass(o1, tuple):
                # I.ii. Two positional tuples must always match exactly
                return len(t0.args) == len(t1.args) and all(
                    it.starmap(_recur, zip(t0.args, t1.args, strict=True))
                )
        elif lit0 and (m1 := t1.main_type):
            assert o0, "Found literal without an origin, which doesn't make sense."
            if o0 is Literal:
                # II.i. A literal can be a subset of an atomic type(s)
                fn = any if intersect else all
                return fn(_recur(arg, t1) for arg in t0.args)
            elif issubclass(o0, m1) and issubclass(m1, tuple):
                if len(t1.args) == 0:
                    # II.ii. Any positional tuple is a subset of its plain base
                    return True
                elif t1.val_type:
                    # II.iii. Theoretically, a positional tuple could a subset of a typed tuple
                    #         e.g. tuple[int, str] x tuple[object, ...]
                    return all(_recur(arg, t1.val_type) for arg in t0.args)

        elif lit1 and intersect and t0.main_type:
            # III. Just recurse w/ flipped arguments for DRY reasons
            return cls._match_literals(t1, t0, intersect=False)

        return False

    # -------------------
    # `+` Primary Methods
    # -------------------

    def __repr__(self) -> str:
        return 'Typist'

    # ------------------
    # `*` Public Methods
    # ------------------
    @staticmethod
    def parse(tvar: Any) -> MyType:
        """Parse a type annotation into a MyType instance. See `MyType.parse()` for details."""
        return MyType.parse(tvar)

    # ---------------
    # `*1` COMPARISON
    # ---------------
    def check[T](self, data: object, tvar: type[T]) -> TypeGuard[T]:
        """Check if a data matches a type variable. See `MyType.check()` for details."""
        return MyType.parse(tvar).check(data)

    def all_are[T](self, iterable: Iterable, tvar: type[T]) -> TypeGuard[Iterable[T]]:
        """Check if all values in an iterable match a type variable."""
        return all(self.check(value, tvar) for value in list(iterable))

    def any_are[E, T](self, iterable: Iterable[E], tvar: type[T]) -> TypeGuard[Iterable[E | T]]:
        """Check if any value in an iterable matches a type variable."""
        return any(self.check(value, tvar) for value in list(iterable))

    @classmethod
    def match(cls, lhs: TypeArg, rhs: TypeArg, intersect: bool = False) -> bool:
        """Check if the first type is valid subset of the second.

        Args:
            lhs: The source type.
            rhs: The target type.
            intersect: If `True`, check for any overlap between the two types
                       rather than full subset coverage.
        """
        # I.i. Any & None (i.e. unspecified) are always true, but unhandled MyTypes are always false
        if {lhs, rhs} & {Any, None}:
            return True
        elif not (lhs and rhs):
            return False

        # II. Check cache based on simple stringification
        n0 = str(lhs.src_type if isinstance(lhs, MyType) else lhs)
        n1 = str(rhs.src_type if isinstance(rhs, MyType) else rhs)
        if intersect:
            n1 += '.I'
        if (cached := cls.MATCH_CACHE[n0, n1]) is not None:
            return cached

        # III. Parse the types (if they're already parsed, no work is done)
        t0 = MyType.parse(lhs)
        t1 = MyType.parse(rhs)

        ret = False
        _recur = ft.partial(cls.match, intersect=intersect)
        if t0.literal_members or t1.literal_members:
            # II. Literal case
            ret = cls._match_literals(t0, t1, intersect)
        elif not (mt0 := t0.main_type) or not (mt1 := t1.main_type):
            # II. Unhandled case
            ret = False
        elif t0.is_split or t1.is_split:
            # III. Unions case
            lhs_options = t0.args if t0.is_split else [t0]
            rhs_options = t1.args if t1.is_split else [t1]
            fn = any if intersect else all
            ret = fn(any(_recur(lo, ro) for ro in rhs_options) for lo in lhs_options)
        else:
            # IV. Main case: check for simple subclass coverage for the main type and any children
            ret = issubclass(mt0, mt1) or (issubclass(mt1, mt0) if intersect else False)
            if ret and t0.key_type and t1.key_type:
                ret &= _recur(t0.key_type, t1.key_type)
            if ret and t0.val_type and t1.val_type:
                ret &= _recur(t0.val_type, t1.val_type)

        # Cache & return
        cls.MATCH_CACHE[n0, n1] = ret
        return ret

    def match_instances(self, lhs: object, rhs: object, intersect: bool = False) -> bool:
        """Check if two instances have matching types.

        Args:
            lhs: First instance.
            rhs: Second instance.
            intersect: If True, check for intersection; if False, check for subset.
        Returns:
            True if the instances' types match.
        """
        t0 = MyType.metaparse(lhs)
        t1 = MyType.metaparse(rhs)
        return self.match(t0, t1, intersect)

    def seek_usage(self, lhs: TypeArg, rhs: type | MyType) -> bool:
        """Check if a type is used anywhere within another type's structure.

        Args:
            lhs: The type to search for.
            rhs: The type to search within.
        Returns:
            True if lhs is used within rhs's type structure.
        """
        t0 = MyType.parse(lhs)
        t1 = MyType.parse(rhs)
        if self.match(t0, t1, intersect=True):
            return True

        if inspect.isclass(rhs):
            # III.ii.a.
            return any(self.seek_usage(t0, ann) for ann in ut.instance_fields(rhs).values())
        elif t1.val_type:
            # III.ii.b. Recurse into container values
            return self.seek_usage(t0, t1.val_type)
        return False

    # -------------
    # `*2` COERCION
    # -------------
    @overload
    def cast(self, data: object, tvar: type[Value]) -> Value | None: ...

    @overload
    def cast(self, data: object, tvar: Any) -> Any | None: ...

    def cast(self, data: object, tvar: type[Value] | Any) -> Value | Any | None:
        """Attempt to cast/coerce the  data to the given type, returning None if unsuccessful."""
        # I. Return null if the target is invalid
        if data is None or tvar in {None, Any}:
            return None
        target = MyType.parse(tvar)
        if (main := target.main_type) is None:
            return None

        # II. Return the data as-is if it already matches the target type
        data = self._clean_data(data)
        if target.check(data):
            return data

        # III. When given abstract classes, arbitrarily choose a concrete type
        target, main = self._concretize(target, main, data)

        # IV. Perform the actual casting
        options = self.sort_options(data, *target.args) if target.is_split else [target]
        for option in options:
            if (ret := self._cast(data, option)) is not None:
                return ret
        return None

    def flexcast(self, data: object, tvar: TypeArg) -> Any | None:
        """Cast data to a type, returning original data on failure.

        Args:
            data: The source data to cast.
            tvar: The target type.
        Returns:
            Cast data if successful, original data otherwise.
        """
        res = self.cast(data, tvar)
        return res if res is not None else data

    def multicast(
        self, values: Iterable[Any], tvar: type[Value] | Any, skip: bool = False
    ) -> list[Value] | list:
        """Cast multiple values to a target type.

        Args:
            values: Iterable of values to cast.
            tvar: The target type to cast to.
            skip: If True, skip failed casts; if False, raise TypeError on failure.
        Returns:
            List of cast values (or original values if skip=True).
        """
        # I. Parse the type once
        target = MyType.parse(tvar)

        # II. Cast the contents iteratively, either skipping failures or throwing TypeError
        ret = []
        for value in values:
            if value is None:
                ret.append(None)
            elif (result := self.cast(value, target)) is not None:
                ret.append(result)
            elif skip:
                continue
            else:
                raise TypeError(f'Cannot cast value `{value}` to type `{tvar}`.')
        return ret

    def flex_deserialize(self, values: Sequence[str] | str) -> list[Atomic]:
        """Convert a list of strings to their most appropriate `Atomic` type."""
        values = [values] if isinstance(values, str) else list(values)
        typing.cast('list[str]', values)
        new_types = [
            next(
                (
                    _type
                    for name, _type in self.ATOMIC_TYPES.items()
                    if name in self.RGXS and self.RGXS[name].fullmatch(val)
                ),
                str,
            )
            for val in values
        ]
        return [  #  type:ignore
            (val if tvar is str else self._to_atomic(val, tvar))
            for val, tvar in zip(values, new_types, strict=True)
        ]

    def setattr(self, obj: object, key: str, value: Any, tvar: TypeArg = None) -> bool:
        """Set an attribute on an object, casting the value to the appropriate type.

        Args:
            obj: The object to set the attribute on.
            key: The attribute name.
            value: The value to set (will be cast if needed).
            tvar: Optional explicit type to cast to (inferred from obj if None).
        Returns:
            True if successful, False if casting failed.
        """
        # I. Infer the type to cast to, when possible
        if tvar is None:
            tvar = ut.instance_fields(type(obj)).get(key, None)

        # II. When we have a parseable type, cast the value before setting
        if value is not None and (target := MyType.parse(tvar)):
            if (cast_value := self.cast(value, target)) is not None:
                value = cast_value
            else:
                fire.error(f'Cannot setattr {type(obj).__name__}.{key} by casting to {tvar}.')
                return False

        # III. Directly set the value attribute on the object
        setattr(obj, key, value)
        return True

    def cast_file_data(self, data: RawJsonData, tvar: type[F]) -> F:
        """Cast raw file data (JSON/YAML) to a specific type with smart conversions.

        Args:
            data: Raw data from file (str, int, float, bool, list, dict, or None).
            tvar: The target type to cast to.
        Returns:
            Cast data of the target type.
        Raises:
            TypeError: If casting fails.
        """
        # I. Edge Cases
        if isinstance(data, tvar):
            return data
        elif issubclass(type(data), tvar):
            return tvar(data)
        elif not data:
            return tvar()

        # II. Casting from atomics
        if isinstance(data, Atomic):
            if issubclass(tvar, Series):
                return tvar([data])
            elif issubclass(tvar, Mapping):
                return tvar({'content': data})

        # III. Catching mistmatched collections
        elif isinstance(data, dict) and issubclass(tvar, Series):
            if len(data) == 1 and isinstance((first := mi.first(data.values())), Series):
                return tvar(first)
            else:
                return tvar([data])
        elif isinstance(data, list) and issubclass(tvar, Mapping):
            if len(data) == 1 and isinstance((first := mi.first(data)), Mapping):
                return tvar(first)
            else:
                return tvar({'content': data})

        # IV. Main case: give it to _cast and pray
        if (ret := self.cast(data, MyType.parse(tvar))) is not None:
            return ret
        raise TypeError(f'Cannot cast file data of type `{type(data)}` to `{tvar}`.')

    # -------------------
    # `*3` TRANSFORMATION
    # -------------------
    def serialize(
        self,
        data: object,
        cases: dict[type | Callable[[object], bool], Callable[[object], Any]] | None = None,
        full: bool = False,
    ) -> Any:
        """Recursively transform the given object into serialization-ready, standardized types."""
        # I. Immediately return atomic values as-is
        if isinstance(data, Atomic):
            return data

        # II. Cast special types (times, enums, etc.) to strings
        elif isinstance(data, Enum | Time):
            return self._to_atomic(data, str)

        # III. Look for familiar functions on models, else treat them as dictionaries
        if isinstance(data, pyd.BaseModel):
            if cases:
                # II.i. If the caller specified a special handler, call that instead
                for case, handler in cases.items():
                    if (isinstance(case, type) and isinstance(data, case)) or case(data):
                        return handler(data)

            if fn := self.get_method(data, 'serialize'):
                # II.ii. Shortcut to a model-specific `serialize()` function
                return fn()

            # II.iii. Rely on the model's serializers and treat the result as a dict
            data = (
                data.model_dump()
                if full
                else data.model_dump(exclude_unset=True, exclude_defaults=True)
            )

        # IV. Handle collections by recursing over their elements
        if isinstance(data, Collection):
            _recur = ft.partial(self.serialize, cases=cases, full=full)
            if isinstance(data, Series):
                return list(map(_recur, data))
            elif isinstance(data, Mapping):
                return ut.val_map(_recur, data)

        return data

    def assemble(
        self,
        base: dict,
        *args: dict,
        copy: bool = True,
        sort: bool = True,
        dups: bool = False,
    ) -> dict:
        """Combine dictionaries, recursively merging nested structures wherever possible.

        Args:
            base: The base dictionary to merge into.
            *args: Additional dictionaries to merge in order.
            copy: If True, make a deep copy of the base before merging.
            sort: If True, sort lists after merging.
            dups: If False, remove duplicates from lists after merging.
        Return:
            Merged dictionary.
        """
        if base is None:
            base = {}
        elif copy:
            base = deepcopy(base)

        # 0. Ensure that we have at least two dictionaries to merge
        _args = list(filter(bool, args))
        if not _args:
            return base
        other, *rest = _args

        # I. Partition fields on the second dict based on presence in the base
        unique, shared = mi.partition(lambda item: item[0] in base, other.items())

        # II. Unique fields overwrite completely
        base |= dict(unique)

        # III. Shared fields are recursively merged if possible, otherwise overwritten
        for key, new in shared:
            old = base[key]
            if self.all_are([old, new], Collection):
                # _cast = self.cast(new, MyType.metaparse(old))
                tvar = type(old)
                if (_cast := self.cast(new, tvar)) is None:
                    pass  # Fall through to overwrite
                elif isinstance(old, dict):
                    base[key] = tvar(self.assemble(old, _cast, copy=False))
                    continue
                elif issubclass(tvar, set):
                    old.update(tvar(new))
                    continue
                elif issubclass(tvar, Sequence):
                    old.extend(new)
                    if not dups:
                        base[key] = old = tvar(mi.unique_everseen(old))
                    if sort:
                        old.sort()
                    continue
            base[key] = new

        # IV. Recursively merge other models into the result if present
        if rest:
            return self.assemble(base, *rest, copy=False)
        return base

    def distill(self, models: list[dict], exclude: set[str] | None = None) -> dict:
        """Recursively extract common fields from multiple models; the inverse of `assemble()`.

        Args:
            models: List of dictionaries to distill.
            exclude: Set of field names to exclude from distillation (used during recursion).
        Returns:
            Distilled dictionary of shared fields.
        """
        assert len(models) > 1, f'At least two models are required to distill, got {len(models)}.'

        base, *rest = models
        distillate: dict = {}
        for key in set(base.keys()):
            if (exclude and key in exclude) or not ut.all_has_all(rest, key):
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

    # ----------------
    # `*4` PERSISTENCE
    # ----------------
    @overload
    def from_file(self, file: str | Path) -> dict: ...

    @overload
    def from_file(self, file: str | Path, tvar: type[F], cast: bool = True) -> F: ...

    def from_file(
        self,
        file: str | Path,
        tvar: type[F] = dict,  # ty:ignore[invalid-parameter-default]
        cast: bool = True,
    ) -> F:
        """Load data from local JSON, YAML, TOML, or Pickle file, then cast to target type.

        In order to cast between the by-far two most common expected types--dict and list--Typist
        will wrap uncastable values in a dict (w/ one key, `'content'`) or a list (w/ one value).

        Args:
            file: Path to the file to load. Note that raw strings are NOT allowed here.
            tvar: Target type to cast the loaded data to (dict by default). Like `cast()`, you
                  can use complex, nested types here if desired.
            cast: If False, data that doesn't match the expected return type raises an error.
        Returns:
            Loaded and cast data from the file.
        """
        if not file:
            fire.error('No file provided.')
            return tvar()
        elif not isinstance(file, Path):
            file = Path(str(file)).expanduser()
        ut.validate_file(file)

        if file.suffix in ['.yml', '.yaml']:
            return self.from_yaml(file, tvar, cast)
        elif file.suffix in ['.json']:
            return self.from_json(file, tvar, cast)
        elif file.suffix in ['.tml', '.toml']:
            return self.from_toml(file, tvar, cast)
        elif file.suffix in ['.pkl']:
            return self.from_pickle(file, tvar, cast)
        else:
            raise ValueError(f'Unsupported file type: {file}')

    @overload
    def from_json(self, file: FileParam) -> dict: ...

    @overload
    def from_json(self, file: FileParam, tvar: type[F], cast: bool = True) -> F: ...

    def from_json(
        self,
        file: FileParam,
        tvar: type[F] = dict,  # ty:ignore[invalid-parameter-default]
        cast: bool = True,
    ):
        """Load data from JSON file or string, then cast to target type. See `from_file()`.

        Args:
            file: Path to the file to load, or raw JSON string/bytes.
            tvar: Target type to cast the loaded data to (dict by default). Like `cast()`, you
                  can use complex, nested types here if desired.
            cast: If False, data that doesn't match the expected return type raises an error.
        Returns:
            Loaded and cast data from the file/string.
        """
        if not file:
            return tvar()
        elif isinstance(file, Path):
            ut.validate_file(file)
            ret = srsly.read_json(file)
        else:
            if isinstance(file, bytes):
                file = file.decode()
            ret = srsly.json_loads(file)

        if isinstance(ret, tvar):
            return ret
        elif cast:
            return tvar(ret)
        else:
            raise TypeError(f'Expected `{tvar}`, got `{type(ret)}`.')

    @overload
    def from_yaml(self, file: FileParam) -> dict: ...

    @overload
    def from_yaml(self, file: FileParam, tvar: type[F], cast: bool = True) -> F: ...

    def from_yaml(
        self,
        file: FileParam,
        tvar: type[F] = dict,  # ty:ignore[invalid-parameter-default]
        cast: bool = True,
    ) -> F:
        """Load data from YAML file or string, then cast to target type. See `from_file()`.

        Args:
            file: Path to the file to load, or raw YAML string/bytes.
            tvar: Target type to cast the loaded data to (dict by default). Like `cast()`, you
                  can use complex, nested types here if desired.
            cast: If False, data that doesn't match the expected return type raises an error.
        Returns:
            Loaded and cast data from the file/string.
        """
        if not file:
            return tvar()
        elif isinstance(file, Path):
            ut.validate_file(file)
            ret = srsly.read_yaml(file)
        else:
            if isinstance(file, bytes):
                file = file.decode()
            if file.strip().startswith('```yaml'):
                file = '\n\n'.join(self.RGXS['yaml'].findall(file))

            # Attempt to parse in-memory YAML strings
            ret = srsly.yaml_loads(file)

        if isinstance(ret, tvar):
            return ret
        elif cast:
            return tvar(ret)
        else:
            raise TypeError(f'Expected `{tvar}`, got `{type(ret)}`.')

    @overload
    def from_toml(self, file: FileParam) -> dict: ...

    @overload
    def from_toml(self, file: FileParam, tvar: type[F], cast: bool = True) -> F: ...

    def from_toml(
        self,
        file: FileParam,
        tvar: type[F] = type[dict],  # ty:ignore[invalid-parameter-default]
        cast: bool = True,
    ) -> F:
        """Load data from TOML file or string, then cast to target type. See `from_file()`.

        Args:
            file: Path to the file to load, or raw TOML string/bytes.
            tvar: Target type to cast the loaded data to (dict by default). Like `cast()`, you
                  can use complex, nested types here if desired.
            cast: If False, data that doesn't match the expected return type raises an error.
        Returns:
            Loaded and cast data from the file/string.
        """
        if not file:
            return tvar()
        elif isinstance(file, Path):
            ret = tomllib.loads(file.read_text())
        else:
            if isinstance(file, bytes):
                file = file.decode()
            ret = tomllib.loads(file)

        if isinstance(ret, tvar):
            return ret
        elif cast:
            return tvar(ret)
        else:
            raise TypeError(f'Expected `{tvar}`, got `{type(ret)}`.')

    @overload
    def from_pickle(self, file: FileParam) -> dict: ...

    @overload
    def from_pickle(self, file: FileParam, tvar: type[F], cast: bool = True) -> F: ...

    def from_pickle(
        self,
        file: FileParam,
        tvar: type[F] = type[dict],  # ty:ignore[invalid-parameter-default]
        cast: bool = True,
    ) -> F:
        """Load data from Pickle file or bytes, then cast to target type. See `from_file()`.

        Args:
            file: Path to the file to load, or raw Pickle bytes/string.
            tvar: Target type to cast the loaded data to (dict by default). Like `cast()`, you
                  can use complex, nested types here if desired.
            cast: If False, data that doesn't match the expected return type raises an error.
        Returns:
            Loaded and cast data from the file/string.
        """
        if not file:
            return tvar()
        elif isinstance(file, Path):
            ret = pickle.loads(file.read_bytes())
        else:
            if isinstance(file, str):
                file = file.encode()
            ret = pickle.loads(file)

        if isinstance(ret, tvar):
            return ret
        elif cast:
            return tvar(ret)
        else:
            raise TypeError(f'Expected `{tvar}`, got `{type(ret)}`.')

    def to_file(self, data: FileData, file: str | File) -> None:
        """Save data to local JSON, YAML, TOML, or Pickle file (depending on file suffix).

        Args:
            data: The data to save.
            file: Path to the file to save. Note that raw strings are NOT allowed here.
        """
        if not file:
            return
        elif not isinstance(file, Path):
            file = Path(str(file)).expanduser()

        file.parent.mkdir(parents=True, exist_ok=True)
        if file.suffix in ['.yml', '.yaml']:
            file.write_text(self.to_yaml(data))
        elif file.suffix in ['.json']:
            file.write_text(self.to_json(data))
        elif file.suffix in ['.tml', '.toml']:
            file.write_text(self.to_toml(data))
        elif file.suffix in ['.pkl']:
            file.write_bytes(self.to_pickle(data))
        else:
            fire.error(f'Unsupported file type: {file}')

    def to_yaml(self, data: FileData, wrap: bool = False, **kwargs) -> str:
        """Serialize data to a YAML string. See `to_file()` for general details.

        Args:
            data: The data to serialize.
            wrap: If True, wrap the output in markdown backticks for YAML.
            **kwargs: Additional keyword arguments to pass to `srsly.yaml_dumps()`.
        Returns:
            YAML string representation of the data.
        """
        obj = self.serialize(data)
        text = self.YAML_CONFIG.dump(obj, **kwargs)

        # If we printed a root array, de-intent it
        if isinstance(data, Series) and text.startswith(' '):
            text = textwrap.dedent(text)

        # If requested, wrap in markdown bactics
        if wrap:
            text = f'```yaml\n{text}\n```'
        return text

    def to_json(self, data: FileData, wrap: bool = False, **kwargs) -> str:
        """Serialize data to a JSON string. See `to_file()` for general details.

        Args:
            data: The data to serialize.
            wrap: If True, wrap the output in markdown backticks for JSON.
            **kwargs: Additional keyword arguments to pass to `srsly.json_dumps()`.
        Returns:
            JSON string representation of the data.
        """
        obj = self.serialize(data)
        if 'indent' not in kwargs:
            kwargs['indent'] = 4
        text = srsly.json_dumps(obj, **kwargs)

        # If requested, wrap in markdown bactics
        if wrap:
            text = f'```json\n{text}\n```'
        return text

    def to_toml(self, data: FileData, wrap: bool = False, **kwargs) -> str:
        """Serialize data to a TOML string. See `to_file()` for general details.

        Args:
            data: The data to serialize.
            wrap: If True, wrap the output in markdown backticks for TOML.
            **kwargs: Additional keyword arguments to pass to `tomli_w.dumps()`.
        Returns:
            TOML string representation of the data.
        """
        obj = self.serialize(data)

        # Cast to dict, as toml only accepts dicts at the top level
        if not isinstance(obj, dict):
            if (
                isinstance(obj, Series)
                and len(obj) == 1
                and isinstance((_obj := mi.first(obj)), dict)
            ):
                obj = _obj
            else:
                obj = dict(content=obj)

        # II. Serialize w/ default params
        text = tomli_w.dumps(obj, **kwargs)
        return text

    def to_pickle(self, data: FileData, **kwargs) -> bytes:
        """Serialize data to Pickle bytes. See `to_file()` for general details.

        Args:
            data: The data to serialize.
            **kwargs: Additional keyword arguments to pass to `pickle.dumps()`.
        Returns:
            Pickle byte representation of the data.
        """
        obj = self.serialize(data)
        return pickle.dumps(obj, **kwargs)

    # ---------------
    # `*5` INVOCATION
    # ---------------
    def try_method(self, obj: object, methods: str, *args, **kwargs) -> tuple[bool, Any, Callable]:
        """A thin wrapper that calls `get_method()`, then `invoke()` if successful."""
        if fn := self.get_method(obj, methods):
            success, result = self.invoke(fn, *args, **kwargs)
            return success, result, fn
        return False, None, lambda *a, **k: None

    def get_str_method(self, obj: object, *extra_methods: str) -> Callable | None:
        """Get a string conversion method from an object.

        Args:
            obj: The object to search for string methods.
            *extra_methods: Additional method names to check before standard ones.
        Returns:
            First found string conversion method, or None if none found.
        """
        return self.get_method(obj, *extra_methods, 'write', 'to_string', '__str__')

    def get_method(self, obj: object, *methods: str) -> Callable | None:
        """Get the first available method from an object by name.

        Args:
            obj: The object to search for methods.
            *methods: Method names to search for in order.
        Returns:
            First found callable method, or None if none found.
        """
        for method in methods:
            if (fn := getattr(obj, method, None)) is not None and callable(fn):
                return fn
        return None

    @classmethod
    def invocable(
        cls, sig: Callable | inspect.Signature, *args: object, **kwargs: object
    ) -> None | inspect.BoundArguments:
        """Check if a function can be called with the given arguments.

        This method validates that the provided arguments can be bound to the function's
        signature and optionally performs type checking on the arguments.

        Args:
            sig: The function or signature to inspect.
            *args: Positional arguments to validate.
            **kwargs: Keyword arguments to validate.

        Returns:
            A tuple of (args, kwargs) that can be used to call the function if binding succeeds,
            or None if the function cannot be called with the given arguments.
        """
        # I. Coerce to signature if needed
        if not isinstance(sig, inspect.Signature):
            assert callable(sig), f'Invalid function provided: {sig}'
            sig = inspect.signature(sig)
        params = list(sig.parameters.values())

        # II.i. Naive attempt
        with ctx.suppress(TypeError):
            bound = sig.bind(*args, **kwargs)
            return bound

        # II.ii. Unpacked attempt
        if len(args) == 1:
            if any(map(cls._param_is_keyword, params)) and (items := ut.map_items(args[0])):
                kwargs = dict(items) | kwargs
            elif isinstance(args[0], Series):
                args = tuple(args[0])
            else:
                return None
            with ctx.suppress(TypeError):
                bound = sig.bind(*args, **kwargs)
                return bound

        # II.iii. Packed attempt
        if len(kwargs) > 0 and any(
            cls.match(param.annotation, Mapping)
            for param in filter(cls._param_is_positional, params)
        ):
            with ctx.suppress(TypeError):
                bound = sig.bind(*args, kwargs)
                return bound
        return None

        # III. Perform type checking on the bound arguments
        # for param_name, param in sig.parameters.items():
        #     if param.annotation is not inspect.Parameter.empty:
        #         value = bound.arguments.get(param_name)
        #         # Skip type checking for None values and varargs/varkwargs
        #         if param.kind in {param.VAR_POSITIONAL, param.VAR_KEYWORD}:
        #             continue
        #         if value is not None and not self.check(value, param.annotation):
        #             return None
        # IV. Return the original arguments (they passed validation)
        # return bound.args, bound.kwargs

    @classmethod
    def invoke(
        cls, func: Callable[[...], T] | None, *args: object, **kwargs: object
    ) -> tuple[bool, T | None]:
        """Attempt to call a function with the given arguments.

        This method first validates the arguments using invocable(), then calls the function
        if validation succeeds.

        Args:
            func: The function to call.
            *args: Positional arguments to pass to the function.
            **kwargs: Keyword arguments to pass to the function.

        Returns:
            A tuple of (success, result) where success is True if the call succeeded,
            and result is the return value of the function (or None if it failed).
        """
        if not func:
            return (False, None)

        # I. Check if the function can be called with the given arguments
        if (bound := cls.invocable(func, *args, **kwargs)) is not None:
            try:
                # II. Unpack the validated arguments and call the function
                result = func(*bound.args, **bound.kwargs)
                return True, result
            except Exception as e:
                name = getattr(func, '__name__', '[ANONYMOUS_FUNCTION]')
                fire.error(
                    f'Failed to invoke {name} with args={bound.args}, kwargs={bound.kwargs}: {e}'
                )
        return False, None


Typist._setup()
typist = Typist(atomics=True, splits=True)

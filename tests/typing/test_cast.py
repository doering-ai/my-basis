############
### HEAD ###
############
### STANDARD
from typing import Any, Literal, cast as type_cast
from collections.abc import Sequence, Collection
from collections import Counter, deque
from datetime import date, datetime, time, timedelta, UTC
from enum import Enum, Flag
import collections.abc as abc
import logging

### EXTERNAL
import pydantic as pyd
import pytest as pyt

### INTERNAL
from my.infra import Time
from my.types import Buffer, Span
from my.regex import MatchData, GroupKind
from my.typing import CastFlags, TypeCast, Typist
from my.typing.cast import CastPreset, Transform
from ..conftest import type_ids

############
### DATA ###
############
cls = TypeCast
#: A fully-flexible Typist instance. NOTE: `cast` is a staticmethod that reads flag state from the
#: global singleton (`Typist.inst()`, defaulting to `flex`), so this instance drives the non-cast
#: facade methods (serialize/flex_deserialize/...) while the flag tests toggle the singleton.
typist = Typist(firsts=True, atomics=True, splits=True, wraps=True)


class Color(Enum):
    """An int-valued enum for cast/serialize tests."""

    RED = 1
    GREEN = 2
    BLUE = 3


class Status(Enum):
    """A string-valued enum for cast tests."""

    ACTIVE = 'active'
    INACTIVE = 'inactive'
    PENDING = 'pending'


class Permission(Flag):
    """A flag enum for flag-cast tests."""

    READ = 1
    WRITE = 2
    EXECUTE = 4
    ADMIN = 8


#: `data, target, expected` matrices for `test_cast__*`, hoisted to module scope so `ids=` (via
#: `type_ids`) can be derived from the same list object the parametrize decorator consumes.
CAST_ATOMICS_CASES = [
    # ---- Numeric ----
    (20.0, int, 20),
    (20, float, 20.0),
    # ---- Deserialization ----
    ('-123', int, -123),
    ('-45.67', float, -45.67),
    ('true', bool, True),
    ('On', bool, True),
    ('EnAbLeD', bool, True),
    ('t', bool, True),
    ('y', bool, True),
    ('yes', bool, True),
    ('FALSE', bool, False),
    ('F', bool, False),
    ('no', bool, False),
    ('n', bool, False),
    ('Disabled', bool, False),
    ('   42   ', int, 42),
    # ---- Bytes/Buffer ----
    ('hello', bytes, b'hello'),
    (b'world', str, 'world'),
    (b'   3.14   ', float, 3.14),
    # ---- Edge Cases ----
    ([], str, '[]'),
    ({}, str, '{}'),
    (set(), str, 'set()'),
    ('maybe', bool, True),  # matches the rest of python
    # ---- Failures ----
    ('abc', int, None),
    ('12.34.56', float, None),
    # ---- NOOPs (string->string preserves whitespace verbatim) ----
    ('   ', str, '   '),
    ('hello', str, 'hello'),
    (5, int, 5),
]

CAST_SERIES_CASES = [
    # ---- Basic ----
    ([1, 2, 3], list[str], ['1', '2', '3']),
    ({1, 2, 3}, list[int], [1, 2, 3]),
    (['a', 'b', 'c'], set[str], {'a', 'b', 'c'}),
    (['abc'], set[str], {'abc'}),
    ('abc', set[str], {'abc'}),
    # ---- Deques ----
    (deque(['1', '5.5', '10']), set[float], {1.0, 5.5, 10.0}),
    ((1, 2, 3), deque[int], deque([1, 2, 3])),
    # ---- Splits ----
    (['1,2,3', '4,5,6'], list[list[int]], [[1, 2, 3], [4, 5, 6]]),
    # ---- Tuples ----
    (['1', '2', '3'], tuple[int, ...], (1, 2, 3)),
    (['1', '5', '10'], tuple[int, ...], (1, 5, 10)),
    (['1', '5', '10'], tuple[int, int, int], (1, 5, 10)),
    (['a', '1', 'b', '2'], tuple[str, int, str, int], ('a', 1, 'b', 2)),
    (['123', '456'], Span, Span(123, 456)),
    # ---- Generics ----
    (['1', '5', '10'], Sequence[int], [1, 5, 10]),
    ({'1', '5', '10'}, Collection[int], {1, 5, 10}),
    (['1', '5', '10'], Sequence[str], ['1', '5', '10']),
    (['1', '5', '10'], abc.Sequence, ['1', '5', '10']),
    (['1', '5', '10'], abc.MutableSequence, ['1', '5', '10']),
    (['1', '5', '10'], abc.MutableSet, {'1', '5', '10'}),
    # ---- Class Children ----
    (['a', 'b'], list[Buffer], [Buffer.new('a'), Buffer.new('b')]),
]

CAST_MAPS_CASES = [
    # ---- dict ----
    (dict(x=20.0), dict[str, int], dict(x=20)),
    ({'1': '2', '3': '4'}, dict[int, int], {1: 2, 3: 4}),
    ({'a': 1.5, 'b': 2.7}, dict[str, int], {'a': 1, 'b': 2}),
    ({'a': {'b': '1'}}, dict[str, dict[str, int]], {'a': {'b': 1}}),
    ('{"a": 1, "b": 2}', dict[str, int], {'a': 1, 'b': 2}),
    (
        [('a', '1'), ('b', '5'), ('c', '10')],
        dict[str, int],
        dict(a=1, b=5, c=10),
    ),
    # ---- Counter ----
    (['a', 'b', 'b'], Counter, Counter(a=1, b=2)),
    (['x', 'y', 'x', 'z'], Counter[str], Counter({'x': 2, 'y': 1, 'z': 1})),
    ([('a', '1'), ('b', '2')], Counter[str], Counter(a=1, b=2)),
    (Counter(z=15), dict[str, int], dict(z=15)),
    (
        ['a.b.c', 'x.y.z', 'a.b.c'],
        Counter[tuple[str, ...]],
        Counter({('a', 'b', 'c'): 2, ('x', 'y', 'z'): 1}),
    ),
]

CAST_MODELS_CASES = [
    ('a', Buffer, Buffer.new('a')),
    (
        dict(a=1, child=dict(b=2, c=3)),
        MatchData,
        MatchData.new({'a': ['1'], 'child.b': ['2'], 'child.c': ['3']}),
    ),
]

CAST_ENUMS_CASES = [
    # ---- Int enums - from int ----
    (1, Color, Color.RED),
    (2, Color, Color.GREEN),
    (3, Color, Color.BLUE),
    # ---- Int enums - from string name ----
    ('RED', Color, Color.RED),
    ('red', Color, Color.RED),
    ('GREEN', Color, Color.GREEN),
    # ---- Int enums - from string digit ----
    ('1', Color, Color.RED),
    ('2', Color, Color.GREEN),
    # ---- String enums ----
    ('active', Status, Status.ACTIVE),  # value
    ('ACTIVE', Status, Status.ACTIVE),  # name
    ('inactive', Status, Status.INACTIVE),
    ('pending', Status, Status.PENDING),
    # ---- Enum to string ----
    (Color.RED, str, 'red'),
    (Status.ACTIVE, str, 'active'),
    # ---- Enum to int ----
    (Color.RED, int, 1),
    (Color.BLUE, int, 3),
    # ---- GroupKind (MyEnum & Flag) ----
    ('plain', GroupKind, GroupKind.PLAIN),
    ('PLAIN', GroupKind, GroupKind.PLAIN),
]

CAST_FLAGS_CASES = [
    # ---- Single flags from int ----
    (1, Permission, Permission.READ),
    (2, Permission, Permission.WRITE),
    (4, Permission, Permission.EXECUTE),
    (8, Permission, Permission.ADMIN),
    # ---- Combined flags from int ----
    (3, Permission, Permission.READ | Permission.WRITE),
    (5, Permission, Permission.READ | Permission.EXECUTE),
    (
        15,
        Permission,
        Permission.READ | Permission.WRITE | Permission.EXECUTE | Permission.ADMIN,
    ),
    # ---- Flags from string name ----
    ('READ', Permission, Permission.READ),
    ('WRITE', Permission, Permission.WRITE),
    # ---- Flags from list (series to flag) ----
    (['READ', 'WRITE'], Permission, Permission.READ | Permission.WRITE),
    (['READ', 'EXECUTE'], Permission, Permission.READ | Permission.EXECUTE),
    # ---- Flags from pipe-separated string ----
    ('READ|WRITE', Permission, Permission.READ | Permission.WRITE),
    (
        'READ | WRITE|EXECUTE',
        Permission,
        Permission.READ | Permission.WRITE | Permission.EXECUTE,
    ),
    # ---- Flag to int ----
    (Permission.READ, int, 1),
    (Permission.READ | Permission.WRITE, int, 3),
    # ---- Flag to string ----
    (Permission.READ, str, 'read'),
]

CAST_TIMES_CASES = [
    # ---- Strings ----
    (date(1970, 2, 1), str, '1970-02-01'),
    (datetime(1970, 2, 1, 10, 20, 30, tzinfo=UTC), str, '1970-02-01T10:20:30'),
    (time(hour=10, minute=20, second=30, tzinfo=UTC), str, '10:20:30'),
    (timedelta(days=1, hours=1, minutes=1), str, '1 day, 1:01:00'),
    # ---- Integers ----
    (date(1970, 2, 1), int, 719194),
    (datetime(1970, 2, 1, 10, 20, 30, tzinfo=UTC), int, 2715630),
    (time(hour=10, minute=20, second=30, tzinfo=UTC), int, 37230),
    (timedelta(hours=10, minutes=20, seconds=30), int, 37230),
]

CAST_LITERALS_CASES = [
    # Literal strings
    ('one', Literal['one', 'two'], 'one'),
    ('two', Literal['one', 'two'], 'two'),
    # Literal ints
    (1, Literal[1, 2, 3], 1),
    (2, Literal[1, 2, 3], 2),
    # Casting to literals (coercion)
    ('1', Literal[1, 2, 3], 1),
    ('2', Literal[1, 2, 3], 2),
    (1, Literal['1', '2', '3'], '1'),
    # Literal tuples (positional)
    ([1, 'a'], tuple[int, str], (1, 'a')),
    (['1', 2], tuple[int, str], (1, '2')),
]

CAST_UNIONS_CASES = [
    # ---- Catching NOOPs ----
    ('1', int | float | bool | str, '1'),
    ('1', list[str] | str, '1'),  # avoid wrapping
    (['1'], str | list[str], ['1']),  # avoid unwrapping
    ((1, 2), tuple[str, ...] | tuple[int, int], (1, 2)),
    # ---- Avoiding problematic clauses ----
    ('1', None | int, 1),
    # ---- Arbitrary Preferences ----
    (1, str | bool, True),
    (2, bool | str, '2'),
    ('-1', float | int, -1),
    ('-1.5', int | float, -1.5),
    (['1', '2'], str | list[int], [1, 2]),
    (['1.0', '2.0'], str | list[int] | list[float], [1.0, 2.0]),
    (['enabled', 'OFF'], str | list[bool], [True, False]),
]

CAST_EDGE_CASES = [
    # Container <-.-> Atomic
    ('1', tuple[int], (1,)),
    (['1'], int, 1),
    (['1', '2'], int, 1),
    ('abc, cde. efg!', list[str], ['abc', 'cde. efg!']),
    ('transformers, safetensors', set[str], {'transformers', 'safetensors'}),
    # Malformed times
    ('25-07-02', datetime, datetime(2025, 7, 2, tzinfo=UTC)),
    (
        '25-07-02T10:20:30',
        datetime,
        datetime(2025, 7, 2, 10, 20, 30, tzinfo=UTC),
    ),
]

#: `data, target` pairs for `test_serialize_cast_roundtrip`: representative values across the type
#: lattice that must survive `serialize()` -> `cast()` and come back equal to the original.
ROUND_TRIP_CASES = [
    # ---- Atomics ----
    (5, int),
    ('hello', str),
    (3.14, float),
    (True, bool),
    (b'hello', bytes),
    (None, int),
    # ---- Vecs ----
    ([1, 2, 3], list[int]),
    ({'a', 'b'}, set[str]),
    ((1, 2, 3), tuple[int, ...]),
    (deque([1, 2, 3]), deque[int]),
    # ---- Maps (incl. nested) ----
    ({'a': 1, 'b': 2}, dict[str, int]),
    ({'a': {'b': 1}}, dict[str, dict[str, int]]),
    (Counter(a=1, b=2), Counter[str]),
    # ---- Enums / Flags ----
    (Color.RED, Color),
    (Status.ACTIVE, Status),
    (Permission.READ | Permission.WRITE, Permission),
    (GroupKind.PLAIN, GroupKind),
    # ---- Times -- timezone-AWARE only; see the exclusion note below ----
    (date(2024, 1, 1), date),
    (datetime(2024, 1, 1, 10, 20, 30, tzinfo=UTC), datetime),
    (time(10, 20, 30, tzinfo=UTC), time),
    (timedelta(days=1, hours=1, minutes=1), timedelta),
    # ---- Pydantic model / Struct ----
    (Buffer.new('hello'), Buffer),
    (MatchData.new({'a': ['1'], 'child.b': ['2']}), MatchData),
    (Span(1, 5), Span),
]

# ---- Legitimate one-way exclusions -- deliberately NOT in `ROUND_TRIP_CASES` ----
# `serialize -> cast` is lossy (not a bug) for these; the string form genuinely cannot carry the
# information needed to recover the original value, so a round-trip equality assertion would be
# wrong to make, not merely inconvenient:
#
#   - Naive `datetime`/`time` (no `tzinfo`): `serialize` renders the object's own local wall-clock
#     fields into an ISO string, but `cast` back always interprets that string as UTC -- there was
#     never a timezone opinion to preserve. On a UTC-5 machine,
#     `datetime(2024, 1, 1, 10, 20, 30)` (naive) serializes to `'2024-01-01T15:20:30'` (localized
#     to UTC) and casts back to `datetime(2024, 1, 1, 15, 20, 30, tzinfo=UTC)` -- a different
#     instant, not just a different repr. Machine-dependent besides.
#   - Negative `timedelta` (e.g. `timedelta(days=-1, hours=1)`): stdlib `timedelta` always
#     normalizes to a signed `days` plus non-negative `seconds`/`microseconds`, and `str()` on a
#     negative one renders as e.g. `'-1 day, 1:00:00'` -- `cast(str, timedelta)` has no rule for
#     recovering that leading sign, so it always comes back positive.


############
### BODY ###
############
class TestCast:
    """Test suite for the `cast` chamber: the `TypeCast` (`tyt`) coercion layer + `Transform`."""

    @pyt.fixture
    def flex_typist(self) -> abc.Iterator[Typist]:
        """The global Typist singleton with every cast flag enabled, restored afterward.

        Casting dispatches through the global singleton, so flag-mutation tests must drive that
        instance (not a fresh one); the fixture saves and restores its flags for isolation.
        """
        inst = Typist.inst()
        flags = ('firsts', 'atomics', 'splits', 'wraps')
        saved = {flag: getattr(inst, flag) for flag in flags}
        for flag in flags:
            setattr(inst, flag, True)
        yield inst
        for flag, value in saved.items():
            setattr(inst, flag, value)

    # -------------------
    # `-` Private Methods
    # -------------------
    @pyt.mark.parametrize(
        'data, expected',
        [
            (['abc', 'cde', 'efg'], ['abc', 'cde', 'efg']),
            (['1', '22', '-33'], [1, 22, -33]),
            (['1', '22.0', '-33'], [1.0, 22.0, -33.0]),
            (['true', 'YES', 'n', 'FaLsE'], [True, True, False, False]),
            (['true', '1', '2.0'], [True, 1, 2.0]),
        ],
    )
    def test_flex_deserialize(self, data: list[str], expected: list):
        # `flex_deserialize` guesses a scalar type per-value then delegates to `cast` -- most of
        # the underlying string->atom coercion is exercised by `test_cast__atomics` below.
        assert typist.flex_deserialize(data) == expected

    @pyt.mark.parametrize(
        'data, expected',
        [
            # ---- Already clean ----
            ('test', 'test'),
            ([1, 2, 3], [1, 2, 3]),
            # ---- Strings preserved verbatim (string->string never strips) ----
            ('  test  ', '  test  '),
            (b'  test  ', '  test  '),
            # ---- Iterators to lists ----
            (iter([1, 2, 3]), [1, 2, 3]),
            (iter(['a', 'b']), ['a', 'b']),
        ],
    )
    def test_clean_data(self, data: Any, expected: Any):
        # Casting to `str` is a verbatim NOOP -- whitespace is data, not noise, so it is
        # never stripped. Parsers (int/float/...) strip internally where they must.
        if isinstance(expected, str):
            result = typist.cast(data, str)
            assert result == expected
        elif isinstance(expected, list):
            # For iterators, test via cast to list
            result = typist.cast(data, list)
            assert result == expected

    # -------------------
    # `+` Primary Methods
    # -------------------

    # ------------------
    # `*` Public Methods
    # ------------------
    # -------------
    # `*2` COERCION
    # -------------
    @pyt.mark.parametrize(
        'data, target, expected', CAST_ATOMICS_CASES, ids=type_ids(CAST_ATOMICS_CASES)
    )
    def test_cast__atomics(self, data: Any, target: type, expected: object):
        assert typist.cast(data, target) == expected

    @pyt.mark.parametrize(
        'data, target, expected', CAST_SERIES_CASES, ids=type_ids(CAST_SERIES_CASES)
    )
    def test_cast__series(self, data: Any, target: type, expected: object):
        assert typist.cast(data, target) == expected

    @pyt.mark.parametrize('data, target, expected', CAST_MAPS_CASES, ids=type_ids(CAST_MAPS_CASES))
    def test_cast__maps(self, data: Any, target: type, expected: object):
        assert typist.cast(data, target) == expected

    @pyt.mark.parametrize(
        'data, target, expected', CAST_MODELS_CASES, ids=type_ids(CAST_MODELS_CASES)
    )
    def test_cast__models(self, data: Any, target: type, expected: object):
        assert typist.cast(data, target) == expected

    @pyt.mark.parametrize(
        'data, target, expected', CAST_ENUMS_CASES, ids=type_ids(CAST_ENUMS_CASES)
    )
    def test_cast__enums(self, data: Any, target: type, expected: object):
        result = typist.cast(data, target)
        assert result == expected

    @pyt.mark.parametrize(
        'data, target, expected', CAST_FLAGS_CASES, ids=type_ids(CAST_FLAGS_CASES)
    )
    def test_cast__flags(self, data: Any, target: type, expected: object):
        result = typist.cast(data, target)
        assert result == expected

    @pyt.mark.parametrize(
        'data, target, expected', CAST_TIMES_CASES, ids=type_ids(CAST_TIMES_CASES)
    )
    def test_cast__times(self, data: Time, target: type, expected: object):
        result = typist.cast(data, target)
        assert result == expected
        reverse = typist.cast(expected, type(data))
        assert reverse == data

    @pyt.mark.parametrize(
        'data, target, expected', CAST_LITERALS_CASES, ids=type_ids(CAST_LITERALS_CASES)
    )
    def test_cast__literals(self, data: Any, target: type, expected: object):
        result = typist.cast(data, target)
        assert result == expected

    @pyt.mark.parametrize(
        'data, target, expected', CAST_UNIONS_CASES, ids=type_ids(CAST_UNIONS_CASES)
    )
    def test_cast__unions(self, data: list, target: type, expected: object):
        assert typist.cast(data, target) == expected

    @pyt.mark.parametrize('data, target, expected', CAST_EDGE_CASES, ids=type_ids(CAST_EDGE_CASES))
    def test_cast__edge(self, data: list, target: type, expected: object):
        assert typist.cast(data, target) == expected

    @pyt.mark.parametrize(
        'data, target',
        [
            # A regression net for the Decline migration: each pair used to make a candidate
            # transform *crash* (and be silently rescued by the loop's blanket suppress) rather
            # than cleanly decline. A `decline-valve:` log record on any of them means a transform
            # is crashing again -- the exact bug class the Decline channel exists to kill.
            # -- parametrized-container source/target hitting the model transforms (_t0/_t1) --
            (['a', 'b'], dict),
            ({'a': [1]}, list[int]),
            ([1, 2, 3], dict),
            # -- single-word flag string (was recursing to RecursionError in _string_to_flag) --
            ('READ', Permission),
            ('plain', GroupKind),
            # -- non-date string (was an unguarded dateutil ParserError in _string_to_time).
            # Also covers basis-12 item 5: `_string_to_time` probes `cast(data, float)` to rule
            # out a numeric string before trying date parsing; that probe dispatches through
            # `_object_to_model` -> `Typist.invoke(float, data)`, which used to log the routine
            # failure at ERROR (`Failed to invoke float with args=...`) instead of debug -- a
            # declined candidate reported as a crash. --
            ('not-a-date', datetime),
            ('hello world', date),
            # -- builtin target with no introspectable signature (Typist.invocable) --
            ('x', int),
            (5, dict),
            # -- model target matching the broad Map bound (was cls(data) in _map_to_map) --
            (dict(a=1, child=dict(b=2, c=3)), MatchData),
        ],
    )
    def test_cast__no_latent_crash(self, data: Any, target: type, caplog: pyt.LogCaptureFixture):
        """A transform must *decline* (not crash) on inputs it can't handle.

        The cast loop's transitional safety valve logs a `decline-valve:` record whenever a
        transform raises something other than `Decline`. Asserting the log stays empty locks in
        the latent-crash fixes and guards against any future transform regressing into a crash.

        More generally, a *successful* cast should never emit an ERROR-level record at all: any
        exception caught along the way (by the decline-valve, by `Typist.invoke`, ...) represents
        a declined candidate, not a real failure, and should be logged no louder than debug.
        """
        with caplog.at_level(logging.DEBUG):
            typist.cast(data, target)
        errors = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
        assert not errors, f'benign cast dispatch logged at ERROR level: {errors}'

    def test_cast__firsts_and_atomics(self, flex_typist: Typist):
        """Test that `firsts`/`atomics` gate collapsing a series down to a single atom."""
        typist = flex_typist
        assert typist.cast([1, 2], int) == 1
        assert typist.cast([1], int) == 1

        typist.firsts = False
        assert typist.cast([1, 2], int) is None
        assert typist.cast([1], int) == 1

        typist.atomics = False
        assert typist.cast([1, 2], int) is None
        assert typist.cast([1], int) is None

    def test_cast__splits_and_wraps(self, flex_typist: Typist):
        """Test that `splits`/`wraps` gate string-splitting and atom-wrapping during casts."""
        typist = flex_typist
        assert typist.cast('A.B', set[str]) == {'A', 'B'}
        assert typist.cast('A.B:C', set[str]) == {'A.B', 'C'}
        assert typist.cast('A.B:C, D', set[str]) == {'A.B:C', 'D'}
        assert typist.cast('A.B:C //   D', set[str]) == {'A.B:C', 'D'}
        assert typist.cast(['A.B'], set[str]) == {'A.B'}
        assert typist.cast([['A.B']], list[set[str]]) == [{'A.B'}]
        assert typist.cast(['A.B'], list[set[str]]) == [{'A', 'B'}]

        typist.splits = False
        assert typist.cast('A.B', set[str]) == {'A.B'}
        assert typist.cast(['A.B'], set[str]) == {'A.B'}

        typist.wraps = False
        assert typist.cast('A.B', set[str]) is None
        assert typist.cast(['A.B'], set[str]) == {'A.B'}

    @pyt.mark.parametrize(
        'level, expected',
        [
            ('strict', CastFlags(firsts=False, atomics=False, splits=False, wraps=False)),
            ('basic', CastFlags(firsts=True, atomics=True, splits=True, wraps=False)),
            ('flex', CastFlags(firsts=True, atomics=True, splits=True, wraps=True)),
        ],
    )
    def test_cast_flags__preset(self, level: CastPreset, expected: CastFlags):
        """`CastFlags.preset` builds the same bundles `Typist.preset` used to hand-roll."""
        assert CastFlags.preset(level) == expected
        # `Typist.preset` now delegates to `CastFlags.preset`; the dict-bundle contract it
        # promises callers (e.g. `Typist(**preset(...))`) must keep matching exactly.
        assert Typist.preset(level) == expected.model_dump()

    def test_cast_flags__preset_invalid(self):
        # A bare `str` (not one of `CastPreset`'s literals) reaching `preset()` is exactly the
        # runtime misuse under test -- `type_cast` (stdlib `typing.cast`, a static-only no-op)
        # documents that intent instead of silencing the checker with a blanket `# type: ignore`.
        bogus = type_cast('CastPreset', 'bogus')
        with pyt.raises(ValueError, match='Invalid preset level'):
            CastFlags.preset(bogus)

    def test_cast_flags__frozen_and_hashable(self):
        """A `CastFlags` instance must reject mutation and be usable as a dict/set key."""
        flags = CastFlags.preset('flex')
        with pyt.raises(pyd.ValidationError):
            # `setattr` (rather than a static `flags.splits = False` assignment) keeps this a
            # runtime-only violation -- pydantic's frozen `__setattr__` still rejects it.
            setattr(flags, 'splits', False)  # noqa: B010

        # Hashable, and equal instances hash the same -- required for the memoization key
        # (`(t0, t1, flags)`) that commit 2 builds on top of this.
        assert hash(flags) == hash(CastFlags.preset('flex'))
        assert flags in {CastFlags.preset('flex'): 'cached'}

    @pyt.mark.parametrize(
        'flags, expected',
        [
            (CastFlags.preset('strict'), None),
            (CastFlags.preset('flex'), {'A', 'B'}),
            ('strict', None),
            ('flex', {'A', 'B'}),
        ],
    )
    def test_cast_flags__explicit_arg_wins(
        self, flex_typist: Typist, flags: CastFlags | CastPreset, expected: set[str] | None
    ):
        """An explicit `flags=` argument overrides the ambient singleton, regardless of it."""
        # The singleton is `flex` here (via the fixture), which would otherwise let 'A.B' split.
        flex_typist.splits = True
        flex_typist.wraps = True
        assert typist.cast('A.B', set[str], flags=flags) == expected

    def test_cast_flags__singleton_snapshot_default(self, flex_typist: Typist):
        """`flags=None` (the default) snapshots the live singleton's fields exactly once."""
        flex_typist.firsts = True
        flex_typist.atomics = False
        flex_typist.splits = False
        flex_typist.wraps = True
        resolved = CastFlags.resolve(None)
        assert resolved == CastFlags(firsts=True, atomics=False, splits=False, wraps=True)

        # And that snapshot is what an unflagged `cast()` call actually dispatches with.
        assert typist.cast('A.B', set[str]) == {'A.B'}  # splits=False -> no split
        assert typist.cast(['A.B'], set[str]) == {'A.B'}  # wraps=True -> wrap-preserved

    def test_cast_flags__resolve_explicit_instance_identity(self, flex_typist: Typist):
        """An explicit `CastFlags` instance passes through `resolve` unchanged (no copy)."""
        flex_typist.splits = True
        explicit = CastFlags(firsts=False, atomics=False, splits=False, wraps=False)
        assert CastFlags.resolve(explicit) is explicit

    def test_cast_flags__mid_cast_singleton_mutation_does_not_affect_inflight_cast(
        self, flex_typist: Typist
    ):
        """The new guarantee: once a `Transform`'s flags are snapshotted, a later mutation of the
        global `Typist` singleton (e.g. another thread/agent toggling `ty.splits`) cannot change
        the outcome of a cast already in flight -- unlike the old live `self.ty.X` reads this
        replaces (`cast.py` used to read `self.ty.splits`/`.wraps`/`.firsts`/`.atomics` at the
        moment each candidate transform ran, not just once at the start).
        """
        flex_typist.splits = True
        transform = Transform('A.B', set[str], flags=CastFlags.resolve(None))

        # Mutate the singleton *after* the snapshot was taken, simulating a concurrent cast (or a
        # nested transform) flipping the ambient default mid-flight.
        flex_typist.splits = False

        # The transform still splits -- its own captured `flags.splits` is untouched.
        assert transform() == {'A', 'B'}
        # Meanwhile, a brand-new cast (which resolves a fresh snapshot) correctly sees the change.
        assert typist.cast('A.B', set[str]) == {'A.B'}

    @pyt.mark.parametrize(
        'data, target, expected',
        [
            # Basic multicast
            (['1', '2', '3'], int, [1, 2, 3]),
            (['a', 'b', 'c'], str, ['a', 'b', 'c']),
            (['1.5', '2.7', '3.9'], float, [1.5, 2.7, 3.9]),
            # With None values
            ([1, None, 3], int, [1, None, 3]),
            (['a', None, 'c'], str, ['a', None, 'c']),
            # Nested
            ([['1', '2'], ['3', '4']], list[int], [[1, 2], [3, 4]]),
        ],
    )
    def test_multicast(self, data: list, target: type, expected: list):
        result = typist.multicast(data, target)
        assert result == expected

    @pyt.mark.parametrize(
        'data, target, expected',
        [
            # Successful casts
            ('123', int, 123),
            ('hello', str, 'hello'),
            (['1', '2'], list[int], [1, 2]),
            # Failed casts (returns original)
            ('abc', int, 'abc'),
            (None, int, None),
            ('not-a-date', datetime, 'not-a-date'),
        ],
    )
    def test_flexcast(self, data: Any, target: type, expected: Any):
        result = typist.flexcast(data, target)
        assert result == expected

    # -------------------
    # `*3` TRANSFORMATION
    # -------------------
    @pyt.mark.parametrize(
        'data, expected',
        [
            # ---- Atomic ----
            ('5', '5'),
            (5, 5),
            ([5], [5]),
            (Buffer.new('5'), '5'),
            (Color.RED, 'red'),
            (Status.ACTIVE, 'active'),
            (date(2025, 1, 1), '2025-01-01'),
            (datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC), '2025-01-01T12:00:00'),
            # ---- Sequences ----
            ([1, 2, Buffer.new('3')], [1, 2, '3']),
            # ---- Maps ----
            ({'a': 1, 'b': Color.RED}, {'a': 1, 'b': 'red'}),
            ({1, 2, 3}, [1, 2, 3]),
            (Counter(a=1, b=2), {'a': 1, 'b': 2}),
        ],
    )
    def test_serialize(self, data: object, expected: Any):
        assert typist.serialize(data) == expected

    @pyt.mark.parametrize(
        'data, cases, expected',
        [
            (['a', 2, 'b'], {str: str.upper}, ['A', 2, 'B']),
            (
                dict(a='hello', b=Color.BLUE, c=3),
                {str: lambda s: s[::-1], Color: lambda c: c.name.upper()},
                dict(a='olleh', b='BLUE', c=3),
            ),
            (
                [Buffer.new('one'), Buffer.new('two'), 3, 'four'],
                {Buffer: lambda b: b.text[0].upper()},
                ['ONE', 'TWO', 3, 'four'],
            ),
        ],
    )
    def test_serialize__cases(self, data: object, cases: dict, expected: Any):
        assert typist.serialize(data, cases=cases) == expected

    @pyt.mark.parametrize(
        'data, target', ROUND_TRIP_CASES, ids=type_ids(ROUND_TRIP_CASES, index=-1)
    )
    def test_serialize_cast_roundtrip(self, data: object, target: type):
        """`serialize() -> cast()` must recover the original value across the type lattice.

        This is the highest-value missing test for a coercion engine: round-trips previously
        existed only in corners (times in `test_cast__times`, pickle in `test_Typist.py`, YAML in
        `test_Predicate.py`) with nothing exercising the general `serialize`/`cast` pair together.
        See the comment above `ROUND_TRIP_CASES` for the legitimate one-way cases (naive times,
        negative timedeltas) intentionally excluded from this matrix -- do not weaken this
        assertion to accommodate them.
        """
        serialized = typist.serialize(data)
        result = typist.cast(serialized, target)
        assert result == data

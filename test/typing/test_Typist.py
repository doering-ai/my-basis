############
### HEAD ###
############
### STANDARD
from typing import Any, Literal
import typing
import types
import collections.abc as abc
from collections.abc import Mapping, Callable, Collection, Sequence
from collections import Counter, deque
from datetime import date, datetime, time, timedelta, UTC
from enum import Enum, Flag

### EXTERNAL
import pytest as pyt
import pydantic as pyd

### INTERNAL
from my.infra import Time
from my.types import Buffer, Span
from my.regex import MatchData, GroupKind
from my.typing import Typist, MyType
from ..conftest import boolmap

############
### DATA ###
############
typist = Typist(firsts=True, atomics=True, splits=True, wraps=True)


class Color(Enum):
    RED = 1
    GREEN = 2
    BLUE = 3


class Status(Enum):
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    PENDING = 'pending'


class Permission(Flag):
    READ = 1
    WRITE = 2
    EXECUTE = 4
    ADMIN = 8


############
### BODY ###
############
class TestTypist:
    # -------------------
    # `.` Initial Methods
    # -------------------

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
        # Most of this testing is done in test_to_atomic
        assert typist.flex_deserialize(data) == expected

    @pyt.mark.parametrize(
        'data, expected',
        [
            # ---- Already clean ----
            ('test', 'test'),
            ([1, 2, 3], [1, 2, 3]),
            # ---- Strings to clean ----
            ('  test  ', 'test'),
            (b'  test  ', 'test'),
            # ---- Iterators to lists ----
            (iter([1, 2, 3]), [1, 2, 3]),
            (iter(['a', 'b']), ['a', 'b']),
        ],
    )
    def test_clean_data(self, data: Any, expected: Any):
        # This tests the _clean_data private method indirectly through cast
        # Direct testing of private methods isn't ideal, but we can verify behavior
        if isinstance(expected, str):
            # For strings, test via cast to str (which calls _clean_data)
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
    # ---------------
    # `*1` COMPARISON
    # ---------------
    # -----------
    # MATCH TESTS
    # -----------
    @pyt.mark.parametrize(
        't0, t1, expected',
        boolmap(
            false=[
                (str, Buffer),
                (Sequence, str),
                (int, list[int]),
                (Span, tuple[int, str]),
                (Span, tuple[str, ...]),
                (str | int, dict | int),
                (str | dict | int, str | int),
                (list[int] | Mapping, Mapping),
                (Literal['A', 'B'], Literal['A']),
            ],
            true=[
                (str, str),
                (str, Sequence),
                (str | int, str | dict | int),
                (Counter, Mapping),
                (Typist, pyd.BaseModel),
                (Span, tuple[int, int]),
                (Mapping, list[int] | Mapping[str, list[int] | Mapping]),
            ],
        ),
    )
    def test_match_basic(self, t0, t1, expected: bool):
        assert typist.match(t0, t1) == expected

    @pyt.mark.parametrize(
        't0, t1, expected',
        boolmap(
            false=[
                (str, Buffer),
                (int, list[int]),
                (Span, tuple[int, str]),
                (Span, tuple[int]),
            ],
            true=[
                (Sequence, str),
                (str | int, dict | int),
                (str | int, str | dict | int),
                (str | dict | int, str | int),
                (str | Mapping, Mapping),
                (list[int] | Mapping, Mapping),
                (Span, tuple[int, ...]),
                (Literal['A', 'B'], Literal['A']),
                (Literal['A'], Literal['A', 'B']),
            ],
        ),
    )
    def test_match_intersect(self, t0, t1, expected: bool):
        assert typist.match(t0, t1, intersect=True) == expected

    @pyt.mark.parametrize(
        't0, t1, expected',
        boolmap(
            false=[
                # ---- Nested type mismatches ----
                (list[int], list[str]),
                (dict[str, int], dict[str, str]),
                (dict[str, int], dict[int, int]),
                (list[list[int]], list[list[str]]),
                (dict[str, list[int]], dict[str, list[str]]),
                # ---- Tuple literal type mismatches ----
                (tuple[int, str], tuple[str, int]),
                (tuple[int, str, float], tuple[int, str]),
                # ---- Literal mismatches ----
                (Literal[1, 2], Literal[3, 4]),
                (Literal['a'], Literal['b']),
            ],
            true=[
                # ---- Nested types ----
                (list[int], list[int]),
                (dict[str, int], dict[str, int]),
                (list[list[int]], list[list[int]]),
                (dict[str, list[int]], dict[str, list[int]]),
                # ---- Nested generics with subtyping ----
                (list[int], Sequence[int]),
                (dict[str, int], Mapping[str, int]),
                (Counter[str], Mapping[str, int]),
                # ---- Complex nested ----
                (dict[str, list[int]], Mapping[str, Sequence[int]]),
                (list[dict[str, int]], Sequence[Mapping[str, int]]),
                # ---- Tuple literals ----
                (tuple[int, str], tuple[int, str]),
                (tuple[int, ...], tuple[int, ...]),
                # ---- Literals ----
                (Literal[1, 2], Literal[1, 2, 3]),
                (Literal['a'], Literal['a', 'b']),
            ],
        ),
    )
    def test_match_nested(self, t0, t1, expected: bool):
        assert typist.match(t0, t1) == expected

    @pyt.mark.parametrize(
        't0, t1, expected',
        boolmap(
            false=[
                (MyType.parse(Ellipsis), MyType.parse(types.NoneType)),
                (MyType.parse(types.NoneType), MyType.parse(typing.Self)),
            ],
            true=[
                (Any, Any),
                (Any, None),
                (Any, str),
                (None, Any),
                (None, None),
                (None, str),
                (str, Any),
                (str, None),
            ],
        ),
    )
    def test_match_edge_cases(self, t0, t1, expected: bool):
        assert typist.match(t0, t1) == expected

    # -----------
    # CHECK TESTS
    # -----------
    @pyt.mark.parametrize(
        'data, tvar, expected',
        boolmap(
            false=[
                ([1, 2, 'a'], int),
                (['a', 1, 'b'], str),
                ([[1, 2], ['a', 'b']], list[int]),
            ],
            true=[
                ([], int),
                ([1, 2, 3], int),
                ([True, False], bool),
                (['a', 'b', 'c'], str),
                ([[1, 2], [3, 4]], list[int]),
            ],
        ),
    )
    def test_all_are(self, data: list, tvar: type, expected: bool):
        assert typist.all_are(data, tvar) == expected

    @pyt.mark.parametrize(
        'data, tvar, expected',
        boolmap(
            false=[
                (['a', 'b', 'c'], int),
                ([1, 2, 3], str),
                ([], int),
            ],
            true=[
                ([1, 'a', 3], int),
                (['a', 1, 'b'], int),
                ([True, 1, 'a'], bool),
                ([1, 2, 3], int),
            ],
        ),
    )
    def test_any_are(self, data: list, tvar: type, expected: bool):
        assert typist.any_are(data, tvar) == expected

    # -------------
    # `*2` COERCION
    # -------------
    @pyt.mark.parametrize(
        'data, target, expected',
        [
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
            # ---- NOOPs ----
            ('   ', str, ''),
            ('hello', str, 'hello'),
            (5, int, 5),
        ],
    )
    def test_cast__atomics(self, data: Any, target: type, expected: object):
        assert typist.cast(data, target) == expected

    @pyt.mark.parametrize(
        'data, target, expected',
        [
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
        ],
    )
    def test_cast__series(self, data: Any, target: type, expected: object):
        assert typist.cast(data, target) == expected

    @pyt.mark.parametrize(
        'data, target, expected',
        [
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
        ],
    )
    def test_cast__maps(self, data: Any, target: type, expected: object):
        assert typist.cast(data, target) == expected

    @pyt.mark.parametrize(
        'data, target, expected',
        [
            ('a', Buffer, Buffer.new('a')),
            (
                dict(a=1, child=dict(b=2, c=3)),
                MatchData,
                MatchData.new({'a': ['1'], 'child.b': ['2'], 'child.c': ['3']}),
            ),
        ],
    )
    def test_cast__models(self, data: Any, target: type, expected: object):
        assert typist.cast(data, target) == expected

    @pyt.mark.parametrize(
        'data, target, expected',
        [
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
        ],
    )
    def test_cast__enums(self, data: Any, target: type, expected: object):
        result = typist.cast(data, target)
        assert result == expected

    @pyt.mark.parametrize(
        'data, target, expected',
        [
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
        ],
    )
    def test_cast__flags(self, data: Any, target: type, expected: object):
        result = typist.cast(data, target)
        assert result == expected

    @pyt.mark.parametrize(
        'data, target, expected',
        [
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
        ],
    )
    def test_cast__times(self, data: Time, target: type, expected: object):
        result = typist.cast(data, target)
        assert result == expected
        reverse = typist.cast(expected, type(data))
        assert reverse == data

    @pyt.mark.parametrize(
        'data, target, expected',
        [
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
        ],
    )
    def test_cast__literals(self, data: Any, target: type, expected: object):
        result = typist.cast(data, target)
        assert result == expected

    @pyt.mark.parametrize(
        'data, target, expected',
        [
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
        ],
    )
    def test_cast__unions(self, data: list, target: type, expected: object):
        assert typist.cast(data, target) == expected

    @pyt.mark.parametrize(
        'data, target, expected',
        [
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
        ],
    )
    def test_cast__edge(self, data: list, target: type, expected: object):
        assert typist.cast(data, target) == expected

    def test_cast__firsts_and_atomics(self):
        assert typist.cast([1, 2], int) == 1
        assert typist.cast([1], int) == 1

        typist.firsts = False
        assert typist.cast([1, 2], int) is None
        assert typist.cast([1], int) == 1

        typist.atomics = False
        assert typist.cast([1, 2], int) is None
        assert typist.cast([1], int) is None

        typist.firsts = typist.atomics = True

    def test_cast__splits_and_wraps(self):
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

        typist.splits = typist.wraps = True

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
        'models, expected',
        [
            # Positive case
            (
                [
                    dict(a=dict(aa=[1, 3, 2, 4], ab=dict(aba=9, abb=99))),
                    dict(a=dict(aa=[8, 7, 6, 5], ab=dict(aba=0))),
                ],
                dict(a=dict(aa=list(range(1, 9)), ab=dict(aba=0, abb=99))),
            ),
            (
                [dict(a=[1, 2, 3]), dict(a=deque([4, 5, 6]))],
                dict(a=[1, 2, 3, 4, 5, 6]),
            ),
            # Negative case
            (
                [dict(a=[1, 2, 3]), dict(a=dict(aa=[4, 5, 6]))],
                dict(a=dict(aa=[4, 5, 6])),
            ),
            (
                [dict(a=1), dict()],
                dict(a=1),
            ),
            (
                [dict(), dict()],
                dict(),
            ),
        ],
    )
    def test_assemble(self, models: list[dict], expected: dict):
        assert typist.assemble(models[0], *models[1:]) == expected

    @pyt.mark.parametrize(
        'models, expected, remaining',
        [
            # Main case
            (
                [
                    dict(a=dict(aa=[3]), b='8'),
                    dict(a=dict(aa=[3, 4, 5], ab='7'), b='8'),
                ],
                dict(a=dict(aa=[3]), b='8'),
                [
                    dict(),
                    dict(a=dict(aa=[4, 5], ab='7')),
                ],
            ),
            # Edge case: type mismatch
            (
                [dict(a=deque([1, 2, 3])), dict(a=[1, 2, 3])],
                dict(),
                [dict(a=deque([1, 2, 3])), dict(a=[1, 2, 3])],
            ),
            # Edge case: empty args
            ([dict(), dict()], dict(), [dict(), dict()]),
        ],
    )
    def test_distill(self, models: list[dict], expected: dict, remaining: list[dict]):
        result = typist.distill(models)
        assert result == expected

        assert len(models) == len(remaining)
        for ret, exp in zip(models, remaining, strict=True):
            assert ret == exp

    # ----------------
    # `*4` PERSISTENCE
    # ----------------
    @pyt.mark.parametrize(
        'data, expected',
        [
            (dict(a=1, b=2, c=3), ['a: 1', 'b: 2', 'c: 3']),
            (
                dict(a=1, b=dict(b0=2, c=dict(c0=3))),
                ['a: 1', 'b:', '    b0: 2', '    c:', '        c0: 3'],
            ),
            (
                dict(a=1, list=[2, dict(b=3, c=dict(d=4)), 5]),
                [
                    'a: 1',
                    'list:',
                    '    - 2',
                    '    - b: 3',
                    '      c:',
                    '          d: 4',
                    '    - 5',
                ],
            ),
            ([dict(a=1, x=9)], ['- a: 1', '  x: 9']),
            (
                [dict(a=1, x=9), dict(b=2, y=8), (dict(c=3, z=7))],
                ['- a: 1', '  x: 9', '- b: 2', '  y: 8', '- c: 3', '  z: 7'],
            ),
            (['one', 'two', 'three'], ['- one', '- two', '- three']),
            (
                ['one', ['two', ['three']]],
                ['- one', '-     - two', '      -     - three'],
            ),
            ([1, Buffer.new('[two]'), 'three'], ['- 1', "- '[two]'", '- three']),
            ([dict(a=1, b=2), 'two', 3], ['- a: 1', '  b: 2', '- two', '- 3']),
            (
                dict(one=1, two='two', three=['a', 'b', 'c']),
                ['one: 1', 'two: two', 'three:', '    - a', '    - b', '    - c'],
            ),
        ],
    )
    def test_to_yaml(self, data: Any, expected: list[str]):
        yaml = typist.to_yaml(data).strip('\n')
        assert yaml == '\n'.join(expected)

    @pyt.mark.parametrize(
        'yaml, tvar, expected',
        [
            (['- 1', "- '[two]'", '- three'], list, [1, '[two]', 'three']),
            (['- a: 1', '  b: 2', '- two', '- 3'], list, [dict(a=1, b=2), 'two', 3]),
            (
                ['one: 1', 'two: two', 'three: [a, b, c]'],
                dict,
                dict(one=1, two='two', three=['a', 'b', 'c']),
            ),
        ],
    )
    def test_from_yaml(self, yaml: list[str], tvar, expected: Any):
        content = '\n'.join(yaml)
        data = typist.from_yaml(content, tvar)
        assert data == expected

    @pyt.mark.parametrize(
        'data, expected',
        [
            (dict(a=1, b=2, c=3), '{\n    "a":1,\n    "b":2,\n    "c":3\n}'),
            ([1, 2, 3], '[\n    1,\n    2,\n    3\n]'),
            ('test', '"test"'),
            (123, '123'),
        ],
    )
    def test_to_json(self, data: Any, expected: str):
        result = typist.to_json(data)
        assert result == expected

    @pyt.mark.parametrize(
        'json_str, tvar, expected',
        [
            ('{"a": 1, "b": 2}', dict, dict(a=1, b=2)),
            ('[1, 2, 3]', list, [1, 2, 3]),
            ('"test"', str, 'test'),
            ('123', int, 123),
            ('true', bool, True),
        ],
    )
    def test_from_json(self, json_str: str, tvar, expected: Any):
        result = typist.from_json(json_str, tvar)
        assert result == expected

    @pyt.mark.parametrize(
        'data, expected_lines',
        [
            (dict(a=1, b=2), ['a = 1', 'b = 2']),
            (dict(section=dict(x=1, y=2)), ['[section]', 'x = 1', 'y = 2']),
            (dict(list=[1, 2, 3]), ['list = [', '    1,', '    2,', '    3,', ']']),
        ],
    )
    def test_to_toml(self, data: dict, expected_lines: list[str]):
        result = typist.to_toml(data)
        for line in expected_lines:
            assert line in result

    @pyt.mark.parametrize(
        'toml_str, expected',
        [
            ('a = 1\nb = 2', dict(a=1, b=2)),
            ('[section]\nx = 1\ny = 2', dict(section=dict(x=1, y=2))),
            ('list = [1, 2, 3]', dict(list=[1, 2, 3])),
        ],
    )
    def test_from_toml(self, toml_str: str, expected: dict):
        result = typist.from_toml(toml_str)
        assert result == expected

    @pyt.mark.parametrize(
        'data',
        [
            dict(a=1, b=2, c=3),
            [1, 2, 3],
            'test string',
            123,
            {'nested': {'data': [1, 2, 3]}},
        ],
    )
    def test_pickle_roundtrip(self, data: Any):
        # Test that pickling and unpickling returns the same data
        pickled = typist.to_pickle(data)
        assert isinstance(pickled, bytes)
        unpickled = typist.from_pickle(pickled, type(data))
        assert unpickled == data

    # ---------------
    # `*5` INVOCATION
    # ---------------
    def test_get_method(self):
        # Test getting existing methods
        obj = Buffer.new('test')
        assert typist.get_method(obj, 'write') is not None
        assert callable(typist.get_method(obj, 'write'))

        # Test with multiple method names (returns first found)
        assert typist.get_method(obj, 'nonexistent', 'write') is not None

        # Test with no matching methods
        assert typist.get_method(obj, 'nonexistent', 'also_nonexistent') is None

        # Test on dict
        d = {'a': 1}
        assert typist.get_method(d, 'get') is not None
        assert typist.get_method(d, 'keys') is not None

    def test_get_str_method(self):
        # Test with Buffer which has write method
        obj = Buffer.new('test')
        method = typist.get_str_method(obj)
        assert method is not None
        assert callable(method)

        # Test with string (has __str__)
        s = 'test'
        method = typist.get_str_method(s)
        assert method is not None

        # Test with int (has __str__)
        n = 123
        method = typist.get_str_method(n)
        assert method is not None

    @pyt.mark.parametrize(
        'data, tvar, expected',
        [
            ([1, '2', 3, '2'], str, ['2', '2']),
            (
                deque(
                    [
                        'the first item',
                        dict(a=[1, '2']),
                        dict(b=[3], c=[]),
                        {b'd': [4]},
                        5,
                    ]
                ),
                dict[str, list[int]],
                [dict(b=[3], c=[])],
            ),
        ],
    )
    def test_type_partition(self, data, tvar, expected):
        ret_false, ret_true = typist.type_partition(data, tvar)
        assert ret_true == expected
        assert ret_false == [v for v in data if v not in ret_true]

    @pyt.mark.parametrize(
        't0, t1, expected',
        boolmap(
            false=[
                (str, int),
                (int, list[str]),
            ],
            true=[
                (str, str),
                (int, list[int]),
                (str, dict[str, int]),
                (str, tuple[int, str]),
                (str, tuple[str, ...]),
                (dict[str, int], dict[tuple[dict[str, int], ...], dict[int, int]]),
                (dict[str, int], dict[tuple[str, int, dict[int, int]], dict[str, int]]),
            ],
        ),
    )
    def test_seek_usage(self, t0, t1, expected: bool):
        assert typist.seek_usage(t0, t1) == expected

    @pyt.mark.parametrize(
        'lhs, rhs, expected',
        boolmap(
            false=[
                ('abc', 123),
                ([1], {1}),
            ],
            true=[
                ('abc', 'def'),
                (1, 2),
                ([1], [2, 3]),
            ],
        ),
    )
    def test_match_instances(self, lhs, rhs, expected: bool):
        assert typist.match_instances(lhs, rhs) == expected

    def test_setattr(self):
        # Create a simple pydantic model for testing
        class TestModel(pyd.BaseModel):
            name: str
            age: int
            score: float

        obj = TestModel(name='test', age=10, score=5.5)

        # Test setting with type casting
        success = typist.setattr(obj, 'age', '25')
        assert success
        assert obj.age == 25

        # Test setting with explicit type
        success = typist.setattr(obj, 'score', '7.5', float)
        assert success
        assert obj.score == 7.5

        # Test setting with correct type (no casting needed)
        success = typist.setattr(obj, 'name', 'new_name')
        assert success
        assert obj.name == 'new_name'

    # Test helper functions for invocable/invoke
    @staticmethod
    def _func_no_params() -> str:
        return 'no params'

    @staticmethod
    def _func_one_pos(x: int) -> int:
        return x * 2

    @staticmethod
    def _func_one_pos_default(x: int = 5) -> int:
        return x * 2

    @staticmethod
    def _func_two_pos(x: int, y: str) -> str:
        return f'{x}: {y}'

    @staticmethod
    def _func_pos_and_kwonly(x: int, *, y: str) -> str:
        return f'{x}: {y}'

    @staticmethod
    def _func_with_varargs(*args: int) -> int:
        return sum(args)

    @staticmethod
    def _func_with_kwargs(**kwargs: Any) -> dict:
        return kwargs

    @staticmethod
    def _func_mixed(a: int, b: str = 'default', *args: int, **kwargs: Any) -> tuple:
        return (a, b, args, kwargs)

    @staticmethod
    def _func_pos_only(x: int, /) -> int:
        return x * 2

    @pyt.mark.parametrize(
        'func, args, kwargs, expected_success',
        [
            # ---- No params ----
            (_func_no_params, (), {}, True),
            (_func_no_params, (1,), {}, False),  # Extra arg
            # ---- One positional ----
            (_func_one_pos, (5,), {}, True),
            (_func_one_pos, (), {}, False),  # Missing required
            (_func_one_pos, (), {'x': 5}, True),  # As kwarg
            (_func_one_pos, (5, 6), {}, False),  # Too many args
            # ---- One positional with default ----
            (_func_one_pos_default, (), {}, True),
            (_func_one_pos_default, (10,), {}, True),
            (_func_one_pos_default, (), {'x': 10}, True),
            # ---- Two positional ----
            (_func_two_pos, (1, 'hi'), {}, True),
            (_func_two_pos, (1,), {'y': 'hi'}, True),
            (_func_two_pos, (), {'x': 1, 'y': 'hi'}, True),
            (_func_two_pos, (1,), {}, False),  # Missing y
            (_func_two_pos, (1, 2), {}, False),  # Wrong type for y
            # ---- Positional and keyword-only ----
            (_func_pos_and_kwonly, (1,), {'y': 'hi'}, True),
            (_func_pos_and_kwonly, (1, 'hi'), {}, False),  # y must be kwarg
            (_func_pos_and_kwonly, (), {'x': 1, 'y': 'hi'}, True),
            # ---- Varargs ----
            (_func_with_varargs, (1, 2, 3), {}, True),
            (_func_with_varargs, (), {}, True),  # Empty varargs ok
            # ---- Kwargs ----
            (_func_with_kwargs, (), {'a': 1, 'b': 2}, True),
            (_func_with_kwargs, (), {}, True),  # Empty kwargs ok
            (_func_with_kwargs, (1,), {}, False),  # No positional params
            # ---- Mixed ----
            (_func_mixed, (5,), {}, True),
            (_func_mixed, (5, 'custom'), {}, True),
            (_func_mixed, (5, 'custom', 1, 2), {'z': 3}, True),
            (_func_mixed, (), {}, False),  # Missing required 'a'
            # ---- Positional-only ----
            (_func_pos_only, (5,), {}, True),
            (_func_pos_only, (), {'x': 5}, False),  # x is positional-only
        ],
    )
    def test_invocable(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        expected_success: bool,
    ):
        result = typist.invocable(func, *args, **kwargs)
        if expected_success:
            assert result is not None
        else:
            assert result is None

    @pyt.mark.parametrize(
        'func, args, kwargs, expected_result',
        [
            # ---- No params ----
            (_func_no_params, (), {}, 'no params'),
            # ---- One positional ----
            (_func_one_pos, (5,), {}, 10),
            (_func_one_pos, (), dict(x=5), 10),
            # ---- One positional with default ----
            (_func_one_pos_default, (), {}, 10),
            (_func_one_pos_default, (7,), {}, 14),
            # ---- Two positional ----
            (_func_two_pos, (42, 'answer'), {}, '42: answer'),
            (_func_two_pos, (42,), dict(y='answer'), '42: answer'),
            (_func_two_pos, (), dict(x=42, y='answer'), '42: answer'),
            (_func_two_pos, (1, 2, 3), dict(), None),
            (_func_two_pos, (), dict(), None),
            (_func_two_pos, (), dict(x=1, y=2, z=3), None),
            (_func_two_pos, (1, 2), dict(x=1), None),
            # ---- Positional and keyword-only ----
            (_func_pos_and_kwonly, (1,), dict(y='test'), '1: test'),
            # ---- Varargs ----
            (_func_with_varargs, (1, 2, 3, 4), {}, 10),
            (_func_with_varargs, (), {}, 0),
            # ---- Kwargs ----
            (_func_with_kwargs, (), dict(a=1, b=2), dict(a=1, b=2)),
            (_func_with_kwargs, (), {}, {}),
            (_func_with_kwargs, (1, 2), dict(), None),
            # ---- Mixed ----
            (_func_mixed, (5,), {}, (5, 'default', (), {})),
            (_func_mixed, (5, 'custom'), {}, (5, 'custom', (), {})),
            (
                _func_mixed,
                (5, 'custom', 1, 2),
                dict(z=3),
                (5, 'custom', (1, 2), dict(z=3)),
            ),
            # ---- Positional-only ----
            (_func_pos_only, (5,), {}, 10),
        ],
    )
    def test_invoke(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        expected_result: Any,
    ):
        result = typist.invoke(func, *args, **kwargs)
        assert result == expected_result, f'Expected {expected_result}, got {result}'

    @pyt.mark.parametrize(
        'func, args, kwargs',
        [
            (_func_one_pos, (), {}),  # Missing required
            (_func_one_pos, (1, 2), {}),  # Too many args
            (_func_two_pos, (1,), {}),  # Missing required
            (_func_pos_and_kwonly, (1, 'hi'), {}),  # y must be kwarg
            (_func_with_kwargs, (1,), {}),  # No positional params
            (_func_pos_only, (), {'x': 5}),  # x is positional-only
        ],
    )
    def test_invoke_failure(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
    ):
        result = typist.invoke(func, *args, **kwargs)
        assert result is None, f'Expected None result on failure, got {result}'

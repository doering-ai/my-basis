############
### HEAD ###
############
### STANDARD
from typing import (
    Any,
    Iterable,
    Mapping,
    Callable,
    Container,
    Collection,
    Coroutine,
    Literal,
    Optional,
    Sequence,
    Generator,
    TypeGuard,
    Annotated,
    Union,
)
from collections import Counter, deque
from collections.abc import Mapping as AbcMapping, Sequence as AbcSequence
from datetime import date, datetime, time, timedelta, timezone

### EXTERNAL
import pytest as pyt
import pydantic as pyd

### INTERNAL
from my.infra import TimeType
from my.types import Buffer, Span
from my.regex import MatchData
from my.typing import Typist, TypeArg

############
### DATA ###
############
typist = Typist(firsts=True, atomics=True, splits=True)


############
### BODY ###
############
class TestTypist:
    @pyt.mark.parametrize(
        'data, expected',
        [
            # Unparseable types
            (None, (None, None, None)),
            (Any, (None, None, None)),
            (Callable, (None, None, None)),
            (Callable[[int, ...], str], (None, None, None)),
            (TypeGuard[str], (None, None, None)),
            (Coroutine, (None, None, None)),
            (Generator, (None, None, None)),
            (Generator[int, None, float], (None, None, None)),
            # Union Types
            (Union[dict[str, int], int], (dict, str, int)),
            (Optional[str], (str, None, None)),
            (dict[str, int] | int, (dict, str, int)),
            ((dict[str, int], int), (dict, str, int)),
            (Coroutine | dict[str, int] | int, (dict, str, int)),
            (Coroutine | Generator, (None, None, None)),
            # Generic types
            (dict[str, int], (dict, str, int)),
            (dict[str, Any], (dict, str, None)),
            (dict[str, list[str]], (dict, str, list[str])),
            (Literal['one', 'two'], (str, None, None)),
            (tuple, (tuple, None, None)),
            (tuple[str, ...], (tuple, None, str)),
            (tuple[str, str], (tuple, None, str)),
            (tuple[str, int, Any], (tuple, (str, int, object), (str, int, object))),
            (
                tuple[str, tuple[str, int], str],
                (tuple, (str, tuple[str, int], str), (str, tuple[str, int], str)),
            ),
            (set[str], (set, None, str)),
            (set, (set, None, None)),
            # Wrappers
            (Annotated[list[int], 5], (list, None, int)),
            (Annotated, (None, None, None)),
            (Literal, (None, None, None)),
            (Counter[str], (Counter, str, int)),
            (Counter, (Counter, None, int)),
            # Tuples
            # Abstract types
            (Mapping, (AbcMapping, None, None)),
            (Mapping[int, Any], (AbcMapping, int, None)),
            (Mapping[int, str], (AbcMapping, int, str)),
            (Sequence, (AbcSequence, None, None)),
            (Sequence[str], (AbcSequence, None, str)),
            (Sequence[Any], (AbcSequence, None, None)),
        ],
    )
    def test_parse(
        self,
        data: type | tuple[type, ...] | None,
        expected: tuple[type | None, type | None, type | None],
    ):
        assert typist.parse(data) == expected

    @pyt.mark.parametrize(
        'tvar, expected',
        [
            (int, None),
            (list[int], None),
            (int | str, (int, str)),
            (list[int] | Mapping, (list[int], Mapping)),
            (Union[list[int], Mapping], (list[int], Mapping)),
        ],
    )
    def test_decompose_union(self, tvar: TypeArg, expected: tuple | None):
        assert typist._decompose_union(tvar) == (expected or tuple())

    @pyt.mark.parametrize(
        't0, t1, expected',
        [
            (str, str, True),
            (str, Sequence, True),
            (Sequence, str, False),
            (str | int, dict | int, True),
            ((str, int), (dict, int), True),
            (Counter, Mapping, True),
            (Typist, pyd.BaseModel, True),
            (list[int] | Mapping, Mapping, True),
            (list[int] | Mapping[str, list[int] | Mapping], Mapping, True),
            (int, list[int], False),
            (str, Buffer, False),
        ],
    )
    def test_match(self, t0: TypeArg, t1: TypeArg, expected: bool):
        assert typist.match(t0, t1) == expected

    @pyt.mark.parametrize(
        't0, t1, expected',
        [
            (int, pyd.BaseModel, False),
            (int, list[int], True),
            (int, dict[int, str], False),
            (int, dict[str, int], True),
            (list[str], Buffer, True),
            (list[float], Buffer, False),
            (list[str], int | dict[str, list[Buffer]], True),
            (str, Buffer, True),
        ],
    )
    def test_match__recursive(self, t0: TypeArg, t1: TypeArg, expected: bool):
        assert typist.match(t0, t1, recurse=True) == expected

    @pyt.mark.parametrize(
        'data, tvar, expected',
        [
            ('abc', str, True),
            (1, str, False),
            (Counter(a=1), Mapping, True),
            (Counter(b=2), Mapping[str, int], True),
            (Counter(b=2), Mapping[str, str], False),
            (dict(a=1), Container[str], True),
        ],
    )
    def test_check(self, data: Iterable, tvar: type, expected: bool):
        assert typist.check(data, tvar) == expected

    @pyt.mark.parametrize(
        'data, target, expected',
        [
            (['1', '5', '10'], Sequence[str], ['1', '5', '10']),
            (['1', '5', '10'], Sequence[int], [1, 5, 10]),
            ({'1', '5', '10'}, Collection[int], {1, 5, 10}),
            (deque(['1', '5.5', '10']), set[float], {1.0, 5.5, 10.0}),
            (['1', '5', '10'], tuple[int], (1, 5, 10)),
        ],
    )
    def test_cast(self, data: Any, target: type, expected: object):
        assert typist.cast(data, target) == expected

    @pyt.mark.parametrize(
        'data, target, expected',
        [
            (['1', '2', '3'], tuple[int, ...], (1, 2, 3)),
            (['a', '1', 'b', '2'], tuple[str, int, str, int], ('a', 1, 'b', 2)),
            (['123', '456'], Span, Span((123, 456))),  # tuple subtype
        ],
    )
    def test_cast__tuples(self, data: Any, target: type, expected: object):
        assert typist.cast(data, target) == expected

    @pyt.mark.parametrize(
        'data, target, expected',
        [
            (dict(x=20.0), dict[str, int], dict(x=20)),
            (Counter(z=15), dict[str, int], dict(z=15)),
            ([('a', '1'), ('b', '5'), ('c', '10')], dict[str, int], dict(a=1, b=5, c=10)),
            ([('a', '1'), ('b', '2')], Counter[str], Counter(a=1, b=2)),
            (['a', 'b', 'b'], Counter, Counter(a=1, b=2)),
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
            # <- -> str
            (date(1970, 2, 1), str, '1970-02-01'),
            (datetime(1970, 2, 1, 10, 20, 30, tzinfo=timezone.utc), str, '1970-02-01T10:20:30'),
            (time(hour=10, minute=20, second=30, tzinfo=timezone.utc), str, '10:20:30'),
            (timedelta(days=1, hours=1, minutes=1), str, '1 day, 1:01:00'),
            # <- -> int
            (date(1970, 2, 1), int, 719194),
            (datetime(1970, 2, 1, 10, 20, 30, tzinfo=timezone.utc), int, 2715630),
            (time(hour=10, minute=20, second=30, tzinfo=timezone.utc), int, 37230),
            (timedelta(hours=10, minutes=20, seconds=30), int, 37230),
        ],
    )
    def test_cast__times(self, data: TimeType, target: type, expected: object):
        result = typist.cast(data, target)
        assert result == expected
        reverse = typist.cast(expected, type(data))
        assert reverse == data

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
            ('25-07-02', datetime, datetime(2025, 7, 2, tzinfo=timezone.utc)),
            ('25-07-02T10:20:30', datetime, datetime(2025, 7, 2, 10, 20, 30, tzinfo=timezone.utc)),
        ],
    )
    def test_cast__edge(self, data: list, target: type, expected: object):
        assert typist.cast(data, target) == expected

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
        assert typist.flex_deserialize(data) == expected

    # ----------------------
    # Distilling and Merging
    # ----------------------
    @pyt.mark.parametrize(
        'models, expected',
        [
            # Basics
            (
                [
                    dict(a=dict(aa=[1, 3, 2, 4], ab=dict(aba=9, abb=99))),
                    dict(a=dict(aa=[8, 7, 6, 5], ab=dict(aba=0))),
                ],
                dict(a=dict(aa=list(range(1, 9)), ab=dict(aba=0, abb=99))),
            ),
            # Values of different types aren't merged
            ([dict(a=[1, 2, 3]), dict(a=deque([4, 5, 6]))], dict(a=deque([4, 5, 6]))),
            # Edge cases
            ([dict(), dict()], dict()),
            # Edge cases
            ([dict(a=1), dict()], dict(a=1)),
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

    # ---------
    # Exporting
    # ---------
    @pyt.mark.parametrize(
        'data, kwargs, expected',
        [
            ('5', dict(), '5'),
            (5, dict(), 5),
            ([5], dict(), [5]),
            (Buffer.new('5'), dict(), '5'),
        ],
    )
    def test_serialize(self, data: object, kwargs: dict, expected: Any):
        assert typist.serialize(data, **kwargs) == expected

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
            (['one', ['two', ['three']]], ['- one', '-     - two', '      -     - three']),
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
        'yaml, expected',
        [
            (['- 1', "- '[two]'", '- three'], [1, '[two]', 'three']),
            (['- a: 1', '  b: 2', '- two', '- 3'], [dict(a=1, b=2), 'two', 3]),
            (
                ['one: 1', 'two: two', 'three: [a, b, c]'],
                dict(one=1, two='two', three=['a', 'b', 'c']),
            ),
        ],
    )
    def test_from_yaml(self, yaml: list[str], expected: Any):
        data = typist.from_yaml('\n'.join(yaml))
        assert data == expected

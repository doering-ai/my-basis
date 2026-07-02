############
### HEAD ###
############
### STANDARD
from typing import Any, Literal
from collections.abc import Mapping, Container
from collections import Counter, deque
from datetime import date, time, datetime, timedelta
from enum import Enum
from types import EllipsisType, NoneType

### EXTERNAL
import pytest as pyt
import pydantic as pyd

### INTERNAL
from my.typing import MyType, TypeCheck, typist
from ..conftest import boolmap, type_ids

############
### DATA ###
############
cls = TypeCheck


class Color(Enum):
    """A small enum for atom/struct predicate tests."""

    RED = 1
    GREEN = 2


class Point(pyd.BaseModel):
    """A small model for `is_model` / `is_struct` tests."""

    x: int = 0
    y: int = 0


def sample_fn(a: int, b: str) -> bool:
    """A sample annotated function for `describe_func`."""
    return bool(a) and bool(b)


def union_fn(x: object) -> int | str:
    """A sample function with a union return for `describe_func`."""
    return x  # type: ignore[return-value]


#: The core `check` matrix -- the de-facto spec, exercised through both check surfaces.
CHECK_CASES = boolmap(
    false=[
        # ---- Type mismatches ----
        (1, str),
        ('abc', int),
        (1.5, bool),
        ([1, 2], dict),
        ({'a': 1}, list),
        # ---- Container element mismatches ----
        ([1, 2, 3], list[str]),
        (['a', 'b', 1], list[str]),
        ({'a': 1}, dict[str, str]),
        ({'a': 1}, dict[int, int]),
        ({1: 'a'}, dict[str, str]),
        (Counter(b=2), Mapping[str, str]),
        ({1, 2, 3}, set[str]),
        # ---- Nested mismatches ----
        ([[1, 2], ['a', 'b']], list[list[int]]),
        ([{'a': 1}, {'b': 'c'}], list[dict[str, int]]),
        # ---- Literal mismatches ----
        ('three', Literal['one', 'two']),
        (3, Literal[1, 2]),
        # ---- Tuple literal mismatches ----
        ((1, 'a', 3.0), tuple[int, str]),
        ((1, 2), tuple[int, str]),
        ((1,), tuple[int, int]),
        # ---- None checks ----
        (None, str),
        (None, list),
        (None, list[str]),
        (5, NoneType),
    ],
    true=[
        # ---- Basic types ----
        ('abc', str),
        (123, int),
        (3.14, float),
        (b'bytes', bytes),
        (True, bool),
        # ---- Any and object (always-true wildcards) ----
        ('anything', Any),
        ('anything', object),
        (123, Any),
        (123, object),
        ([1, 2], Any),
        # ---- Lists ----
        (['a', 'b'], list[str]),
        ([1, 2, 3], list),
        ([1, 2, 3], list[int]),
        ([], list[int]),
        # ---- Dicts ----
        ({'a': 1, 'b': 2}, dict[str, int]),
        ({'a': 1}, dict),
        ({1: 'a', 2: 'b'}, dict[int, str]),
        ({}, dict[str, int]),
        # ---- Sets ----
        (set(), set[int]),
        ({'a', 'b'}, set[str]),
        ({1, 2, 3}, set),
        ({1, 2, 3}, set[int]),
        # ---- Mappings ----
        (Counter(a=1), Mapping),
        (Counter(b=2), Mapping[str, int]),
        ({'a': 1}, Mapping[str, int]),
        # ---- Containers ----
        ('abc', Container[str]),
        ([1, 2], Container[int]),
        ({'a': 1}, Container[str]),
        ({1, 2, 3}, Container[int]),
        # ---- Nested structures ----
        ([[1, 2], [3, 4]], list[list[int]]),
        ([{'a': 1}, {'b': 2}], list[dict[str, int]]),
        ({'x': [1, 2], 'y': [3, 4]}, dict[str, list[int]]),
        # ---- Literal matches ----
        ('one', Literal['one', 'two']),
        (2, Literal[1, 2]),
        # ---- Deque ----
        (deque([1, 2, 3]), deque),
        (deque([1, 2, 3]), deque[int]),
        # ---- Special-form sentinels ----
        (Ellipsis, EllipsisType),
        (None, NoneType),
    ],
)


############
### BODY ###
############
class TestCheck:
    """Test suite for the `check` chamber: the `TypeCheck` (`tyc`) qualify layer."""

    # ------------------
    # `*` Primary Methods
    # ------------------
    @pyt.mark.parametrize('data, tvar, expected', CHECK_CASES, ids=type_ids(CHECK_CASES))
    def test_check(self, data, tvar: type, expected: bool):
        """Test `tyc.check` directly against the data/type matrix."""
        assert cls.check(data, tvar) == expected

    @pyt.mark.parametrize('data, tvar, expected', CHECK_CASES, ids=type_ids(CHECK_CASES))
    def test_check__via_mytype(self, data, tvar: type, expected: bool):
        """Test the same matrix through the `MyType.check` delegation surface."""
        assert MyType.parse(tvar).check(data) == expected

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
    def test_check_all(self, data: list, tvar: type, expected: bool):
        """Test `check_all`: every element of an iterable matches the type."""
        assert cls.check_all(data, tvar) == expected

    @pyt.mark.parametrize(
        'data, expected',
        boolmap(
            true=['one', 'two'],
            false=['three', 'four'],
        ),
    )
    def test_is_literal(self, data: str, expected: bool):
        """Test `is_literal` against a `Literal[...]` membership type."""
        tvar = MyType.parse(Literal['one', 'two'])
        assert cls.is_literal(data, tvar) == expected

    # ------------------
    # `*` Public Methods
    # ------------------
    @pyt.mark.parametrize(
        'data, expected',
        boolmap(
            true=[bytearray(b'x'), memoryview(b'x')],
            false=['abc', b'bytes', 1, [1, 2]],
            base_type=tuple,
        ),
    )
    def test_is_stream(self, data, expected: bool):
        """Test `is_stream`: bytearray / memoryview / IO are streams; str and bytes are not."""
        assert cls.is_stream(data) == expected

    @pyt.mark.parametrize(
        'data, expected',
        boolmap(
            true=['abc', b'bytes', bytearray(b'x'), memoryview(b'x')],
            false=[1, 1.5, None],
            base_type=tuple,
        ),
    )
    def test_is_string(self, data, expected: bool):
        """Test `is_string`: str, bytes, and streams all count as strings."""
        assert cls.is_string(data) == expected

    @pyt.mark.parametrize(
        'data, expected',
        boolmap(
            true=[1, 1.5, 1 + 2j, True],
            false=['abc', None, [1]],
            base_type=tuple,
        ),
    )
    def test_is_scalar(self, data, expected: bool):
        """Test `is_scalar`: int / float / complex / bool are scalars."""
        assert cls.is_scalar(data) == expected

    @pyt.mark.parametrize(
        'data, expected',
        boolmap(
            true=[date(2025, 1, 1), time(12, 0), datetime(2025, 1, 1), timedelta(days=1)],
            false=[1, 'abc', None],
            base_type=tuple,
        ),
    )
    def test_is_time(self, data, expected: bool):
        """Test `is_time`: date / time / datetime / timedelta are times."""
        assert cls.is_time(data) == expected

    @pyt.mark.parametrize(
        'data, expected',
        boolmap(
            true=['abc', 1, True, date(2025, 1, 1), Color.RED],
            false=[[1], {'a': 1}, None, (1, 2)],
            base_type=tuple,
        ),
    )
    def test_is_atom(self, data, expected: bool):
        """Test `is_atom`: strings, scalars, times, and enum members are atoms."""
        assert cls.is_atom(data) == expected

    @pyt.mark.parametrize(
        'data, expected',
        boolmap(
            true=[[1, 2], (1, 2), {1, 2}, deque([1]), range(3)],
            false=['abc', {'a': 1}, 1, None],
            base_type=tuple,
        ),
    )
    def test_is_vec(self, data, expected: bool):
        """Test `is_vec`: list / tuple / set / deque / range are vecs; str and dict are not."""
        assert cls.is_vec(data) == expected

    @pyt.mark.parametrize(
        'data, expected',
        boolmap(
            true=[{'a': 1}, Counter(a=1), {'a': 1}.items()],
            false=[[1, 2], [('a', 1)], 'abc', None, int],
            base_type=tuple,
        ),
    )
    def test_is_map(self, data, expected: bool):
        """Test `is_map`: Mappings and ItemsViews are maps; lists of pairs and types are not."""
        assert cls.is_map(data) == expected

    @pyt.mark.parametrize(
        'data, expected',
        boolmap(
            true=[('a', 1), (1, 'x')],
            false=[('a',), ('a', 1, 2), 'ab', [1, 2]],
            base_type=tuple,
        ),
    )
    def test_is_map_item(self, data, expected: bool):
        """Test `is_map_item`: a 2-tuple with a hashable first element is a map item."""
        assert cls.is_map_item(data) == expected

    @pyt.mark.parametrize(
        'data, expected',
        boolmap(
            true=[iter([1, 2]), (x for x in [1])],
            false=['abc', [1, 2], {'a': 1}, 1],
            base_type=tuple,
        ),
    )
    def test_is_iter(self, data, expected: bool):
        """Test `is_iter`: a bare iterable that is not a string, vec, or map."""
        assert cls.is_iter(data) == expected

    @pyt.mark.parametrize(
        'data, expected',
        boolmap(
            true=[[1, 2], {'a': 1}, Point()],
            false=['abc', 1, None],
            base_type=tuple,
        ),
    )
    def test_is_struct(self, data, expected: bool):
        """Test `is_struct`: vecs, maps, and models are structs."""
        assert cls.is_struct(data) == expected

    @pyt.mark.parametrize(
        'data, expected',
        boolmap(
            true=[len, print, sample_fn, lambda x: x],
            false=[1, 'abc', None],
            base_type=tuple,
        ),
    )
    def test_is_func(self, data, expected: bool):
        """Test `is_func`: callables are funcs; plain values are not."""
        assert cls.is_func(data) == expected

    @pyt.mark.parametrize(
        'data, expected',
        boolmap(
            true=[Point(), Point(x=1, y=2)],
            false=[{'a': 1}, 'abc', None, Point],
            base_type=tuple,
        ),
    )
    def test_is_model(self, data, expected: bool):
        """Test `is_model`: model instances are models; the bare class and dicts are not."""
        assert cls.is_model(data) == expected

    def test_describe_func__basic(self):
        """Test `describe_func` extracts parameter names and a single return type."""
        params, returns = cls.describe_func(sample_fn)
        assert set(params) == {'a', 'b'}
        assert len(returns) == 1
        assert returns[0].check(True)

    def test_describe_func__union_return(self):
        """Test `describe_func` splits a union return into one type per member."""
        params, returns = cls.describe_func(union_fn)
        assert set(params) == {'x'}
        assert len(returns) == 2

    # -----------------
    # `*` Facade Methods
    # -----------------
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
        """Test the `typist.all_are` facade: all elements match (relocated from test_Typist)."""
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
        """Test the `typist.any_are` facade: any element matches (relocated from test_Typist)."""
        assert typist.any_are(data, tvar) == expected

############
### HEAD ###
############
### STANDARD
from typing import Any, Literal, Self
from collections.abc import Mapping, Sequence
from collections import Counter, deque
from datetime import date, time, datetime, timedelta
from enum import Enum
from types import NoneType, FunctionType
import collections.abc as abc

### EXTERNAL
import pytest as pyt
import pydantic as pyd

### INTERNAL
from my.types import Buffer, Span
from my.typing import MyType, TypeMatch, typist
from ..conftest import boolmap

############
### DATA ###
############
cls = TypeMatch


class Color(Enum):
    """A small enum for atom-type predicate tests."""

    RED = 1
    GREEN = 2


#: `match` subset cases: `t0` is (not) a subset of `t1`.
MATCH_SUBSET = boolmap(
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
        (Span, tuple[int, int]),
        (Mapping, list[int] | Mapping[str, list[int] | Mapping]),
    ],
)

#: `match` intersection cases: `t0` and `t1` overlap.
MATCH_INTERSECT = boolmap(
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
)

#: `match` nested-generic cases: element types are recursed into.
MATCH_NESTED = boolmap(
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
)

#: `match` wildcard / special-form edge cases. `Any`/bare-`None` are bidirectional wildcards.
MATCH_EDGE = boolmap(
    false=[
        (MyType.parse(Ellipsis), MyType.parse(NoneType)),
        (MyType.parse(NoneType), MyType.parse(Self)),  # DEFERRED: NoneType-vs-Self edge.
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
)


############
### BODY ###
############
class TestMatch:
    """Test suite for the `match` chamber: the `TypeMatch` (`tym`) subset/intersection layer."""

    # ------------------
    # `*` Primary Methods
    # ------------------
    @pyt.mark.parametrize('t0, t1, expected', MATCH_SUBSET)
    def test_match(self, t0, t1, expected: bool):
        """Test `tym.match` subset coverage: is `t0` a subset of `t1`?

        NOTE: the two `Span` cases are a known-deferred edge (needs `Real`->`int` resolution).
        """
        assert cls.match(t0, t1) == expected

    @pyt.mark.parametrize('t0, t1, expected', MATCH_INTERSECT)
    def test_match__intersect(self, t0, t1, expected: bool):
        """Test `tym.match(..., intersect=True)`: do `t0` and `t1` overlap?"""
        assert cls.match(t0, t1, intersect=True) == expected

    @pyt.mark.parametrize('t0, t1, expected', MATCH_NESTED)
    def test_match__nested(self, t0, t1, expected: bool):
        """Test `tym.match` recursing into nested generic element types."""
        assert cls.match(t0, t1) == expected

    @pyt.mark.parametrize('t0, t1, expected', MATCH_EDGE)
    def test_match__edge(self, t0, t1, expected: bool):
        """Test `tym.match` wildcard semantics for `Any`/`None`.

        NOTE: `(NoneType, Self)` is a known-deferred edge (currently matches True).
        """
        assert cls.match(t0, t1) == expected

    def test_is_map_item_type(self):
        """Test `is_map_item_type`: a 2-tuple (or bare `tuple`) of hashable-keyed pairs."""
        assert cls.is_map_item_type(tuple[str, int]) is True
        assert cls.is_map_item_type(tuple) is True
        assert cls.is_map_item_type(tuple[int, str, float]) is False
        assert cls.is_map_item_type(list) is False

    # -------------------
    # `*` Type Predicates
    # -------------------
    @pyt.mark.parametrize(
        'tvar, expected',
        boolmap(true=[bytearray, memoryview], false=[str, bytes, int, list], base_type=tuple),
    )
    def test_is_stream_type(self, tvar, expected: bool):
        """Test `is_stream_type`: bytearray / memoryview / IO; not str or bytes."""
        assert cls.is_stream_type(tvar) == expected

    @pyt.mark.parametrize(
        'tvar, expected',
        boolmap(true=[str, bytes, bytearray, memoryview], false=[int, list, dict], base_type=tuple),
    )
    def test_is_string_type(self, tvar, expected: bool):
        """Test `is_string_type`: str, bytes, and stream types."""
        assert cls.is_string_type(tvar) == expected

    @pyt.mark.parametrize(
        'tvar, expected',
        boolmap(true=[int, float, complex, bool], false=[str, list, type(None)], base_type=tuple),
    )
    def test_is_scalar_type(self, tvar, expected: bool):
        """Test `is_scalar_type`: int / float / complex / bool."""
        assert cls.is_scalar_type(tvar) == expected

    @pyt.mark.parametrize(
        'tvar, expected',
        boolmap(true=[date, time, datetime, timedelta], false=[int, str, list], base_type=tuple),
    )
    def test_is_time_type(self, tvar, expected: bool):
        """Test `is_time_type`: date / time / datetime / timedelta."""
        assert cls.is_time_type(tvar) == expected

    @pyt.mark.parametrize(
        'tvar, expected',
        boolmap(true=[str, int, bool, date, Color], false=[list, dict, set], base_type=tuple),
    )
    def test_is_atom_type(self, tvar, expected: bool):
        """Test `is_atom_type`: string / scalar / time / enum types."""
        assert cls.is_atom_type(tvar) == expected

    @pyt.mark.parametrize(
        'tvar, expected',
        boolmap(true=[list, tuple, set, deque], false=[str, dict, int], base_type=tuple),
    )
    def test_is_vec_type(self, tvar, expected: bool):
        """Test `is_vec_type`: list / tuple / set / deque; not str or dict."""
        assert cls.is_vec_type(tvar) == expected

    @pyt.mark.parametrize(
        'tvar, expected',
        boolmap(true=[list, dict, tuple], false=[int, type(None)], base_type=tuple),
    )
    def test_is_struct_type(self, tvar, expected: bool):
        """Test `is_struct_type`: vec / map / model (iterable or model) types."""
        assert cls.is_struct_type(tvar) == expected

    @pyt.mark.parametrize(
        'tvar, expected',
        boolmap(true=[FunctionType, type(len)], false=[int, str, list], base_type=tuple),
    )
    def test_is_func_type(self, tvar, expected: bool):
        """Test `is_func_type`: function / builtin types; not plain values' types."""
        assert cls.is_func_type(tvar) == expected

    @pyt.mark.parametrize(
        'tvar, expected',
        boolmap(true=[pyd.BaseModel], false=[dict, str, int], base_type=tuple),
    )
    def test_is_model_type(self, tvar, expected: bool):
        """Test `is_model_type`: pydantic models / dataclasses / TypedDicts."""
        assert cls.is_model_type(tvar) == expected

    # --------------------------------
    # `*` Deferred Predicates (to cast)
    # --------------------------------
    @pyt.mark.xfail(
        reason='is_map_type does `issubclass(main, Map)` against a subscripted union (TypeError); '
        'a working fix unmasks an infinite `_model_to_map` recursion -- fix in the cast chamber.',
    )
    @pyt.mark.parametrize(
        'tvar, expected',
        boolmap(true=[dict, Counter, abc.Mapping], false=[list, str, int], base_type=tuple),
    )
    def test_is_map_type(self, tvar, expected: bool):
        """Test `is_map_type`: Mapping / ItemsView / pair-iterable types (currently broken)."""
        assert cls.is_map_type(tvar) == expected

    @pyt.mark.xfail(
        reason='is_iter_type crashes via is_map_type (subscripted-union TypeError) -- '
        'fix in the cast chamber with is_map_type.',
    )
    @pyt.mark.parametrize(
        'tvar, expected',
        boolmap(true=[abc.Iterable, abc.Collection], false=[dict], base_type=tuple),
    )
    def test_is_iter_type(self, tvar, expected: bool):
        """Test `is_iter_type`: a non-string, non-vec, non-map Iterable type (currently broken)."""
        assert cls.is_iter_type(tvar) == expected

    # -----------------
    # `*` Facade Methods
    # -----------------
    @pyt.mark.parametrize(
        'lhs, rhs, expected',
        boolmap(
            false=[('abc', 123), ([1], {1})],
            true=[('abc', 'def'), (1, 2), ([1], [2, 3])],
        ),
    )
    def test_match_instances(self, lhs, rhs, expected: bool):
        """Test the `typist.match_instances` facade: do two values share a matching type?"""
        assert typist.match_instances(lhs, rhs) == expected

    @pyt.mark.parametrize(
        't0, t1, expected',
        boolmap(
            false=[(str, int), (int, list[str])],
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
        """Test the `typist.seek_usage` facade: is `t0` used anywhere within `t1`'s structure?"""
        assert typist.seek_usage(t0, t1) == expected

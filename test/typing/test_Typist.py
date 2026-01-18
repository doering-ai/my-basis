############
### HEAD ###
############
### STANDARD
from typing import Any, Literal
from collections.abc import (
    Iterable,
    Mapping,
    Callable,
    Container,
    Collection,
    Sequence,
)
from collections import Counter, deque
from datetime import date, datetime, time, timedelta, UTC

### EXTERNAL
import pytest as pyt
import pydantic as pyd

### INTERNAL
from my.infra import Time
from my.types import Buffer, Span
from my.regex import MatchData
from my.typing import Typist, TypeArg
from ..conftest import boolmap

############
### DATA ###
############
typist = Typist(firsts=True, atomics=True, splits=True)


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
        "data, expected",
        [
            (["abc", "cde", "efg"], ["abc", "cde", "efg"]),
            (["1", "22", "-33"], [1, 22, -33]),
            (["1", "22.0", "-33"], [1.0, 22.0, -33.0]),
            (["true", "YES", "n", "FaLsE"], [True, True, False, False]),
            (["true", "1", "2.0"], [True, 1, 2.0]),
        ],
    )
    def test_flex_deserialize(self, data: list[str], expected: list):
        assert typist.flex_deserialize(data) == expected

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
        "t0, t1, expected",
        boolmap(
            false=[
                (Sequence, str),
                (int, list[int]),
                (str, Buffer),
                (Span, tuple[int, str]),
                (Span, tuple[str, ...]),
                (str | int, dict | int),
                (str | dict | int, str | int),
                (list[int] | Mapping, Mapping),
                (Literal["A", "B"], Literal["A"]),
            ],
            true=[
                (str, str),
                (str, Sequence),
                (str | int, str | dict | int),
                (Counter, Mapping),
                (Typist, pyd.BaseModel),
                (Span, tuple[int, int]),
                (Mapping, list[int] | Mapping),
                (Mapping, list[int] | Mapping[str, list[int] | Mapping]),
                (Literal["A"], Literal["A", "B"]),
            ],
        ),
    )
    def test_match_basic(self, t0, t1, expected: bool):
        assert typist.match(t0, t1) == expected

    @pyt.mark.parametrize(
        "t0, t1, expected",
        boolmap(
            false=[
                (Span, tuple[int, ...]),
            ],
            true=[
                (str | int, dict | int),
                (str | int, str | dict | int),
                (str | dict | int, str | int),
                (str | Mapping, Mapping),
            ],
        ),
    )
    def test_match_intersect(self, t0, t1, expected: bool):
        assert typist.match(t0, t1, intersect=True) == expected

    # -----------
    # CHECK TESTS
    # -----------
    @pyt.mark.parametrize(
        "data, tvar, expected",
        [
            ("abc", str, True),
            (1, str, False),
            (Counter(a=1), Mapping, True),
            (Counter(b=2), Mapping[str, int], True),
            (Counter(b=2), Mapping[str, str], False),
            (dict(a=1), Container[str], True),
        ],
    )
    def test_check(self, data: Iterable, tvar: type, expected: bool):
        assert typist.check(data, tvar) == expected

    # -------------
    # `*2` COERCION
    # -------------
    @pyt.mark.parametrize(
        "data, target, expected",
        [
            (["1", "5", "10"], Sequence[str], ["1", "5", "10"]),
            (["1", "5", "10"], Sequence[int], [1, 5, 10]),
            ({"1", "5", "10"}, Collection[int], {1, 5, 10}),
            (deque(["1", "5.5", "10"]), set[float], {1.0, 5.5, 10.0}),
            (["1", "5", "10"], tuple[int], (1, 5, 10)),
        ],
    )
    def test_cast(self, data: Any, target: type, expected: object):
        assert typist.cast(data, target) == expected

    @pyt.mark.parametrize(
        "data, target, expected",
        [
            (["1", "2", "3"], tuple[int, ...], (1, 2, 3)),
            (["a", "1", "b", "2"], tuple[str, int, str, int], ("a", 1, "b", 2)),
            (["123", "456"], Span, Span((123, 456))),  # tuple subtype
        ],
    )
    def test_cast__tuples(self, data: Any, target: type, expected: object):
        assert typist.cast(data, target) == expected

    @pyt.mark.parametrize(
        "data, target, expected",
        [
            (dict(x=20.0), dict[str, int], dict(x=20)),
            (Counter(z=15), dict[str, int], dict(z=15)),
            (
                [("a", "1"), ("b", "5"), ("c", "10")],
                dict[str, int],
                dict(a=1, b=5, c=10),
            ),
            ([("a", "1"), ("b", "2")], Counter[str], Counter(a=1, b=2)),
            (["a", "b", "b"], Counter, Counter(a=1, b=2)),
            (
                ["a.b.c", "x.y.z", "a.b.c"],
                Counter[tuple[str, ...]],
                Counter({("a", "b", "c"): 2, ("x", "y", "z"): 1}),
            ),
        ],
    )
    def test_cast__maps(self, data: Any, target: type, expected: object):
        assert typist.cast(data, target) == expected

    @pyt.mark.parametrize(
        "data, target, expected",
        [
            ("a", Buffer, Buffer.new("a")),
            (
                dict(a=1, child=dict(b=2, c=3)),
                MatchData,
                MatchData.new({"a": ["1"], "child.b": ["2"], "child.c": ["3"]}),
            ),
        ],
    )
    def test_cast__models(self, data: Any, target: type, expected: object):
        assert typist.cast(data, target) == expected

    @pyt.mark.parametrize(
        "data, target, expected",
        [
            # <- -> str
            (date(1970, 2, 1), str, "1970-02-01"),
            (datetime(1970, 2, 1, 10, 20, 30, tzinfo=UTC), str, "1970-02-01T10:20:30"),
            (time(hour=10, minute=20, second=30, tzinfo=UTC), str, "10:20:30"),
            (timedelta(days=1, hours=1, minutes=1), str, "1 day, 1:01:00"),
            # <- -> int
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
        "data, target, expected",
        [
            # Container <-.-> Atomic
            ("1", tuple[int], (1,)),
            (["1"], int, 1),
            (["1", "2"], int, 1),
            ("abc, cde. efg!", list[str], ["abc", "cde. efg!"]),
            ("transformers, safetensors", set[str], {"transformers", "safetensors"}),
            # Malformed times
            ("25-07-02", datetime, datetime(2025, 7, 2, tzinfo=UTC)),
            (
                "25-07-02T10:20:30",
                datetime,
                datetime(2025, 7, 2, 10, 20, 30, tzinfo=UTC),
            ),
        ],
    )
    def test_cast__edge(self, data: list, target: type, expected: object):
        assert typist.cast(data, target) == expected

    # -------------------
    # `*3` TRANSFORMATION
    # -------------------
    @pyt.mark.parametrize(
        "data, kwargs, expected",
        [
            ("5", dict(), "5"),
            (5, dict(), 5),
            ([5], dict(), [5]),
            (Buffer.new("5"), dict(), "5"),
        ],
    )
    def test_serialize(self, data: object, kwargs: dict, expected: Any):
        assert typist.serialize(data, **kwargs) == expected

    @pyt.mark.parametrize(
        "models, expected",
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
        "models, expected, remaining",
        [
            # Main case
            (
                [
                    dict(a=dict(aa=[3]), b="8"),
                    dict(a=dict(aa=[3, 4, 5], ab="7"), b="8"),
                ],
                dict(a=dict(aa=[3]), b="8"),
                [
                    dict(),
                    dict(a=dict(aa=[4, 5], ab="7")),
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
        "data, expected",
        [
            (dict(a=1, b=2, c=3), ["a: 1", "b: 2", "c: 3"]),
            (
                dict(a=1, b=dict(b0=2, c=dict(c0=3))),
                ["a: 1", "b:", "    b0: 2", "    c:", "        c0: 3"],
            ),
            (
                dict(a=1, list=[2, dict(b=3, c=dict(d=4)), 5]),
                [
                    "a: 1",
                    "list:",
                    "    - 2",
                    "    - b: 3",
                    "      c:",
                    "          d: 4",
                    "    - 5",
                ],
            ),
            ([dict(a=1, x=9)], ["- a: 1", "  x: 9"]),
            (
                [dict(a=1, x=9), dict(b=2, y=8), (dict(c=3, z=7))],
                ["- a: 1", "  x: 9", "- b: 2", "  y: 8", "- c: 3", "  z: 7"],
            ),
            (["one", "two", "three"], ["- one", "- two", "- three"]),
            (
                ["one", ["two", ["three"]]],
                ["- one", "-     - two", "      -     - three"],
            ),
            ([1, Buffer.new("[two]"), "three"], ["- 1", "- '[two]'", "- three"]),
            ([dict(a=1, b=2), "two", 3], ["- a: 1", "  b: 2", "- two", "- 3"]),
            (
                dict(one=1, two="two", three=["a", "b", "c"]),
                ["one: 1", "two: two", "three:", "    - a", "    - b", "    - c"],
            ),
        ],
    )
    def test_to_yaml(self, data: Any, expected: list[str]):
        yaml = typist.to_yaml(data).strip("\n")
        assert yaml == "\n".join(expected)

    @pyt.mark.parametrize(
        "yaml, expected",
        [
            (["- 1", "- '[two]'", "- three"], [1, "[two]", "three"]),
            (["- a: 1", "  b: 2", "- two", "- 3"], [dict(a=1, b=2), "two", 3]),
            (
                ["one: 1", "two: two", "three: [a, b, c]"],
                dict(one=1, two="two", three=["a", "b", "c"]),
            ),
        ],
    )
    def test_from_yaml(self, yaml: list[str], expected: Any):
        data = typist.from_yaml("\n".join(yaml))
        assert data == expected

    # ---------------
    # `*5` INVOCATION
    # ---------------
    # Test helper functions for invocable/invoke
    @staticmethod
    def _func_no_params() -> str:
        return "no params"

    @staticmethod
    def _func_one_pos(x: int) -> int:
        return x * 2

    @staticmethod
    def _func_one_pos_default(x: int = 5) -> int:
        return x * 2

    @staticmethod
    def _func_two_pos(x: int, y: str) -> str:
        return f"{x}: {y}"

    @staticmethod
    def _func_pos_and_kwonly(x: int, *, y: str) -> str:
        return f"{x}: {y}"

    @staticmethod
    def _func_with_varargs(*args: int) -> int:
        return sum(args)

    @staticmethod
    def _func_with_kwargs(**kwargs: Any) -> dict:
        return kwargs

    @staticmethod
    def _func_mixed(a: int, b: str = "default", *args: int, **kwargs: Any) -> tuple:
        return (a, b, args, kwargs)

    @staticmethod
    def _func_pos_only(x: int, /) -> int:
        return x * 2

    @pyt.mark.parametrize(
        "func, args, kwargs, expected_success",
        [
            # No params
            (_func_no_params, (), {}, True),
            (_func_no_params, (1,), {}, False),  # Extra arg
            # One positional
            (_func_one_pos, (5,), {}, True),
            (_func_one_pos, (), {}, False),  # Missing required
            (_func_one_pos, (), {"x": 5}, True),  # As kwarg
            (_func_one_pos, (5, 6), {}, False),  # Too many args
            # One positional with default
            (_func_one_pos_default, (), {}, True),
            (_func_one_pos_default, (10,), {}, True),
            (_func_one_pos_default, (), {"x": 10}, True),
            # Two positional
            (_func_two_pos, (1, "hi"), {}, True),
            (_func_two_pos, (1,), {"y": "hi"}, True),
            (_func_two_pos, (), {"x": 1, "y": "hi"}, True),
            (_func_two_pos, (1,), {}, False),  # Missing y
            (_func_two_pos, (1, 2), {}, False),  # Wrong type for y
            # Positional and keyword-only
            (_func_pos_and_kwonly, (1,), {"y": "hi"}, True),
            (_func_pos_and_kwonly, (1, "hi"), {}, False),  # y must be kwarg
            (_func_pos_and_kwonly, (), {"x": 1, "y": "hi"}, True),
            # Varargs
            (_func_with_varargs, (1, 2, 3), {}, True),
            (_func_with_varargs, (), {}, True),  # Empty varargs ok
            # Kwargs
            (_func_with_kwargs, (), {"a": 1, "b": 2}, True),
            (_func_with_kwargs, (), {}, True),  # Empty kwargs ok
            (_func_with_kwargs, (1,), {}, False),  # No positional params
            # Mixed
            (_func_mixed, (5,), {}, True),
            (_func_mixed, (5, "custom"), {}, True),
            (_func_mixed, (5, "custom", 1, 2), {"z": 3}, True),
            (_func_mixed, (), {}, False),  # Missing required 'a'
            # Positional-only
            (_func_pos_only, (5,), {}, True),
            (_func_pos_only, (), {"x": 5}, False),  # x is positional-only
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
            assert result is not None, (
                f"Expected {func} to accept args={args}, kwargs={kwargs}"
            )
            # Result should be a tuple of (args, kwargs)
            assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
            assert len(result) == 2, f"Expected tuple of length 2, got {len(result)}"
        else:
            assert result is None, (
                f"Expected {func} to reject args={args}, kwargs={kwargs}"
            )

    @pyt.mark.parametrize(
        "func, args, kwargs, expected_result",
        [
            # No params
            (_func_no_params, (), {}, "no params"),
            # One positional
            (_func_one_pos, (5,), {}, 10),
            (_func_one_pos, (), {"x": 5}, 10),
            # One positional with default
            (_func_one_pos_default, (), {}, 10),  # Uses default 5 * 2
            (_func_one_pos_default, (7,), {}, 14),
            # Two positional
            (_func_two_pos, (42, "answer"), {}, "42: answer"),
            (_func_two_pos, (42,), {"y": "answer"}, "42: answer"),
            (_func_two_pos, (), {"x": 42, "y": "answer"}, "42: answer"),
            # Positional and keyword-only
            (_func_pos_and_kwonly, (1,), {"y": "test"}, "1: test"),
            # Varargs
            (_func_with_varargs, (1, 2, 3, 4), {}, 10),
            (_func_with_varargs, (), {}, 0),
            # Kwargs
            (_func_with_kwargs, (), {"a": 1, "b": 2}, {"a": 1, "b": 2}),
            (_func_with_kwargs, (), {}, {}),
            # Mixed
            (_func_mixed, (5,), {}, (5, "default", (), {})),
            (_func_mixed, (5, "custom"), {}, (5, "custom", (), {})),
            (
                _func_mixed,
                (5, "custom", 1, 2),
                {"z": 3},
                (5, "custom", (1, 2), {"z": 3}),
            ),
            # Positional-only
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
        success, result = typist.invoke(func, *args, **kwargs)
        assert success, f"Expected {func} to succeed with args={args}, kwargs={kwargs}"
        assert result == expected_result, f"Expected {expected_result}, got {result}"

    @pyt.mark.parametrize(
        "func, args, kwargs",
        [
            (_func_one_pos, (), {}),  # Missing required
            (_func_one_pos, (1, 2), {}),  # Too many args
            (_func_two_pos, (1,), {}),  # Missing required
            (_func_pos_and_kwonly, (1, "hi"), {}),  # y must be kwarg
            (_func_with_kwargs, (1,), {}),  # No positional params
            (_func_pos_only, (), {"x": 5}),  # x is positional-only
        ],
    )
    def test_invoke_failure(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
    ):
        success, result = typist.invoke(func, *args, **kwargs)
        assert not success, f"Expected {func} to fail with args={args}, kwargs={kwargs}"
        assert result is None, f"Expected None result on failure, got {result}"

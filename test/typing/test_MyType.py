############
### HEAD ###
############
### STANDARD
import typing
from typing import Any, Literal, Optional, TypeGuard, Annotated, Union, Unpack
from collections.abc import (
    Mapping,
    Callable,
    Container,
    Coroutine,
    Sequence,
    Generator,
)
from collections import Counter, deque
from datetime import date, datetime, time, timedelta, UTC
from enum import Enum

### EXTERNAL
import pytest as pyt
import pydantic as pyd

### INTERNAL
from my.types import Buffer, Span
from my.typing import MyType
from my.regex import GroupKind
from ..conftest import boolmap

############
### DATA ###
############
cls = MyType

Expected = tuple[type, ...] | type | None


class BaseEnum(Enum):
    A = 1
    B = 2


T = typing.TypeVar("T")
Ts = typing.TypeVarTuple("Ts")


############
### BODY ###
############
class TestMyType:
    # ------------
    # TEST HELPERS
    # ------------
    def check_inst(self, inst: MyType | None, exp: Expected):
        if exp is None:
            assert not inst
            return
        assert inst is not None
        if isinstance(exp, type):
            exp = (exp,)

        if len(exp) == 1:
            assert inst.main_type is exp[0]
            assert not inst.val_type
            assert not inst.key_type
        if len(exp) == 2:
            assert inst.main_type is exp[0]
            self.check_inst(inst.val_type, exp[1])
            assert not inst.key_type
        elif len(exp) == 3:
            assert inst.main_type is exp[0]
            self.check_inst(inst.key_type, exp[1])
            self.check_inst(inst.val_type, exp[2])

    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyt.mark.parametrize(
        "data",
        [
            int,
            str,
            float,
            bool,
            bytes,
            date,
            time,
            datetime,
            timedelta,
            BaseEnum,
            GroupKind,
            # Classes aren't technically atomic, but are the same for this purpose
            Buffer,
            MyType,
        ],
    )
    def test_parse_atomic(self, data):
        inst = cls.parse(data)
        assert inst.main_type is data
        assert len(inst.args) == 0
        assert bool(inst)

    @pyt.mark.parametrize(
        "data, expected",
        [
            # Sequences
            (tuple, tuple),
            (tuple[str, ...], (tuple, str)),
            (set, set),
            (set[str], (set, str)),
            (deque[str], (deque, str)),
            # Maps
            (dict, dict),
            (dict[str, int], (dict, str, int)),
            (dict[str, Any], (dict, str, None)),
            (dict[str, list[str]], (dict, str, (list, str))),
            # Wrappers
            (Optional[str], str),
            (Annotated[list[int], 5], (list, int)),
            (Annotated[list[int], dict[int, int]], (list, int)),
            (Counter[str], (Counter, str, int)),
            (Counter, (Counter, None, int)),
        ],
    )
    def test_parse_generic(self, data, expected: Expected):
        inst = cls.parse(data)
        self.check_inst(inst, expected)

    @pyt.mark.parametrize(
        "data, expected, test_vals",
        [
            (
                Literal["one", "two"],
                [str],
                dict(true=["two", "one"], false=["three", "ONE", 5]),
            ),
            (
                Literal["one", 2, "three"],
                [str, int],
                dict(true=["one", 2, "three"], false=["four", 3, "ONE"]),
            ),
            (
                tuple[int],
                [int],
                dict(true=[(1,), (0,)], false=[(1, "a"), ("a",), ()]),
            ),
            (
                tuple[str, str],
                [str, str],
                dict(true=[("a", "b"), ("", "")], false=[("a", 1), ("a",), ()]),
            ),
            (
                tuple[int, str, float],
                [int, str, float],
                dict(
                    true=[(1, "a", 3.0), (0, "", -1.5)], false=[(1, "a"), (1, 2, 3), ()]
                ),
            ),
            (
                Span,
                [int, int],
                dict(true=[Span(1, 5), Span(0, 0)], false=[(1, 5), (1,), ()]),
            ),
        ],
    )
    def test_parse_literal(
        self, data, expected: list[type], test_vals: dict[str, list]
    ):
        inst = cls.parse(data)

        if inst.origin is Literal:
            assert inst.main_type is None
            assert set(arg.src_type for arg in inst.args) == set(expected)
        elif inst.origin is not None and issubclass(inst.origin, tuple):
            assert inst.main_type == inst.origin
            assert list(arg.src_type for arg in inst.args) == expected
        else:
            assert False, f"{inst=!r} is invalid."

        assert inst.literal_check is not None
        for val in test_vals.get("true", []):
            assert inst.literal_check(val)
        for val in test_vals.get("false", []):
            assert not inst.literal_check(val)

    @pyt.mark.parametrize(
        "data, expected",
        [
            # Oldschool _SpecialForm::Union
            (Union[dict[str, int], int], [(dict, str, int), int]),
            # Modern UnionType
            (dict[str, int] | int, [(dict, str, int), int]),
            (Coroutine | dict[str, int] | int, [None, (dict, str, int), int]),
            (Coroutine | Generator, [None, None]),
            # Super new TypeTuples (idiomatically speaking)
            ((dict[str, int], int), [(dict, str, int), int]),
            # Unpack isn't technically split, but is handled whenever nested by _process_args
            (Unpack[tuple[dict[str, int], int]], [(dict, str, int), int]),
        ],
    )
    def test_parse_split(self, data, expected: list[Expected]):
        inst = cls.parse(data)
        for arg, exp in zip(inst.args, expected, strict=True):
            self.check_inst(arg, exp)

    @pyt.mark.parametrize(
        "data, expected",
        [
            (typing.Mapping, Mapping),
            (typing.Mapping[int, Any], (Mapping, int, None)),
            (typing.Mapping[int, str], (Mapping, int, str)),
            (typing.Sequence, Sequence),
            (typing.Sequence[str], (Sequence, str)),
            (typing.Sequence[Any], Sequence),
        ],
    )
    def test_parse_abstract(self, data, expected: Expected):
        inst = cls.parse(data)
        self.check_inst(inst, expected)

    @pyt.mark.parametrize(
        "data",
        [
            None,
            Any,
            Callable,
            Callable[[int, ...], str],
            TypeGuard[str],
            Coroutine,
            Annotated,
            Literal,
            Generator,
            Generator[int, None, float],
        ],
    )
    def test_parse_unhandled(self, data):
        inst = cls.parse(data)
        assert not inst
        assert inst.main_type is None

    # -------------------
    # `-` Private Methods
    # -------------------

    # -------------------
    # `+` Primary Methods
    # -------------------
    # TEST_DECOMPOSE_UNION:
    #     "tvar, expected",
    #     [
    #         (int, None),
    #         (list[int], None),
    #         (int | str, (int, str)),
    #         (list[int] | Mapping, (list[int], Mapping)),
    #         (Union[list[int], Mapping], (list[int], Mapping)),
    #     ],
    # )

    # ------------------
    # `*` Public Methods
    # ------------------
    @pyt.mark.parametrize(
        "data, tvar, expected",
        boolmap(
            false=[
                (1, str),
                (Counter(b=2), Mapping[str, str]),
            ],
            true=[
                ("abc", str),
                (Counter(a=1), Mapping),
                (Counter(b=2), Mapping[str, int]),
                (dict(a=1), Container[str]),
            ],
        ),
    )
    def test_check(self, data, tvar: type, expected: bool):
        assert cls.parse(tvar).check(data) == expected

############
### HEAD ###
############
### STANDARD
import typing
from typing import Any, Literal, Optional, TypeGuard, Annotated, Union, Unpack
import types
from collections.abc import (
    Mapping,
    Callable,
    Container,
    Coroutine,
    Sequence,
    Generator,
)
from collections import Counter, deque
from datetime import date, datetime, time, timedelta
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

Expected = type | tuple[type, ...] | None


class BaseEnum(Enum):
    """Test class for basic Enums."""

    A = 1
    B = 2


############
### BODY ###
############
class TestMyType:
    """Test MyType."""

    # ------------
    # TEST HELPERS
    # ------------
    def check_inst(self, inst: MyType | None, exp: Expected):
        """Helper method for checking expectations against an instance."""
        # I.i. Handle expectations of failure and invalid instances
        if exp is None:
            assert inst is None
            return
        else:
            assert inst is not None

        # I.ii. Normalize to a tuple of types
        if not isinstance(exp, tuple):
            exp = (exp,)

        if inst.is_split:
            # II.i. For split types, the args should match the expected types
            assert len(exp) == 1
            found_args = {arg.root for arg in inst.args}
            exp_union_args = {arg.root for arg in cls.parse(exp[0]).args}
            assert found_args == exp_union_args
        elif len(exp) == 1:
            # II.ii. For non-split types, the main should match the expected type and there should
            # be no args
            assert inst.main is exp[0]
            assert not inst.vals
            assert not inst.keys
        elif len(exp) == 2:
            assert inst.main is exp[0]
            self.check_inst(inst.vals, exp[1])
            assert not inst.keys
        elif len(exp) == 3:
            assert inst.main is exp[0]
            self.check_inst(inst.keys, exp[1])
            self.check_inst(inst.vals, exp[2])

    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyt.mark.parametrize(
        'data',
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
    def test_parse__atomic(self, data):
        inst = cls.parse(data)
        assert inst.main is data
        assert len(inst.args) == 0
        assert bool(inst)

    @pyt.mark.parametrize(
        'data, expected',
        [
            # ---- Sequences ----
            (tuple, tuple),
            (tuple[str, ...], (tuple, str)),
            (set, set),
            (set[str], (set, str)),
            (deque[str], (deque, str)),
            (list[int], (list, int)),
            (list[str], (list, str)),
            (frozenset[int], (frozenset, int)),
            # ---- Maps ----
            (dict, dict),
            (dict[str, int], (dict, str, int)),
            (dict[str, Any], (dict, str, None)),
            (dict[str, list[str]], (dict, str, (list, str))),
            (dict[int, dict[str, float]], (dict, int, (dict, str, float))),
            (Mapping[str, int], (Mapping, str, int)),
            (Counter[str], (Counter, str, int)),
            (Counter, (Counter, None, int)),
            # ---- Wrappers ----
            (Annotated[list[int], None], (list, int)),
            (Annotated[list[int], 5], (list, int)),
            (Annotated[list[int], dict[int, int], 5], (list, int)),
            (Annotated[str, 'metadata'], str),
            (Unpack[tuple[dict[str, int], int]], [(dict, str, int), int]),
            # ---- Nested generics ----
            (list[list[int]], (list, (list, int))),
            (dict[str, list[int]], (dict, str, (list, int))),
            (set[tuple[str, ...]], (set, (tuple, str))),
            (list[dict[str, int]], (list, (dict, str, int))),
        ],
    )
    def test_parse__generic(self, data, expected: Expected):
        inst = cls.parse(data)
        self.check_inst(inst, expected)

    @pyt.mark.parametrize(
        'data, expected, test_vals',
        [
            (
                Literal['one', 'two'],
                [str],
                dict(true=['two', 'one'], false=['three', 'ONE', 5]),
            ),
            (
                Literal['one', 2, 'three'],
                [str, int],
                dict(true=['one', 2, 'three'], false=['four', 3, 'ONE']),
            ),
            (
                Literal[1, 2, 3],
                [int],
                dict(true=[1, 2, 3], false=[0, 4, '1']),
            ),
            (
                Literal[True, False],
                [bool],
                dict(true=[True, False, 1, 0], false=[2, -1, 'True']),
            ),
            (
                Literal['x'],
                [str],
                dict(true=['x'], false=['X', 'y', '']),
            ),
            (
                tuple[int],
                [int],
                dict(true=[(1,), (0,)], false=[(1, 'a'), ('a',), ()]),
            ),
            (
                tuple[str, str],
                [str, str],
                dict(true=[('a', 'b'), ('', '')], false=[('a', 1), ('a',), ()]),
            ),
            (
                tuple[int, str, float],
                [int, str, float],
                dict(true=[(1, 'a', 3.0), (0, '', -1.5)], false=[(1, 'a'), (1, 2, 3), ()]),
            ),
            (
                tuple[str, int, bool, float],
                [str, int, bool, float],
                dict(
                    true=[('x', 1, True, 2.5)],
                    false=[('x', 1, True), (1, 'x', True, 2.5), ()],
                ),
            ),
            (
                Span,
                [int, int],
                dict(true=[Span(1, 5), Span(0, 0)], false=[(1, 5), (1,), ()]),
            ),
        ],
    )
    def test_parse__literal(self, data, expected: list[type], test_vals: dict[str, list]):
        inst = cls.parse(data)

        if inst.origin is Literal:
            assert inst.main is None
            assert {arg.root for arg in inst.args} == set(expected)
        elif inst.origin is not None and issubclass(inst.origin, tuple):
            assert inst.main == inst.origin
            assert [arg.root for arg in inst.args] == expected
        else:
            pyt.fail(f'{inst!r} is invalid.')

        assert inst.literal_check is not None
        for val in test_vals.get('true', []):
            assert inst.literal_check(val)
        for val in test_vals.get('false', []):
            assert not inst.literal_check(val)

    @pyt.mark.parametrize(
        'data, expected',
        [
            # ---- Oldschool _SpecialForm::Union ----
            (Union[str, int, float], [str, int, float]),
            (Union[dict[str, int], int], [(dict, str, int), int]),
            (Union[list[str], dict[str, int]], [(list, str), (dict, str, int)]),
            # ---- Modern UnionType ----
            (dict[str, int] | int, [(dict, str, int), int]),
            (str | int | float, [str, int, float]),
            (list[int] | set[str], [(list, int), (set, str)]),
            (Coroutine | dict[str, int] | int, [None, (dict, str, int), int]),
            (Coroutine | Generator, [None, None]),
            # ---- Super new TypeTuples (idiomatically speaking) ----
            ((str, int, float), [str, int, float]),
            ((dict[str, int], int), [(dict, str, int), int]),
            # ---- Complex unions with nested generics ----
            (Optional[str], [str, None]),  # noqa: UP045
            (Optional[list[int]], [(list, int), None]),  # noqa: UP045
            (list[int] | dict[str, list[int]], [(list, int), (dict, str, (list, int))]),
        ],
    )
    def test_parse__split(self, data, expected: list[Expected]):
        inst = cls.parse(data)
        assert inst.is_split
        for arg, exp in zip(inst.args, expected, strict=True):
            self.check_inst(arg, exp)

    @pyt.mark.parametrize(
        'data, expected',
        [
            (typing.Mapping, Mapping),
            (typing.Mapping[int, Any], (Mapping, int, None)),
            (typing.Mapping[int, str], (Mapping, int, str)),
            (typing.Sequence, Sequence),
            (typing.Sequence[str], (Sequence, str)),
            (typing.Sequence[Any], Sequence),
        ],
    )
    def test_parse__abstract(self, data, expected: Expected):
        inst = cls.parse(data)
        self.check_inst(inst, expected)

    @pyt.mark.parametrize(
        'data',
        [
            None,
            Any,
            Callable,
            Callable[[int, ...], str],  # type: ignore
            TypeGuard[str],
            Coroutine,
            Annotated,
            Literal,
            Generator,
            Generator[int, None, float],
        ],
    )
    def test_parse__unhandled(self, data):
        inst = cls.parse(data)
        assert not inst
        assert inst.main is None

    @pyt.mark.parametrize(
        'data, expected',
        [
            # ---- Atomic types ----
            (42, int),
            ('hello', str),
            (3.14, float),
            (True, bool),
            (b'bytes', bytes),
            (date(2024, 1, 1), date),
            (datetime(2024, 1, 1, 12, 0, 0), datetime),
            (time(12, 0, 0), time),
            (timedelta(days=1), timedelta),
            (BaseEnum.A, BaseEnum),
            # ---- Empty containers ----
            ([], list),
            ({}, dict),
            (set(), set),
            (tuple(), tuple),
            (deque(), deque),
            (Counter(), (Counter, None, int)),
            # ---- Homogeneous lists ----
            ([1, 2, 3], (list, int)),
            (['a', 'b', 'c'], (list, str)),
            ([1.0, 2.0, 3.0], (list, float)),
            # ---- Heterogeneous lists ----
            ([1, 'a', 2.0], (list, int | str | float)),
            ([1, 2, 'three'], (list, int | str)),
            # ---- Homogeneous tuples ----
            ((1, 2, 3), (tuple, int)),
            (('a', 'b', 'c'), (tuple, str)),
            # ---- Homogeneous sets ----
            ({1, 2, 3}, (set, int)),
            ({'a', 'b', 'c'}, (set, str)),
            # ---- Heterogeneous sets ----
            ({1, 'a'}, (set, int | str)),
            # ---- Homogeneous dicts ----
            ({'a': 1, 'b': 2}, (dict, str, int)),
            ({1: 'a', 2: 'b'}, (dict, int, str)),
            # ---- Heterogeneous dicts ----
            ({'a': 1, 'b': 'c'}, (dict, str, int | str)),
            ({1: 'a', 'b': 2}, (dict, int | str, str | int)),
            # ---- Nested structures ----
            ([[1, 2], [3, 4]], (list, (list, int))),
            ([{'a': 1}, {'b': 2}], (list, (dict, str, int))),
            ({'x': [1, 2], 'y': [3, 4]}, (dict, str, (list, int))),
            # ---- Counter ----
            (Counter(['a', 'b', 'a']), (Counter, str, int)),
            (Counter([1, 2, 1]), (Counter, int, int)),
            # ---- Deque ----
            (deque([1, 2, 3]), (deque, int)),
            (deque(['a', 'b']), (deque, str)),
        ],
    )
    def test_metaparse(self, data, expected: Expected):
        inst = cls.typeof(data)
        self.check_inst(inst, expected)

    def test_metaparse__tuples(self):
        inst = cls.typeof((1, 'a'))
        assert inst.root == tuple[int, str]
        inst = cls.typeof((1, 'a', 2.0))
        assert inst.root == tuple[int, str, float]
        inst = cls.typeof(('x', (1, 'a'), True))
        assert inst.root == tuple[str, tuple[int, str], bool]

    # -------------------
    # `-` Private Methods
    # -------------------

    # -------------------
    # `+` Primary Methods
    # -------------------

    # ------------------
    # `*` Public Methods
    # ------------------

    @pyt.mark.parametrize(
        'value, tvar, expected',
        boolmap(
            false=[
                ((1, 2, 'a'), tuple[int, ...]),
                ((1, 2), tuple[int, str]),
                (('a', 1), tuple[int, str]),
                ('ONE', Literal['one', 'two']),
                (4, Literal[1, 2, 3]),
            ],
            true=[
                (('a', 'b'), tuple),
                ((), tuple[int, ...]),
                ((1, 'a'), tuple[int, str]),
                ((1, 'a', 2.0), tuple[int, str, float]),
                ((1, 2, 3), tuple),
                ((1, 2, 3), tuple[int, ...]),
                ('one', Literal['one', 'two']),
                (2, Literal[1, 2, 3]),
            ],
        ),
    )
    def test_check__literals(self, value: tuple, tvar: type, expected: bool):
        assert cls.parse(tvar).check(value) == expected

    @pyt.mark.parametrize(
        'data, tvar, expected',
        boolmap(
            false=[
                (1.5, str | int),
                ({1, 2}, list[int] | dict[str, int]),
                ('string', list[list[int]] | dict[str, int]),
            ],
            true=[
                ('a', str | int),
                (1, str | int),
                ([1, 2], list[int] | dict[str, int]),
                ([[1, 2]], list[list[int]] | dict[str, int]),
                ({'a': 1}, list[list[int]] | dict[str, int]),
                ({'a': 1}, list[int] | dict[str, int]),
            ],
        ),
    )
    def test_check__union(self, data, tvar: type, expected: bool):
        assert cls.parse(tvar).check(data) == expected

    @pyt.mark.parametrize(
        'data, tvar, expected',
        boolmap(
            false=[
                ((1, 2, 'a'), tuple[int, ...]),
                ((1,), tuple[int, str]),
                (('a', 1), tuple[int, str]),
                ((1, 'a', 'b'), tuple[int, str, float]),
            ],
            true=[
                ((), tuple[int, ...]),
                ((1, 2, 3), tuple[int, ...]),
                (('a', 'b'), tuple[str, ...]),
                ((1, 'a'), tuple[int, str]),
                ((1, 'a', 2.0), tuple[int, str, float]),
            ],
        ),
    )
    def test_check__tuple(self, data, tvar: type, expected: bool):
        assert cls.parse(tvar).check(data) == expected

    def test_check_iter(self):
        # ---- Test successful iteration ----
        int_type = cls.parse(int)
        results = list(int_type.check_iter([1, 2, 3]))
        assert results == [True, True, True]

        results = list(int_type.check_iter([1, 'a', 3]))
        assert results == [True, False, True]

        # ---- Test with strings ----
        str_type = cls.parse(str)
        results = list(str_type.check_iter(['a', 'b', 'c']))
        assert results == [True, True, True]

        # ---- Test with complex types ----
        list_int_type = cls.parse(list[int])
        results = list(list_int_type.check_iter([[1, 2], [3, 4], ['a']]))
        assert results == [True, True, False]

    @pyt.mark.parametrize(
        'tvar, expected',
        boolmap(
            false=[
                int,
                str,
                list[int],
                dict[str, int],
                tuple[int],
                tuple[int, int, int],
                tuple[int, ...],
            ],
            true=[
                tuple,
                tuple[str, int],
                tuple[int, str],
                tuple[str, list[int]],
                tuple[dict[str, int], float],
            ],
        ),
    )
    def test_is_map_item(self, tvar: type, expected: bool):
        assert cls.parse(tvar).is_map_item() == expected

    @pyt.mark.parametrize(
        'inst1, inst2, expected',
        [
            # ---- Equality by uid ----
            (cls.parse(int), cls.parse(int), True),
            (cls.parse(str), cls.parse(str), True),
            (cls.parse(list[int]), cls.parse(list[int]), True),
            (cls.parse(dict[str, int]), cls.parse(dict[str, int]), True),
            # ---- Inequality ----
            (cls.parse(int), cls.parse(str), False),
            (cls.parse(list[int]), cls.parse(list[str]), False),
            (cls.parse(dict[str, int]), cls.parse(dict[int, str]), False),
            # ---- Equality with raw types ----
            (cls.parse(int), int, True),
            (cls.parse(str), str, True),
            # ---- Inequality with raw types ----
            (cls.parse(int), str, False),
            (cls.parse(str), int, False),
            # ---- None comparisons ----
            (cls.parse(None), None, True),
            (cls.parse(int), None, False),
        ],
    )
    def test_eq(self, inst1, inst2, expected: bool):
        assert (inst1 == inst2) == expected

    @pyt.mark.parametrize(
        'inst, expected',
        [
            # ---- Truthy instances ----
            (cls.parse(int), True),
            (cls.parse(str), True),
            (cls.parse(list[int]), True),
            (cls.parse(dict[str, int]), True),
            (cls.parse(Literal['a', 'b']), True),
            (cls.parse(tuple[int, str]), True),
            # ---- Falsy instances ----
            (cls.parse(None), False),
            (cls.parse(Any), False),
            (cls.parse(Callable), False),
            (cls.parse(Generator), False),
        ],
    )
    def test_bool(self, inst, expected: bool):
        assert bool(inst) == expected

    def test_hash(self):
        # Same types should have same hash
        assert hash(cls.parse(int)) == hash(cls.parse(int))
        assert hash(cls.parse(list[int])) == hash(cls.parse(list[int]))

        # Different types should (usually) have different hashes
        assert hash(cls.parse(int)) != hash(cls.parse(str))
        assert hash(cls.parse(list[int])) != hash(cls.parse(list[str]))

        # Can be used in sets/dicts
        s = {cls.parse(int), cls.parse(str), cls.parse(int)}
        assert len(s) == 2

    def test_parse_caching(self):
        # Same type should return cached instance
        inst1 = cls.parse(int)
        inst2 = cls.parse(int)
        assert inst1 is inst2  # Same object due to caching

        inst1 = cls.parse(list[int])
        inst2 = cls.parse(list[int])
        assert inst1 is inst2  # Same object due to caching

        # Different types should return different instances
        inst1 = cls.parse(int)
        inst2 = cls.parse(str)
        assert inst1 is not inst2

    def test_parse_mytype_input(self):
        # Parsing a MyType should return it unchanged
        inst1 = cls.parse(int)
        inst2 = cls.parse(inst1)
        assert inst1 is inst2

    def test_parse_ellipsis(self):
        # Test that Ellipsis is converted to EllipsisType
        inst = cls.parse(Ellipsis)
        assert inst.main is types.EllipsisType

    def test_members(self):
        # Define a test Pydantic model
        class TestModel(pyd.BaseModel):
            name: str
            age: int
            score: float
            active: bool

        # Parse the model type
        model_type = cls.parse(TestModel)

        # Get members
        members = list(model_type.members())

        # Should have 4 members
        assert len(members) == 4

        # All members should be MyType instances
        assert all(isinstance(m, MyType) for m in members)

        # Check the types of the members
        member_types = {m.main for m in members}
        assert member_types == {str, int, float, bool}

    def test_members_empty(self):
        # Non-Pydantic types should yield no members
        int_type = cls.parse(int)
        assert list(int_type.members()) == []

        list_type = cls.parse(list[int])
        assert list(list_type.members()) == []

############
### HEAD ###
############
### STANDARD
from typing import Any
from collections.abc import Callable
from collections import deque
from dataclasses import dataclass

### EXTERNAL
import pytest as pyt
import pydantic as pyd

### INTERNAL
from my.types import Buffer
from my.typing import Typist

############
### DATA ###
############
cls = Typist
typist = Typist(firsts=True, atomics=True, splits=True, wraps=True)


############
### BODY ###
############
class TestTypist:
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

    def test_serialize__dataclass(self):
        """Dataclasses serialize as mappings instead of being treated as iterables."""

        @dataclass
        class Record:
            name: str
            count: int

        assert typist.serialize(Record('example', 2)) == {'name': 'example', 'count': 2}

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
        'data, expected',
        [
            (dict(a=1, b=2), 'a = 1\nb = 2\n'),
            (dict(section=dict(x=1, y=2)), '[section]\nx = 1\ny = 2\n'),
            (dict(list=[1, 2, 3]), 'list = [\n    1,\n    2,\n    3,\n]\n'),
        ],
    )
    def test_to_toml(self, data: dict, expected: str):
        result = typist.to_toml(data)
        assert result == expected

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

    def test_invocable__pep563(self):
        """Regression: PEP 563 string annotations are resolved before checking (`eval_str`)."""
        # Built via exec so the future import genuinely stringifies the annotations.
        ns: dict = {}
        exec(
            'from __future__ import annotations\n'
            'def fn(x: int, y: str) -> str:\n'
            "    return f'{x}: {y}'\n",
            ns,
        )
        fn = ns['fn']
        assert typist.invocable(fn, 4, 'hi') is not None
        assert typist.invocable(fn, 'not-an-int', 'hi') is None
        assert typist.invoke(fn, 4, 'hi') == '4: hi'

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

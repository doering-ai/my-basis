############
### HEAD ###
############
### STANDARD
from typing import Any, Iterable, Callable, Mapping, Sequence, Collection
from collections import deque, Counter

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.utils import IterUtils

cls = IterUtils


############
### BODY ###
############
class TestIterUtils:
    # ----------------
    # `0` CONSTRUCTION
    # ----------------
    @pyt.mark.parametrize('data, expected', [])
    def test_build(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize(
        'data, expected',
        [
            (dict(a=1, b=2, c=3), [('a', 1), ('b', 2), ('c', 3)]),
            ([('a', 1), ('b', 2), ('c', 3)], [('a', 1), ('b', 2), ('c', 3)]),
            (Counter(['a', 'b', 'b', 'c', 'c', 'c']), [('a', 1), ('b', 2), ('c', 3)]),
            ([], []),
            (5, []),
            ([5], []),
            ((1, 2), []),
        ],
    )
    def test_map_items(self, data: Mapping | Sequence, expected: list[tuple[Any, Any]]):
        assert cls.map_items(data) == expected

    @pyt.mark.parametrize('data, expected', [])
    def test_partition(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data, expected', [])
    def test_multi_partition(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data, expected', [])
    def test_bucket(self, data: str, expected: str):
        pass

    # -------------
    # `1` SELECTION
    # -------------
    @pyt.mark.parametrize('data,expected', [])
    def test_find(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test_find_key(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test_next_in(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test_condense(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test_map_condense(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test_get_all(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test_get_any(self, data: str, expected: str):
        pass

    # ---------------
    # `2` APPLICATION
    # ---------------
    @pyt.mark.parametrize(
        'func, data, expected',
        [
            (lambda x: x, {}, {}),
            (lambda x: x**2, dict(a=1, b=2, c=3), dict(a=1, b=4, c=9)),
            (lambda x: x**2, [('a', 1), ('b', 2), ('c', 3)], dict(a=1, b=4, c=9)),
            (lambda x: x**2, [1, 2, 3], {1: 1, 2: 4, 3: 9}),
            (lambda x: x.upper(), deque(['abc', 'cde']), dict(abc='ABC', cde='CDE')),
            (lambda x: x * 0, ['abc', 'cde'], dict()),
        ],
    )
    def test_val_map(self, func: Callable, data: Iterable, expected: dict):
        assert cls.val_map(func, data, drop=True) == expected

    @pyt.mark.parametrize('data,expected', [])
    def test_attr_map(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data,expected', [])
    def test_chain_map(self, data: str, expected: str):
        pass

    # -------------
    # `3` EXECUTION
    # -------------
    @pyt.mark.parametrize('data,expected', [])
    def test_repeat_until_complete(self, data: str, expected: str):
        pass

    # ------------
    # `4` PRESENCE
    # ------------
    @pyt.mark.parametrize(
        'expected, data, target',
        [
            # Test basics
            ((0, 0, 0, 0), ['abc', 'cde', 'cefg'], ['z']),
            ((0, 0, 0, 1), ['abc', 'cde', 'cefg'], ['a', 'z']),
            ((0, 0, 1, 1), ['abc', 'cde', 'cefg'], ['c', 'z']),
            ((0, 1, 0, 1), ['abc', 'cde', 'cefg'], ['a']),
            ((0, 1, 1, 1), ['abc', 'cde', 'cefg'], ['a', 'c']),
            ((1, 1, 1, 1), ['abc', 'cde', 'cefg'], ['c']),
            # Test type flexibility
            ((0, 0, 0, 0), [dict(abc=1), dict(cde=2), dict(cefg=3)], ['a', 'z']),
            ((0, 0, 0, 1), [dict(abc=1), dict(cde=2), dict(cefg=3)], ['abc', 'yxz']),
            ((1, 1, 1, 1), [dict(a=1, b=2, c=3), dict(c=1, d=2, e=3)], ['c']),
            ((0, 0, 0, 0), [['abc'], ['cde'], ['cef']], ['c']),
            ((0, 1, 0, 1), [['abc'], ['cde'], ['cef']], ['abc']),
        ],
    )
    def test_has_x(self, expected: tuple[int, int, int, int], data: Iterable, target: list[str]):
        assert (
            cls.all_has_all(data, *target),
            cls.any_has_all(data, *target),
            cls.all_has_any(data, *target),
            cls.any_has_any(data, *target),
        ) == tuple(map(bool, expected))

    @pyt.mark.parametrize(
        'data, target, expected',
        [
            (dict(a=1, b=2, c=3), 'z', 0),
            (dict(a=1, b=2, c=3), 'a', 0),
            (dict(a=1), 'a', 1),
        ],
    )
    def test_has_only(self, data: Collection, target: str, expected: int):
        assert cls.has_only(data, target) == bool(expected)

    @pyt.mark.parametrize(
        'data, target, expected',
        [
            (dict(a=1, b=2, c=3), 'z', 1),
            (dict(a=1, b=2, c=3), 'a', 0),
            (dict(a=1), 'a', 0),
        ],
    )
    def test_has_none(self, data: Collection, target: str, expected: int):
        assert cls.has_none(data, target) == bool(expected)

    # --------------
    # `5` COMPARISON
    # --------------
    @pyt.mark.parametrize(
        'data, expected',
        [
            ([], ''),
            (['abc', ''], ''),
            (['abc', 'abZc'], 'ab'),
            (['abc', 'bdc'], ''),
            (['abc', 'abdc', 'a'], 'a'),
        ],
    )
    def test_shared_prefix(self, data: list[str], expected: str):
        assert cls.shared_prefix(*data) == expected

    @pyt.mark.parametrize(
        'data, expected',
        [
            ([], ''),
            (['abc', ''], ''),
            (['abc', 'aZbc'], 'bc'),
            (['abc', 'bdc'], 'c'),
            (['abc', 'aZbc', 'c'], 'c'),
        ],
    )
    def test_shared_suffix(self, data: list[str], expected: str):
        assert cls.shared_suffix(*data) == expected

    @pyt.mark.parametrize('data,expected', [])
    def test_common_elements(self, data: str, expected: str):
        pass

    # ----------------
    # `6` MODIFICATION
    # ----------------
    @pyt.mark.parametrize(
        'data, mask, expected',
        [
            (['a', 'b', 'c'], [0, 1], ['c']),
            (['a', 'b', 'c'], [99], ['a', 'b', 'c']),
            ([], [99], []),
        ],
    )
    def test_drop_at(self, data: list, mask: list[int], expected: list):
        assert cls.drop_at(data, mask) == expected

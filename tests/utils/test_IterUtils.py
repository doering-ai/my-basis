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
    @pyt.mark.parametrize(
        'initial, funcs, expected',
        [
            (0, [], 0),
            (5, [lambda x: x + 1], 6),
            (1, [lambda x: x * 2, lambda x: x + 3], 5),  # (1*2)+3 = 5
            ('hello', [str.upper, lambda s: s + '!'], 'HELLO!'),
            ([1, 2], [lambda x: x + [3], lambda x: x * 2], [1, 2, 3, 1, 2, 3]),
        ],
    )
    def test_build(self, initial: Any, funcs: list[Callable], expected: Any):
        assert cls.build(initial, *funcs) == expected

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

    @pyt.mark.parametrize(
        'items, pred, expected',
        [
            ([1, 2, 3, 4, 5], lambda x: x > 3, ([1, 2, 3], [4, 5])),
            ([1, 2, 3], lambda x: x > 10, ([1, 2, 3], [])),
            ([], lambda x: True, ([], [])),
            (['a', 'ab', 'abc'], lambda s: len(s) > 1, (['a'], ['ab', 'abc'])),
        ],
    )
    def test_partition(self, items: list, pred: Callable, expected: tuple[list, list]):
        assert cls.partition(items, pred) == expected

    @pyt.mark.parametrize(
        'items, preds, expected',
        [
            (
                [1, 2, 3, 4, 5, 6],
                {'even': lambda x: x % 2 == 0, 'gt3': lambda x: x > 3},
                {'even': [2, 4, 6], 'gt3': [5], 'rest': [1, 3]},
            ),
            ([1, 2, 3], {'all': lambda x: True}, {'all': [1, 2, 3], 'rest': []}),
            ([1, 2, 3], {'none': lambda x: False}, {'none': [], 'rest': [1, 2, 3]}),
            ([], {'test': lambda x: True}, {'test': [], 'rest': []}),
        ],
    )
    def test_multi_partition(self, items: list, preds: dict, expected: dict):
        assert cls.multi_partition(items, **preds) == expected

    @pyt.mark.parametrize(
        'items, key_func, expected',
        [
            ([1, 2, 3, 4, 5], lambda x: x % 2, {0: [2, 4], 1: [1, 3, 5]}),
            (['a', 'ab', 'abc'], len, {1: ['a'], 2: ['ab'], 3: ['abc']}),
            ([], lambda x: x, {}),
            ([1, 1, 2, 2, 3], lambda x: x, {1: [1, 1], 2: [2, 2], 3: [3]}),
        ],
    )
    def test_bucket(self, items: list, key_func: Callable, expected: dict):
        result = cls.bucket(items, key_func)
        assert dict(result) == expected

    # -------------
    # `1` SELECTION
    # -------------
    @pyt.mark.parametrize(
        'container, predicate, expected',
        [
            ([0, 0, 1, 0], bool, 2),  # First truthy value
            ([1, 2, 3], lambda x: x > 2, 2),  # First value > 2
            ([1, 2, 3], 2, 1),  # Find value 2
            ([1, 2, 3], 5, -1),  # Value not found
            ([], bool, -1),  # Empty container
            ([False, False, True], bool, 2),
        ],
    )
    def test_find(self, container: Sequence, predicate: Callable | Any, expected: int):
        assert cls.find(container, predicate) == expected

    @pyt.mark.parametrize(
        'items, predicate, default, expected',
        [
            ({'a': 1, 'b': 0, 'c': 3}, bool, None, 'a'),  # First truthy value
            ({'a': 1, 'b': 2, 'c': 3}, lambda x: x > 2, None, 'c'),  # First value > 2
            ({'a': 1, 'b': 2}, 2, None, 'b'),  # Find value 2
            ({'a': 1, 'b': 2}, 5, 'default', 'default'),  # Not found, return default
            ([('x', 10), ('y', 20)], lambda v: v > 15, None, 'y'),  # Iterable of tuples
            ({}, bool, 'empty', 'empty'),  # Empty mapping
        ],
    )
    def test_find_key(
        self, items: Mapping | Iterable, predicate: Callable | Any, default: Any, expected: Any
    ):
        assert cls.find_key(items, predicate, default) == expected

    @pyt.mark.parametrize(
        'container, items, expected',
        [
            ([1, 2, 3], [4, 2, 5], 2),  # First match is 2
            (['a', 'b'], ['c', 'd', 'a'], 'a'),  # First match is "a"
            ([1, 2, 3], [4, 5, 6], None),  # No matches
            (set(), [1, 2], None),  # Empty container
            ({1, 2}, [], None),  # Empty items
        ],
    )
    def test_next_in(self, container: Collection, items: Iterable, expected: Any):
        assert cls.next_in(container, items) == expected

    @pyt.mark.parametrize(
        'items, pred, expected',
        [
            ([0, 1, 2, 0, 3], bool, [1, 2, 3]),  # Filter truthy
            ([1, 2, 3, 4, 5], lambda x: x > 2, [3, 4, 5]),  # Custom predicate
            ([0, 0, 0], bool, []),  # All falsy
            ([], bool, []),  # Empty input
        ],
    )
    def test_condense(self, items: Iterable, pred: Callable, expected: list):
        assert cls.condense(items, pred) == expected

    @pyt.mark.parametrize(
        'items, pred, expected',
        [
            ({'a': 1, 'b': 0, 'c': 3}, bool, [('a', 1), ('c', 3)]),
            ({'a': 1, 'b': 2, 'c': 3}, lambda x: x > 1, [('b', 2), ('c', 3)]),
            (
                [('x', 5), ('y', 0), ('z', 10)],
                lambda v: v > 4,
                [('x', 5), ('z', 10)],
            ),
            ({}, bool, []),
        ],
    )
    def test_map_condense(self, items: Mapping | Iterable, pred: Callable, expected: list):
        assert list(cls.map_condense(items, pred)) == expected

    @pyt.mark.parametrize(
        'dictionary, keys, mandatory, expected',
        [
            ({'a': 1, 'b': 2, 'c': 3}, ['a', 'b'], False, {'a': 1, 'b': 2}),
            ({'a': 1, 'b': 2}, ['a', 'x'], False, {'a': 1}),  # Missing key ignored
            ({'a': 1, 'b': 2}, ['a', 'x'], True, {}),  # Missing key with mandatory=True
            ({'a': 1}, ['a'], True, {'a': 1}),  # All keys present with mandatory
            ({}, ['a'], False, {}),  # Empty dict
        ],
    )
    def test_get_all(self, dictionary: dict, keys: list[str], mandatory: bool, expected: dict):
        assert cls.get_all(dictionary, *keys, mandatory=mandatory) == expected

    @pyt.mark.parametrize(
        'dictionary, keys, default, unique, expected',
        [
            ({'a': 1, 'b': 2, 'c': 3}, ['a', 'b'], None, False, 1),  # First key found
            ({'a': 1, 'b': 2}, ['x', 'a'], None, False, 1),  # Skip missing, find "a"
            ({'a': 1}, ['x', 'y'], 99, False, 99),  # No keys found, return default
            ({'a': 5, 'b': 5}, ['x'], 5, False, 5),  # Default matches values (not found)
            ({}, ['a'], None, False, None),  # Empty dict
        ],
    )
    def test_get_any(
        self, dictionary: dict, keys: list[str], default: Any, unique: bool, expected: Any
    ):
        assert cls.get_any(dictionary, *keys, default=default, unique=unique) == expected

    def test_get_any_unique_error(self):
        with pyt.raises(ValueError, match='Multiple keys found'):
            cls.get_any({'a': 1, 'b': 2}, 'a', 'b', unique=True)

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

    @pyt.mark.parametrize(
        'obj, fields, drop, expected',
        [
            # Test basic attribute extraction
            (type('O', (), {'a': 1, 'b': 2, 'c': 3})(), ['a', 'b'], False, {'a': 1, 'b': 2}),
            # Test with drop=True to filter falsy values (empty strings become '')
            (type('O', (), {'x': 'hello', 'y': ''})(), ['x'], False, {'x': 'hello'}),
        ],
    )
    def test_attr_map(self, obj: object, fields: list[str], drop: bool, expected: dict):
        assert cls.attr_map(obj, fields, drop=drop) == expected

    def test_attr_map_missing_attr(self):
        obj = type('O', (), {'x': 'hello'})()
        with pyt.raises(AttributeError):
            cls.attr_map(obj, ['x', 'missing'], drop=False)

    @pyt.mark.parametrize(
        'funcs, item, expected',
        [
            ([lambda x: x * 2, lambda x: x + 1], 5, [10, 6]),  # Both return truthy
            ([lambda x: x if x > 10 else None, lambda x: x * 2], 5, [10]),  # First returns None
            ([lambda x: None, lambda x: None], 5, []),  # All return falsy
            ([], 5, []),  # No functions
        ],
    )
    def test_chain_map(self, funcs: list[Callable], item: Any, expected: list):
        assert list(cls.chain_map(funcs, item)) == expected

    # -------------
    # `3` EXECUTION
    # -------------
    def test_repeat_until_complete(self):
        # Create a simple function that removes one 'x' per call
        @cls.repeat_until_complete
        def remove_x(obj: Any, text: str) -> tuple[int, str]:
            if 'x' in text:
                return 1, text.replace('x', '', 1)
            return 0, text

        # Test with string containing multiple 'x's
        total_changes, result = remove_x(None, 'xxxhello')
        assert total_changes == 3
        assert result == 'hello'

        # Test with no changes needed
        total_changes, result = remove_x(None, 'hello')
        assert total_changes == 0
        assert result == 'hello'

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

    @pyt.mark.parametrize(
        'lhs, rhs, expected',
        [
            ([1, 2, 3], [2, 3, 4], [2, 3]),  # Sequences with overlap
            ([1, 1, 2], [1, 2, 2], [1, 2]),  # Duplicates (min count preserved)
            ({1, 2, 3}, {2, 3, 4}, [2, 3]),  # Sets
            ([1, 2], [3, 4], []),  # No overlap
            ([], [1, 2], []),  # Empty sequence
            ([1, 2, 2, 2], [2, 2, 3], [2, 2]),  # Multiple duplicates (min preserved)
        ],
    )
    def test_common_elements(self, lhs: Sequence | set, rhs: Sequence | set, expected: list):
        result = cls.common_elements(lhs, rhs)
        # For sets, order doesn't matter
        if isinstance(lhs, set) or isinstance(rhs, set):
            assert sorted(result) == sorted(expected)
        else:
            assert sorted(result) == sorted(expected)

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

############
### HEAD ###
############
### STANDARD
from typing import Any, Literal
from collections.abc import (
    Mapping,
    Container,
)
from collections import Counter, deque
from enum import Enum

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.typing import MyType
from ..conftest import boolmap

############
### DATA ###
############
cls = MyType

Expected = tuple[type, ...] | type | None


class TestTypecheck:
    @pyt.mark.parametrize(
        'data, tvar, expected',
        boolmap(
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
            ],
            true=[
                # ---- Basic types ----
                ('abc', str),
                (123, int),
                (3.14, float),
                (b'bytes', bytes),
                (True, bool),
                # ---- Any and object ----
                ('anything', Any),
                ('anything', object),
                (123, Any),
                (123, object),
                # ---- Lists ----
                (['a', 'b'], list[str]),
                ([1, 2, 3], list),
                ([1, 2, 3], list[int]),
                ([1, 2], Any),
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
                # ---- Deque ----
                (deque([1, 2, 3]), deque),
                (deque([1, 2, 3]), deque[int]),
                # ---- Funcs ----
            ],
        ),
    )
    def test_check(self, data, tvar: type, expected: bool):
        assert cls.parse(tvar).check(data) == expected

############
### HEAD ###
############
### STANDARD
from typing import Any, Iterable, Callable, Mapping, Sequence, Collection
from collections import deque, Counter

### EXTERNAL
import pytest as pyt

### INTERNAL
from my import utils as ut


############
### BODY ###
############
class TestUtils:
    # -------------------
    # 1. System Utilities
    # -------------------
    # @pyt.mark.parametrize('data, expected', [])
    # def test_posix(self, data: str, expected: str):
    #     assert ut.posix(data) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_instrument(self, data: str, expected: str):
    #     assert ut.instrument(data) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_measure_context(self, data: str, expected: str):
    #     assert ut.measure_context(data) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_monitor(self, data: str, expected: str):
    #     assert ut.monitor(data) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_wrap(self, data: str, expected: str):
    #     assert ut.wrap(data) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_bootstrap_logfire(self, data: str, expected: str):
    #     assert ut.bootstrap_logfire(data) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_validate_dir(self, data: str, expected: str):
    #     assert ut.validate_dir(data) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_validate_file(self, data: str, expected: str):
    #     assert ut.validate_file(data) == expected

    @pyt.mark.parametrize(
        'pattern, expected', [
            (r'utils\.py', True),
            (r'base/utils\.py', True),
            (r'invalid/base/utils\.py', False),
        ]
    )
    @pyt.mark.asyncio
    async def test_find_file(self, pattern: str, expected: bool, root):
        ret = await ut.find_file(pattern, root)
        assert (ret is not None) == expected

    @pyt.mark.parametrize(
        'lines, expected', [
            (
                ['welcome', 'to the ', 'club now', ''],
                ['welcome to the club now'],
            ),
            (
                ['    welcome to', '        the club', '    now.'],
                ['welcome to the club now.'],
            ),
            (
                [
                    '    * welcome     ',
                    '    * >to the-',
                    '    * club-',
                    '    * !now-',
                    '    * - parent',
                    '    *     - child',
                    '    * > quote here',
                    '    * 1. numbered parent',
                    '    *     11. numbered child',
                ],
                [
                    'welcome >to the-club- !now-',
                    '- parent',
                    '    - child',
                    '> quote here',
                    '1. numbered parent',
                    '    11. numbered child',
                ],
            ),
        ]
    )
    def test_unwrap_paragraphs(self, lines: list[str], expected: list[str]):
        assert ut.unwrap_paragraphs('\n'.join(lines)) == '\n'.join(expected)

    # ----------------------
    # 2. Functional Wrappers
    # ----------------------
    # @pyt.mark.parametrize('data, expected', [])
    # def test_build(self, data: str, expected: str):
    #     assert ut.build(data) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_find(self, data: str, expected: str):
    #     assert ut.find(data) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_find_key(self, data: str, expected: str):
    #     assert ut.find_key(data) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_measure(self, data: str, expected: str):
    #     assert ut.measure(data) == expected

    @pyt.mark.parametrize(
        'func, data, expected', [
            (lambda x: x, {}, {}),
            (lambda x: x**2, dict(a=1, b=2, c=3), dict(a=1, b=4, c=9)),
            (lambda x: x**2, [('a', 1), ('b', 2), ('c', 3)], dict(a=1, b=4, c=9)),
            (lambda x: x**2, [1, 2, 3], {
                1: 1,
                2: 4,
                3: 9
            }),
            (lambda x: x.upper(), deque(['abc', 'cde']), dict(abc='ABC', cde='CDE')),
            (lambda x: x * 0, ['abc', 'cde'], dict()),
        ]
    )
    def test_val_map(self, func: Callable, data: Iterable, expected: dict):
        assert ut.val_map(func, data, drop=True) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_attr_map(self, data: str, expected: str):
    #     assert ut.attr_map(data) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_chain_map(self, data: str, expected: str):
    #     assert ut.chain_map(data) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_condense(self, data: str, expected: str):
    #     assert ut.condense(data) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_map_condense(self, data: str, expected: str):
    #     assert ut.map_condense(data) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_get_all(self, data: str, expected: str):
    #     assert ut.get_all(data) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_get_any(self, data: str, expected: str):
    #     assert ut.get_any(data) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_repeat_until_complete(self, data: str, expected: str):
    #     assert ut.repeat_until_complete(data) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_replace(self, data: str, expected: str):
    #     assert ut.replace(data) == expected

    # ---------------
    # Presence checks
    # ---------------
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
        ]
    )
    def test_has_X(self, expected: tuple[int, int, int, int], data: Iterable, target: list[str]):
        assert (
            ut.all_has_all(data, *target), ut.any_has_all(data, *target),
            ut.all_has_any(data, *target), ut.any_has_any(data, *target)
        ) == tuple(map(bool, expected))

    @pyt.mark.parametrize(
        'data, target, expected', [
            (dict(a=1, b=2, c=3), 'z', 0),
            (dict(a=1, b=2, c=3), 'a', 0),
            (dict(a=1), 'a', 1),
        ]
    )
    def test_has_only(self, data: Collection, target: str, expected: int):
        assert ut.has_only(data, target) == bool(expected)

    @pyt.mark.parametrize(
        'data, target, expected', [
            (dict(a=1, b=2, c=3), 'z', 1),
            (dict(a=1, b=2, c=3), 'a', 0),
            (dict(a=1), 'a', 0),
        ]
    )
    def test_has_none(self, data: Collection, target: str, expected: int):
        assert ut.has_none(data, target) == bool(expected)

    @pyt.mark.parametrize(
        'data, mask, expected', [
            (['a', 'b', 'c'], [0, 1], ['c']),
            (['a', 'b', 'c'], [99], ['a', 'b', 'c']),
            ([], [99], []),
        ]
    )
    def test_drop_at(self, data: list, mask: list[int], expected: list):
        assert ut.drop_at(data, mask) == expected

    @pyt.mark.parametrize(
        'data, expected', [
            ([], ''),
            (['abc', ''], ''),
            (['abc', 'abZc'], 'ab'),
            (['abc', 'bdc'], ''),
            (['abc', 'abdc', 'a'], 'a'),
        ]
    )
    def test_shared_prefix(self, data: list[str], expected: str):
        assert ut.shared_prefix(*data) == expected

    @pyt.mark.parametrize(
        'data, expected', [
            ([], ''),
            (['abc', ''], ''),
            (['abc', 'aZbc'], 'bc'),
            (['abc', 'bdc'], 'c'),
            (['abc', 'aZbc', 'c'], 'c'),
        ]
    )
    def test_shared_suffix(self, data: list[str], expected: str):
        assert ut.shared_suffix(*data) == expected

    # --------------------------
    # 3. Serialization Functions
    # --------------------------
    # @pyt.mark.parametrize('data, expected', [])
    # def test_regex_dict(self, data: str, expected: str):
    #     assert ut.regex_dict(data) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_regex_array(self, data: str, expected: str):
    #     assert ut.regex_array(data) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_spaced_rgx(self, data: str, expected: str):
    #     assert ut.spaced_rgx(data) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_multi_rgx(self, data: str, expected: str):
    #     assert ut.multi_rgx(data) == expected

    @pyt.mark.parametrize(
        'data, expected', [
            (' "hello \'world\' " ', 'hello \'world\''),
            ('hello world', 'hello world'),
            ('" _**hello_world**_ "', 'hello_world'),
            ('hello world**', 'hello world**'),
        ]
    )
    def test_strip_quotes(self, data: str, expected: str):
        assert ut.strip_quotes(data) == expected

    @pyt.mark.parametrize(
        'text, expected', [
            (' a\nb\n ', 'a-b'),
            ('ABC:DEF', 'abc_def'),
            ('a bc : de f', 'a-bc_de-f'),
            ('a,bc : de.f', 'a_bc_def'),
            ('a bc (de f)', 'a-bc_de-f'),
        ]
    )
    def test_clean_string(self, text: str, expected: str):
        assert ut.clean_string(text) == expected

    @pyt.mark.parametrize(
        'text, expected', [
            ('A', ['A']),
            ('A B', ['A', 'B']),
            ('A\'B', ['A', 'B']),
            ('A-B', ['A', 'B']),
            ('A_B', ['A_B']),
            ('', []),
            (',!', []),
            ('abc, cde. efg!', ['abc', 'cde', 'efg']),
        ]
    )
    def test_to_words(self, text: str, expected: list[str]):
        assert ut.to_words(text) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_line_num(self, data: str, expected: str):
    #     assert ut.line_num(data) == expected

    # ------------------
    # 4. Code Reflection
    # ------------------
    # @pyt.mark.parametrize('data, expected', [])
    # def test_instance_fields(self, data: str, expected: str):
    #     assert ut.instance_fields(data) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_nested_replace(self, data: str, expected: str):
    #     assert ut.nested_replace(data) == expected

    # @pyt.mark.parametrize('data, expected', [])
    # def test_parse_domain(self, data: str, expected: str):
    #     assert ut.parse_domain(data) == expected

    # --------------------
    # 5. Semantic Coercion
    # --------------------
    @pyt.mark.parametrize(
        'roman, decimal', [
            ('I', 1),
            ('II', 2),
            ('III', 3),
            ('IV', 4),
            ('V', 5),
            ('VI', 6),
            ('VII', 7),
            ('VIII', 8),
            ('IX', 9),
            ('X', 10),
            ('XL', 40),
            ('LX', 60),
            ('XC', 90),
            ('CXI', 111),
            ('MCXI', 1111),
            ('CMXCIX', 999),
            ('', 0),
            ('X: not a roman numeral', 0),
            ('X I', 0),
        ]
    )
    def test_roman_to_decimal(self, roman: str, decimal: int):
        assert ut.roman_to_decimal(roman) == decimal

    @pyt.mark.parametrize(
        'decimal, roman', [
            (1, 'I'),
            (2, 'II'),
            (3, 'III'),
            (4, 'IV'),
            (5, 'V'),
            (6, 'VI'),
            (7, 'VII'),
            (8, 'VIII'),
            (9, 'IX'),
            (10, 'X'),
            (40, 'XL'),
            (60, 'LX'),
            (90, 'XC'),
            (111, 'CXI'),
            (1111, 'MCXI'),
            (999, 'CMXCIX'),
        ]
    )
    def test_decimal_to_roman(self, decimal: int, roman: str):
        assert ut.decimal_to_roman(decimal) == roman

    @pyt.mark.parametrize(
        'data, expected', [
            (dict(a=1, b=2, c=3), [('a', 1), ('b', 2), ('c', 3)]),
            ([('a', 1), ('b', 2), ('c', 3)], [('a', 1), ('b', 2), ('c', 3)]),
            (Counter(['a', 'b', 'b', 'c', 'c', 'c']), [('a', 1), ('b', 2), ('c', 3)]),
            ([], []),
            (5, []),
            ([5], []),
            ((1, 2), []),
        ]
    )
    def test_map_items(self, data: Mapping | Sequence, expected: list[tuple[Any, Any]]):
        assert ut.map_items(data) == expected

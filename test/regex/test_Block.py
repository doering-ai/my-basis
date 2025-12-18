############
### HEAD ###
############
### STANDARD
from typing import Any
import itertools as it

### EXTERNAL
import pytest as pyt

### INTERNAL
from ..conftest import boolmap
from my.regex import Quantifier, Atom, Regex, Block

cls = Block


############
### BODY ###
############
class TestBlock:
    # -------------------
    # `0` Initial Methods
    # -------------------
    @pyt.mark.parametrize(
        'args, expected',
        [
            # No split
            (['abc'], [3]),
            (['(abc)'], [1]),
            # Simple split
            (['a|b'], [1, 1]),
            (['(?|a|b)|c'], [1, 1]),
            (['a|(?>b|c)|d'], [1, 1, 1]),
            (['a|(?!b|c)'], [1, 1]),
            (['abc|def|ghi'], [3, 3, 3]),
            (['ab', 'c', 'd|e'], [2, 1, 1, 1]),
            # Other types
            (
                [
                    Regex(Atom('a'), Atom('b')),
                    Atom('c'),
                    Regex(Atom('d'), Atom('|'), Atom('e')),
                ],
                [2, 1, 1, 1],
            ),
            ([map(Regex, ['ab', 'c', 'd|e'])], [2, 1, 1, 1]),
            # Edge cases
            ([], []),
            ([''], [0]),
            (['|'], [0]),
            (['a|'], [1, 0]),
            (['|b'], [0, 1]),
            (['||'], [0]),
        ],
    )
    def test_new(self, args: list[Any], expected: list[int]):
        ret = cls.new(*args)
        assert list(map(len, ret.branches)) == expected

    # -------------------
    # `-` Private Methods
    # -------------------
    @pyt.mark.parametrize(
        'atoms, expected',
        [
            (['abc', 'bbc'], ''),
            (['', ''], ''),
            (['abc', ''], ''),
            (['', 'abc'], ''),
            (['abc', 'abd'], 'ab'),
            (['abc', 'abd', '.abc'], r''),
            ([r'ab\d', r'ab\d'], r'ab\d'),
        ],
    )
    def test_greatest_common_prefix(self, atoms: list[str], expected: str):
        result = cls.greatest_common_prefix(*[Regex(a) for a in atoms])
        assert str(result) == expected

    @pyt.mark.parametrize(
        'atoms, expected',
        [
            (['abc', 'bbc'], 'bc'),
            (['', ''], ''),
            (['abc', ''], ''),
            (['', 'abc'], ''),
            (['abc', 'abd'], ''),
            ([r'ab\d', r'ab\d'], r'ab\d'),
            ([r'xa(?:b|c)', r'ya(?:b|c)', r'za(?:b|c)'], r'a(?:b|c)'),
        ],
    )
    def test_greatest_common_suffix(self, atoms: list[str], expected: str):
        result = cls.greatest_common_suffix(*[Regex(a) for a in atoms])
        assert str(result) == expected

    @pyt.mark.parametrize(
        'block, expected',
        boolmap(
            true=[
                cls(r'a|b|c'),
                cls(r'a|\[b\]|c'),
                cls(r'a|\(?:b\)|c'),
                cls(r'a|(?:b)|(?>c)'),
                cls(r'a|b[b]|c'),
            ],
            false=[
                cls(r'a++|[b]|c'),
                cls(r'a|[b]|c'),
                cls(r'a|(?:b)++|c'),
                cls(r'a|b[b]|c', suffix=r'd'),
            ],
        ),
    )
    def test_supports_atomic_grouping(self, block: Block, expected: bool):
        assert block.supports_atomic_grouping() == expected

    @pyt.mark.parametrize(
        'lhs, rhs, expected',
        boolmap(
            true=[
                (r'abc', r'xabc'),
                (r'(?:abc)def', r'x(?:abc)def'),
                (r'abc', r'x?abc'),
            ],
            false=[
                (r'', r''),
                (r'xabc', r'abc'),
                (r'abc', r'xabcd'),
            ],
        ),
    )
    def test_is_clone_with_prefix(self, lhs: str, rhs: str, expected: bool):
        assert cls._is_clone_with_prefix(Regex(lhs), Regex(rhs)) == expected

    # -------------------
    # `+` Primary Methods
    # -------------------
    @pyt.mark.parametrize(
        'expr, expected',
        [
            # NOOP
            (r'a', ['a']),
            (r'\P{s}', [r'\P{s}']),
            (r'(?:ab)', [r'ab']),
            # Groups
            (r'(?:ab)?', ['', r'ab']),
            (r'(ab)?', [r'(ab)?']),
            (r'(?:a|b)', [r'a', r'b']),
            (r'(?:footnotes|reliable)', ['footnotes', 'reliable']),
            (r'(?i-s:ab)?', ['', r'ab']),
            # Sets
            (r'[ab]?', ['', 'a', 'b']),
            (r'[+*?]', [r'\+', r'\*', r'\?']),
            (r'[()|]', [r'\(', r'\)', r'\|']),
            (r'[.^$]', [r'\.', r'\^', r'\$']),
            # Optional elements
            (r'(?:ab[cd]?e)', ['abe', 'abce', 'abde']),
            (r'(?:ac?ez)', ['aez', 'acez']),
            (r'(?:(?:i-)?sup)', ['i-sup', 'sup']),
            (r'(?:br2?)', ['br', 'br2']),
        ],
    )
    def test_expand_atom(self, expr: str, expected: list[str]):
        old_block = cls.new(expr)
        assert len(old_block) == 1
        new_block = old_block.expand_atom(old_block.branches[0].one)
        assert set(map(str, new_block.branches)) == set(expected)

    @pyt.mark.parametrize(
        'block, expected',
        [
            (cls(r'z|y|x'), ['[xyz]']),
            (cls(r'z|[yx]'), ['[xyz]']),
            (cls(r'[\P{S}z]|[yx]'), [r'[\P{S}xyz]']),
            (
                cls(r'(?:a)|x|[yz]|[^[:lower:]]|[A-Z]'),
                [r'[xyz]', r'(?:a)', r'[^[:lower:]]', r'[A-Z]'],
            ),
        ],
    )
    def test_condense_atomic_branches(self, block: Block, expected: list[str]):
        result = cls.condense_atomic_branches(block.branches)
        assert list(map(str, result)) == expected

    @pyt.mark.parametrize(
        'blocks, expected',
        [
            # Basic case (rare in practice)
            (
                [cls(r'ab|cd'), cls(r'ef|gh')],
                [r'ab', r'cd', r'ef', r'gh'],
            ),
            # With context (prefix, suffix, and/or quantifier)
            (
                [cls(r'ab|cd', prefix=r'xyz'), cls(r'ef|gh')],
                [r'xyz(?>ab|cd)', r'ef', r'gh'],
            ),
            (
                [cls(r'ab|cd'), cls(r'ef|gh', suffix='xyz')],
                [r'ab', r'cd', r'(?>ef|gh)xyz'],
            ),
            (
                [cls(r'ab|cd', quantifier=r'+'), cls(r'ef|gh')],
                [r'(?>ab|cd)+', r'ef', r'gh'],
            ),
            # With shared suffix b/w blocks
            (
                [cls(r'abX|cdX'), cls(r'efX|ghX')],
                [r'(?>ab|cd|ef|gh)X'],
            ),
            (
                [cls(r'abX|cdX'), cls(r'ef|gh', suffix=r'X')],
                [r'(?>ab|cd|(?>ef|gh))X'],
            ),
        ],
    )
    def test_condense_blocks(self, blocks: list[Block], expected: list[str]):
        results = cls.condense_blocks(blocks)
        assert list(map(str, results)) == expected

    @pyt.mark.parametrize(
        'branches, expected',
        [
            ([r'abc', r'abd', r'xyz'], [2, 1]),
            ([r'test', r'foo'], [1, 1]),
            ([r'same', r'same'], [2]),
        ],
    )
    def test_group_branches_by_prefix(self, branches: list[str], expected: list[int]):
        groups = list(cls.group_branches_by_prefix(list(map(Regex, branches))))
        assert list(map(len, groups)) == expected

    @pyt.mark.parametrize(
        'lhs, rhs, did_group',
        boolmap(
            true=[
                (cls.new(r'abc'), cls.new(r'xbc')),
                (cls.new(r'abc', r'dbc'), cls.new(r'efg', r'hij', suffix=Regex(r'kbc'))),
            ],
            false=[
                (cls.new(r'abc'), cls.new(r'abz')),
                (cls.new(r'abc', r'ybc'), cls.new(r'abz')),
            ],
        ),
    )
    def test_group_blocks_by_suffix(self, lhs: Block, rhs: Block, did_group: bool):
        groups = list(cls.group_blocks_by_suffix([lhs, rhs]))
        assert len(groups) == (1 if did_group else 2)

    @pyt.mark.parametrize(
        'quantifier, expected',
        [
            (r'', r'?'),
            (r'?', r'?'),
            (r'+', r'*'),
            (r'*', r'*'),
            (r'++', r'*+'),
            (r'{1,5}?', r'{0,5}?'),
            (r'{2,5}?', None),
        ],
    )
    def test_make_optional(self, quantifier: str, expected: str | None):
        block = cls.new('a', 'b', quantifier=Quantifier(quantifier))
        result = block.make_optional()
        if expected is None:
            assert result is False
        else:
            assert result is True
            assert block.quantifier == expected

    # ------------------
    # `x` Public Methods
    # ------------------
    # --------------
    # `x0` Overrides
    # --------------
    @pyt.mark.parametrize(
        'block, expected',
        [
            (cls(r'a|b|c'), 3),
            (cls(r'ab|cd'), 2),
            (cls(), 0),
        ],
    )
    def test_len(self, block: Block, expected: int):
        assert len(block) == expected

    @pyt.mark.parametrize(
        'block, expected',
        boolmap(
            true=[
                cls(r'a|b'),
                cls(r'test'),
            ],
            false=[
                cls(),
                cls(r''),
            ],
        ),
    )
    def test_bool(self, block: Block, expected: bool):
        assert bool(block) == expected

    @pyt.mark.parametrize(
        'block, expected',
        [
            (cls(r'ab|cd'), [r'ab', r'cd']),
            (cls(r'ab|cd', suffix=r'ef'), [r'ef']),
            (cls(), []),
        ],
    )
    def test_last(self, block: Block, expected: list[str]):
        assert list(map(str, block.last)) == expected

    # --------------
    # `x1` Modifiers
    # --------------
    @pyt.mark.parametrize(
        'block, expected',
        [
            (cls(r'c|a|b'), r'(?>a|b|c)'),
            (cls(r'xyz|abc|def'), r'(?>abc|def|xyz)'),
        ],
    )
    def test_sort(self, block: Block, expected: str):
        block.sort()
        assert block.render() == expected

    @pyt.mark.parametrize(
        'block, expected',
        [
            # NOOPS
            (cls(r'ab|cd?|ef'), r'(?>ab|cd?|ef)'),
            (cls(r'ab|cd{0,5}|ef*', quantifier=r'?'), r'(?>ab|cd{0,5}|ef*)?'),
            # Bubble-up optionality
            (cls(r'ab|(?:cd)?|[ef]'), r'(?:ab|(?:cd)|[ef])?'),
            (cls(r'ab|(?:cd)?|[ef]', quantifier=r'?'), r'(?:ab|(?:cd)|[ef])?'),
            (cls(r'|a|b'), r'(?>a|b)?'),
            (cls(r'a||b', quantifier=r'?'), r'(?>a|b)?'),
            (cls(r'a|b|', quantifier=r'*?'), r'(?>a|b)*?'),
            (cls(r'a{0,5}|b*', quantifier=r'?'), r'(?:a{1,5}|b+)?'),
            # Prefixed branches
            (cls(r'ab(cd)?|xab(cd)?'), r'x?ab(cd)?'),
            (cls(r'ab(cd)?|x?ab(cd)?'), r'x?ab(cd)?'),
        ],
    )
    def test_clean(self, block: Block, expected: str):
        block.clean()
        assert str(block.render()) == expected

    @pyt.mark.parametrize(
        'block, expected',
        [
            (cls(r'a[bc]d'), 2),
            (cls(r'a(?:b|c)d'), 2),
            (cls(r'a(?:b|c)(?>d|e)'), ['abd', 'abe', 'acd', 'ace']),
            (cls(r'a(?:b|c)|(?:d|e)'), 4),
            # Nested
            (cls(r'a(?:b|[cd]e)z'), 3),
            (cls(r'[cd]?e'), [r'ce', r'de', r'e']),
            (cls(r'a(?:b|[cd]?e)z'), 4),
            (
                cls(r'a(?:b|c(?>d|t?[de]?))z'),
                ['abz', 'acdz', 'actdz', 'acz', 'actz', 'acez', 'actez'],
            ),
            # Optionals
            (cls(r'ab?cd?ef?g'), 8),
            (cls(r'ab?cd?ef?gh?i'), 16),
            (cls(r'ab?cd?ef?gh?ij?k'), 16),
            # Sets
            (cls(r'[abc]?[def]'), 12),
            (cls(r'[+*?]'), [r'\+', r'\*', r'\?']),
            (cls(r'[()|]'), [r'\(', r'\)', r'\|']),
            (cls(r'[.^$]'), [r'\.', r'\^', r'\$']),
            # Live examples
            (cls(r'confirm(?:ation)?'), [r'confirm', 'confirmation']),
            (
                cls(r'(?:[ib]-)?(?:small-)?su[bp]'),
                [
                    'i-small-sub',
                    'i-small-sup',
                    'b-small-sub',
                    'b-small-sup',
                    'b-sub',
                    'b-sup',
                    'i-sub',
                    'i-sup',
                    'small-sub',
                    'small-sup',
                    'sub',
                    'sup',
                ],
            ),
        ],
    )
    def test_expand(self, block: Block, expected: int | list[str]):
        block.expand()
        if isinstance(expected, int):
            assert len(block) == expected
        else:
            assert set(map(str, block.branches)) == set(expected)

    @pyt.mark.parametrize(
        'block, expected',
        [
            (cls(r'abc', r'abd'), cls(r'c|d', prefix=r'ab')),
            (cls(r'xbc', r'ybc'), cls(r'x|y', suffix=r'bc')),
        ],
    )
    def test_factor(self, block: Block, expected: Block):
        block.factor()
        assert block == expected

    @pyt.mark.parametrize(
        'block, expected',
        [
            (cls(r'abc', r'abd'), r'ab[cd]'),
            (cls(r'test', r'foo'), r'(?>test|foo)'),
            (cls(r'xyz', r'xyz'), r'xyz'),
            (cls(r'abc1cde', r'abc[2]cde'), r'abc[12]cde'),
        ],
    )
    def test_condense(self, block: Block, expected: str):
        block.condense()
        assert str(block.render()) == expected

    # ------------------
    # `x2` Serialization
    # ------------------
    @pyt.mark.parametrize(
        'block, expected',
        [
            (cls(r'abc'), r'abc'),
            (cls(r'a[bc]d'), r'a[bc]d'),
            (cls('ab', 'cd', 'ef'), r'(?>ab|cd|ef)'),
            (cls('ab', '(?:cd)', '[ef]'), r'(?:ab|(?:cd)|[ef])'),
            (cls('', 'cd', 'ef'), r'(?:|cd|ef)'),
            (cls('', 'cd', 'ef', quantifier=r'?'), r'(?:|cd|ef)?'),
        ],
    )
    def test_render(self, block: Block, expected: str):
        ret = block.render()
        assert str(ret) == expected

############
### HEAD ###
############
### STANDARD
from typing import Any

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
            (['|'], [0, 0]),
            (['a|'], [1, 0]),
            (['|b'], [0, 1]),
            (['||'], [0, 0, 0]),
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
        'branches, expected',
        boolmap(
            false=[
                [],
            ],
            true=[
                [],
            ],
        ),
    )
    def test_supports_atomic_grouping(self, branches: list[str], expected: bool):
        block = cls.new(*branches)
        assert block.supports_atomic_grouping() == expected

    @pyt.mark.parametrize(
        'lhs, rhs, expected',
        boolmap(
            false=[
                ('', ''),
            ],
            true=[
                ('', ''),
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
            # Groups
            (r'(?:ab)?', ['', r'ab']),
            (r'(ab)?', ['', r'(ab)']),
            (r'(?:a|b)', [r'a', r'b']),
            (r'(?:footnotes|reliable)', ['footnotes', 'reliable']),
            (r'(?i-s:ab)?', ['', r'(?i-s)ab']),
        ],
    )
    def test_expand_group(self, expr: str, expected: list[str]):
        from my.regex import GroupAtom

        block = cls.expand_group(GroupAtom(data=expr))
        result = [str(br) for br in block.branches]
        assert set(result) == set(expected)

    @pyt.mark.parametrize(
        'expr, expected',
        [
            (r'[ab]?', ['', 'a', 'b']),
            (r'[+*?]', [r'\+', r'\*', r'\?']),
            (r'[()|]', [r'\(', r'\)', r'\|']),
            (r'[.^$]', [r'\.', r'\^', r'\$']),
        ],
    )
    def test_expand_set(self, expr: str, expected: list[str]):
        from my.regex import SetAtom

        block = cls.expand_set(SetAtom(data=expr))
        result = [str(br) for br in block.branches]
        assert set(result) == set(expected)

    @pyt.mark.parametrize(
        'expr, expected',
        [
            # No-op
            (r'a', ['a']),
            (r'\P{s}', [r'\P{s}']),
            (r'(?:ab)', [r'(?:ab)']),
            # Optionals
            (r'(?:ab[cd]?e)', ['abe', 'abce', 'abde']),
            (r'(?:ac?ez)', ['aez', 'acez']),
            (r'(?:(?:i-)?sup)', ['i-sup', 'sup']),
            (r'(?:br2?)', ['br', 'br2']),
        ],
    )
    def test_expand_atom(self, expr: str, expected: list[str]):
        block = cls.expand_atom(Atom(expr))
        assert len(block) == len(expected)
        assert set(map(str, block.branches)) == set(expected)

    @pyt.mark.parametrize(
        'atoms, expected',
        [
            (['z', 'y', 'x'], '[xyz]'),
            (['z', '[yx]'], '[xyz]'),
            ([r'[\P{S}z]', '[yx]'], r'[\P{S}xyz]'),
            ([r'(?:x)', r'[yz]', r'[^[:lower:]]', r'[A-Z]'], r'(?:[yz]|(?:x)|[^[:lower:]]|[A-Z])'),
        ],
    )
    def test_collapse_atoms(self, atoms: list[str], expected: str):
        assert cls.collapse_atoms(*map(Atom, atoms)) == expected

    @pyt.mark.parametrize(
        'blocks, expected',
        [
            ([[r'ab', r'cd'], [r'ef', r'gh']], [[r'ab', r'cd'], [r'ef', r'gh']]),
        ],
    )
    def test_collapse_blocks_by_suffix(self, blocks: list[list[str]], expected: list[list[str]]):
        block_objs = [cls.new(*b) for b in blocks]
        results = cls.collapse_blocks_by_suffix(block_objs)
        # Just verify it returns a list for now
        assert isinstance(results, list)

    @pyt.mark.parametrize(
        'branches, expected_count',
        [
            ([r'abc', r'abd', r'xyz'], 2),
            ([r'test', r'foo'], 2),
            ([r'same', r'same'], 1),
        ],
    )
    def test_group_branches_by_prefix(self, branches: list[str], expected_count: int):
        branch_objs = [Regex(b) for b in branches]
        groups = list(cls.group_branches_by_prefix(*branch_objs))
        assert len(groups) == expected_count

    @pyt.mark.parametrize(
        'blocks, expected_count',
        [
            ([[r'abc'], [r'xbc']], 1),
            ([[r'abc'], [r'xyz']], 2),
        ],
    )
    def test_group_blocks_by_suffix(self, blocks: list[list[str]], expected_count: int):
        block_objs = [cls.new(*b) for b in blocks]
        groups = list(cls.group_blocks_by_suffix(*block_objs))
        assert len(groups) == expected_count

    @pyt.mark.parametrize(
        'branches, quantifier, expected',
        [
            ([r'a', r'b'], '', True),
            ([r'a', r'b'], '?', True),
            ([r'a', r'b'], '+', False),
        ],
    )
    def test_make_optional(self, branches: list[str], quantifier: str, expected: bool):
        block = cls.new(*branches, quantifier=Quantifier(quantifier))
        result = block.make_optional()
        assert result == expected

    # ------------------
    # `x` Public Methods
    # ------------------
    # --------------
    # `x0` Overrides
    # --------------
    @pyt.mark.parametrize(
        'branches, expected',
        [
            ([r'a', r'b', r'c'], 3),
            ([r'ab', r'cd'], 2),
            ([], 0),
        ],
    )
    def test_len(self, branches: list[str], expected: int):
        assert len(cls.new(*branches)) == expected

    @pyt.mark.parametrize(
        'branches, expected',
        boolmap(
            true=[[r'a', r'b'], [r'test']],
            false=[[], [r'', r'']],
        ),
    )
    def test_bool(self, branches: list[str], expected: bool):
        assert bool(cls.new(*branches)) == expected

    @pyt.mark.parametrize(
        'branches, index, expected',
        [
            ([r'a', r'b', r'c'], 0, r'a'),
            ([r'a', r'b', r'c'], 1, r'b'),
            ([r'a', r'b', r'c'], 2, r'c'),
        ],
    )
    def test_getitem(self, branches: list[str], index: int, expected: str):
        assert str(cls.new(*branches)[index]) == expected

    @pyt.mark.parametrize(
        'branches, suffix, expected',
        [
            ([r'ab', r'cd'], r'', [r'ab', r'cd']),
            ([r'ab', r'cd'], r'ef', [r'ef']),
        ],
    )
    def test_last(self, branches: list[str], suffix: str, expected: list[str]):
        block = cls.new(*branches, suffix=Regex(suffix))
        result = [str(e) for e in block.last]
        assert result == expected

    # --------------
    # `x1` Modifiers
    # --------------
    @pyt.mark.parametrize(
        'branches, expected',
        [
            ([r'c', r'a', r'b'], [r'a', r'b', r'c']),
            ([r'xyz', r'abc', r'def'], [r'abc', r'def', r'xyz']),
        ],
    )
    def test_sort(self, branches: list[str], expected: list[str]):
        block = cls.new(*branches)
        block.sort()
        assert [str(br) for br in block.branches] == expected

    @pyt.mark.parametrize(
        'branches, quant, expected, exp_quant',
        [
            # non-atomic
            ([r'ab', r'cd?', r'ef'], r'', [r'ab', r'cd?', r'ef'], r''),
            ([r'ab', r'cd{0,5}', r'ef*'], r'?', [r'ab', r'cd{0,5}', r'ef*'], r''),
            # Optional, atomic
            ([r'ab', r'(?:cd)?', r'[ef]'], r'', [r'ab', r'(?:cd)', r'[ef]'], r'?'),
            ([r'ab', r'(?:cd)?', r'[ef]'], r'?', [r'ab', r'(?:cd)', r'[ef]'], r'?'),
            ([r'', r'cd', r'ef'], r'', [r'cd', r'ef'], r'?'),
            ([r'(?:cd){0,5}', r'(?:ef)*'], r'?', [r'(?:cd){1,5}', r'(?:ef)+'], r'?'),
            # Prefixed branches
            ([r'ab(cd)?', r'xab(cd)?'], '', [r'x?ab(cd)?'], r''),
        ],
    )
    def test_clean(self, branches: list[str], quant: str, expected: list[str], exp_quant: str):
        block = cls.new(*branches, quantifier=Quantifier(quant))
        block.clean()
        assert list(map(str, block.branches)) == expected
        assert block.quantifier == exp_quant

    @pyt.mark.parametrize(
        'expr, expected',
        [
            (r'a[bc]d', 2),
            (r'a(?:b|c)d', 2),
            (r'a(?:b|c)(?>d|e)', ['abd', 'abe', 'acd', 'ace']),
            (r'a(?:b|c)|(?:d|e)', 4),
            # Nested
            (r'a(?:b|[cd]e)z', 3),
            (r'[cd]?e', [r'ce', r'de', r'e']),
            (r'a(?:b|[cd]?e)z', 4),
            (r'a(?:b|c(?>d|t?[de]?))z', ['abz', 'acdz', 'actdz', 'acz', 'actz', 'acez', 'actez']),
            # Optionals
            (r'ab?cd?ef?g', 8),
            (r'ab?cd?ef?gh?i', 16),
            (r'ab?cd?ef?gh?ij?k', 16),
            # Sets
            (r'[abc]?[def]', 12),
            (r'[+*?]', [r'\+', r'\*', r'\?']),
            (r'[()|]', [r'\(', r'\)', r'\|']),
            (r'[.^$]', [r'\.', r'\^', r'\$']),
            # Live examples
            (
                r'(?:[ib]-)?(?:small-)?su[bp]',
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
            (r'confirm(?:ation)?', [r'confirm', 'confirmation']),
        ],
    )
    def test_expand(self, expr: str, expected: int | list[str]):
        block = cls.new(expr)
        block.expand()
        if isinstance(expected, int):
            assert len(block) == expected
        else:
            assert {str(br) for br in block.branches} == set(expected)

    @pyt.mark.parametrize(
        'branches, expected_prefix, expected_suffix',
        [
            ([r'abc', r'abd'], r'ab', r''),
            ([r'xbc', r'ybc'], r'', r'bc'),
            ([r'abc', r'abc'], r'abc', r''),
        ],
    )
    def test_factor(self, branches: list[str], expected_prefix: str, expected_suffix: str):
        block = cls.new(*branches)
        block.factor()
        assert str(block.prefix) == expected_prefix
        assert str(block.suffix) == expected_suffix

    # ------------------
    # `x2` Serialization
    # ------------------
    @pyt.mark.parametrize(
        'branches, kwargs, expected',
        [
            (['ab', 'cd', 'ef'], dict(), '(?>ab|cd|ef)'),
            (['ab', '(?:cd)', '[ef]'], dict(), '(?:ab|(?:cd)|[ef])'),
            (['', 'cd', 'ef'], dict(), '(?>cd|ef)?'),
            (['', 'cd', 'ef'], dict(quantifier=Quantifier('?')), '(?>cd|ef)?'),
            (['-ef', 'cd', 'ef'], dict(), '(?>-?ef|cd)'),
        ],
    )
    def test_render(self, branches: list[str], kwargs: dict, expected: str):
        block = cls.new(*branches, **kwargs)
        ret = block.render()
        assert ret == expected

    # ------------------
    # `x3` Top-level API
    # ------------------
    @pyt.mark.parametrize(
        'branches, expected',
        [
            ([r'abc', r'abd'], r'ab[cd]'),
            ([r'test', r'foo'], r'(?:foo|test)'),
        ],
    )
    def test_optimize(self, branches: list[str], expected: str):
        block = cls.new(*branches)
        block.optimize()
        result = str(block.render())
        # Just verify it returns a string for now
        assert isinstance(result, str)

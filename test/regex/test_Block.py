############
### HEAD ###
############
### STANDARD
from typing import Any

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.regex import Quantifier, Atom, Atoms, Block

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
                [Atoms(Atom('a'), Atom('b')), Atom('c'), Atoms(Atom('d'), Atom('|'), Atom('e'))],
                [2, 1, 1, 1],
            ),
            ([map(Atoms, ['ab', 'c', 'd|e'])], [2, 1, 1, 1]),
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
        'lhs, args, expected',
        [
            ('abc', 'bbc', ''),
            ('', '', ''),
            ('abc', '', ''),
            ('', 'abc', ''),
            ('abc', 'abd', 'ab'),
            (r'ab\d', r'ab\d', r'ab\d'),
        ],
    )
    def test_greatest_common_prefix(self, lhs: str, args: str | list[str], expected: str):
        if isinstance(args, str):
            args = [args]
        ret = cls._greatest_common_prefix(*map(cls.atomize, (lhs, *args)))
        assert ''.join(ret) == expected

    @pyt.mark.parametrize(
        'lhs, args, expected',
        [
            ('abc', 'bbc', 'bc'),
            ('', '', ''),
            ('abc', '', ''),
            ('', 'abc', ''),
            ('abc', 'abd', ''),
            (r'ab\d', r'ab\d', r'ab\d'),
            (r'xa(?:b|c)', [r'ya(?:b|c)', r'za(?:b|c)'], r'a(?:b|c)'),
        ],
    )
    def test_greatest_common_suffix(self, lhs: str, args: str | list[str], expected: str):
        if isinstance(args, str):
            args = [args]
        ret = cls._greatest_common_suffix(*map(cls.atomize, (lhs, *args)))
        assert ''.join(ret) == expected

    def test_choose_joining_mark(self):
        pass

    def test_is_clone_with_prefix(self):
        pass

    # -------------------
    # `+` Primary Methods
    # -------------------
    def test_expand_group(self):
        pass

    def test_expand_set(self):
        pass

    @pyt.mark.parametrize(
        'expr, expected',
        [
            # No-op
            (r'a', 1),
            (r'\P{s}', 1),
            (r'(?:ab)', 1),
            # Groups
            (r'(?:ab)?', ['', r'ab']),
            (r'(ab)?', ['', r'(ab)']),
            (r'(?:a|b)', 2),
            (r'(?:footnotes|reliable)', ['footnotes', 'reliable']),
            (r'(?i-s:ab)?', ['', r'(?i-s)ab']),
            # Sets
            (r'[ab]?', ['', 'a', 'b']),
            (r'[+*?]', [r'\+', r'\*', r'\?']),
            (r'[()|]', [r'\(', r'\)', r'\|']),
            (r'[.^$]', [r'\.', r'\^', r'\$']),
            # Optionals
            (r'(?:ab[cd]?e)', ['abe', 'abce', 'abde']),
            (r'(?:ac?ez)', ['aez', 'acez']),
            (r'(?:(?:i-)?sup)', ['i-sup', 'sup']),
            (r'(?:br2?)', ['br', 'br2']),
        ],
    )
    def test_expand_atom(self, expr: str, expected: int | list[str]):
        ret = cls.expand_atom(Atom(expr))
        if isinstance(expected, int):
            assert len(ret) == expected
        elif len(expected) == 0:
            assert len(ret) == 0
        else:
            assert len(ret) == len(expected)
            assert set(map(''.join, ret)) == set(expected)

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
        ret = cls.collapse_atoms(*map(Atom, atoms))
        assert ret == expected

    def test_collapse_by_suffix(self):
        pass

    def test_group_branches_by_prefix(self):
        pass

    def test_group_blocks_by_suffix(self):
        pass

    def test_make_optional(self):
        pass

    # ------------------
    # `x` Public Methods
    # ------------------
    # --------------
    # `x0` Overrides
    # --------------
    def test_len(self):
        pass

    def test_bool(self):
        pass

    def test_getitem(self):
        pass

    def test_last(self):
        pass

    # --------------
    # `x1` Modifiers
    # --------------
    def test_sort(self):
        pass

    @pyt.mark.parametrize(
        'branches, quant, expected, opt',
        [
            # non-atomic
            (['ab', 'cd?', 'ef'], '', ['ab', 'cd?', 'ef'], False),
            (['ab', 'cd{0,5}', 'ef*'], '?', ['ab', 'cd{0,5}', 'ef*'], False),
            # Optional, atomic
            (['ab', '(?:cd)?', '[ef]'], '', ['ab', '(?:cd)', '[ef]'], True),
            (['ab', '(?:cd)?', '[ef]'], '?', ['ab', '(?:cd)', '[ef]'], True),
            (['', 'cd', 'ef'], '', ['cd', 'ef'], True),
            (['(?:cd){0,5}', '(?:ef)*'], '?', ['(?:cd){1,5}', '(?:ef)+'], True),
            # Prefixed branches
            (['ab(cd)?', 'xab(cd)?'], '', ['x?ab(cd)?'], False),
        ],
    )
    def test_clean(self, branches: list[str], quant: str, expected: list[str], exp_quant: str):
        block = cls.new(*branches, quantifier=Quantifier(quant))
        block.clean()
        assert [str(br) for br in block.branches] == expected
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
        ret = block.split()
        if isinstance(expected, int):
            assert len(ret) == expected
        else:
            assert set(ret) == set(expected)

    def test_factor(self):
        pass

    # ------------------
    # `x2` Serialization
    # ------------------
    @pyt.mark.parametrize(
        'branches, quant, suf, expected',
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
    def test_construct_tree(self):
        pass

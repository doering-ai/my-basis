############
### HEAD ###
############
### STANDARD

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.text import (RegexStore, RgxList, RgxVal, GroupKind)

Captures = dict[str, list[str]]
Params = dict[str, str]
Atom = str
Atoms = tuple[str, ...]
Span = tuple[int, int]

############
### DATA ###
############
cls = RegexStore


############
### BODY ###
############
class TestRegexStore:
    @pyt.fixture(scope='class')
    def store(self) -> RegexStore:
        return RegexStore.new(
            dict(
                separator=r' ?',
                autostrip_brackets=True,
            ),
            _parenthetical=(r'\(\w+\)', lambda s: s.strip('() ')),
        )

    def test_new(self, store: RegexStore) -> None:
        assert len(store.patterns) == len(store.definitions)

    @pyt.mark.parametrize(
        'mark, expected', [
            ('[]:', (GroupKind.PLAIN, '(?:', '', '')),
            ('[]>*+', (GroupKind.ATOMS, '(?>', '', '*+')),
            ('|:?', (GroupKind.PLAIN, '(?:', '|', '?')),
            ('|?', (GroupKind.MULTI, '(?|', '|', '?')),
            ('[ ]!', (GroupKind.NOT_AHEAD, '(?!', ' ', '')),
            ('[a]<={2,}', (GroupKind.BEHIND, '(?<=', 'a', '{2,}')),
            (':m-is', (GroupKind.PLAIN, r'(?m-is:', r' ?', '')),
            ('m-is', (GroupKind.POSIT, r'((?m-is)', r' ?', '')),
            ('[ *]:{2,}?', (GroupKind.PLAIN, r'(?:', r' *', '{2,}?')),
        ]
    )
    def test_parse_mark(self, mark: str, expected: tuple[str, str, str], store: RegexStore):
        assert store._parse_mark(mark) == expected

    @pyt.mark.parametrize(
        'text, body, quant', [
            (r'ab[cd]*?ef', 'cd', '*?'),
            (r'ab\[cd\]ef', '', ''),
            (r'ab[(?:cd)+]ef', '(?:cd)+', ''),
            (r'ab[^[:lower:]A-Z]ef', r'^[:lower:]A-Z', ''),
            (r'ab[\[|\]\[[:lower:]\]]+?cd', r'\[|\]\[[:lower:]\]', '+?'),
        ]
    )
    def test_set_iterator(self, text: str, body: str, quant: str):
        ret = next(cls.set_iterator(text), None)  # type: ignore
        if not body:
            assert ret is None
        else:
            assert ret is not None
            assert ret[1:] == (body, quant)

    @pyt.mark.parametrize(
        'text, kind, name, body, quant', [
            (r'ab(cd)ef', GroupKind.POSIT, '', 'cd', ''),
            (r'ab(?:cd)+ef', GroupKind.PLAIN, '', 'cd', '+'),
            (r'ab\\(?:cd\\)+ef', GroupKind.PLAIN, '', r'cd\\', '+'),
            (r'ab\(?:cd\)+ef', GroupKind(0), '', '', ''),
            (r'ab[a-b](?:cd)+ef', GroupKind.PLAIN, '', 'cd', '+'),
            (r'ab\[(?:cd)+\]ef', GroupKind.PLAIN, '', 'cd', '+'),
            (r'ab[(?:cd)+]ef', GroupKind(0), '', '', ''),
        ]
    )
    def test_group_iterator(self, text: str, kind: GroupKind, name: str, body: str, quant: str):
        ret = next(cls.group_iterator(text), None)  # type: ignore
        if kind == GroupKind(0):
            assert ret is None
        else:
            assert ret is not None
            assert ret[1:] == (kind, name, body, quant)

    @pyt.mark.parametrize(
        'text, expected',
        [
            # Simple pattern with no groups
            ('abc', ['a', 'b', 'c']),
            ('(?=abc)', ['(?=abc)']),
            ('a(bc)d', ['a', '(bc)', 'd']),
            ('(?=ab)(?<!cd)', ['(?=ab)', '(?<!cd)']),
            ('a(b(c)d)e', ['a', '(b(c)d)', 'e']),
            ('a.b*c+', ['a', '.', 'b*', 'c+']),
            (r'[[:alpha:]]+[A[:lower:]Z]', ['[[:alpha:]]+', '[A[:lower:]Z]']),

            # Optional characters
            (r'a?', [r'a?']),
            (r'a?b?c?', ['a?', 'b?', 'c?']),

            # No-ops
            (r'[()|]', [r'[()|]']),

            # Edge cases
            ('', []),
            ('()', ['()']),
            (r'|\||', ['|', r'\|', '|']),
        ]
    )
    def test_atomize(self, text: str, expected: list[str]):
        ret = cls.atomize(text)
        assert ret == tuple(expected)

    @pyt.mark.parametrize(
        'lhs, args, expected', [
            ('abc', 'bbc', ''),
            ('', '', ''),
            ('abc', '', ''),
            ('', 'abc', ''),
            ('abc', 'abd', 'ab'),
            (r'ab\d', r'ab\d', r'ab\d'),
        ]
    )
    def test_greatest_common_prefix(self, lhs: str, args: str | list[str], expected: str):
        if isinstance(args, str):
            args = [args]
        ret = cls._greatest_common_prefix(*map(cls.atomize, (lhs, *args)))
        assert ''.join(ret) == expected

    @pyt.mark.parametrize(
        'lhs, args, expected', [
            ('abc', 'bbc', 'bc'),
            ('', '', ''),
            ('abc', '', ''),
            ('', 'abc', ''),
            ('abc', 'abd', ''),
            (r'ab\d', r'ab\d', r'ab\d'),
            (r'xa(?:b|c)', [r'ya(?:b|c)', r'za(?:b|c)'], r'a(?:b|c)'),
        ]
    )
    def test_greatest_common_suffix(self, lhs: str, args: str | list[str], expected: str):
        if isinstance(args, str):
            args = [args]
        ret = cls._greatest_common_suffix(*map(cls.atomize, (lhs, *args)))
        assert ''.join(ret) == expected

    @pyt.mark.parametrize(
        'atom, expected', [
            (r'', 0),
            (r'a', 0),
            (r'\(', 0),
            (r'(abc)', 1),
            (r'(?:abc)', 1),
            (r'(?>abc)', 1),
            (r'(?P=abc)', 1),
            (r'(?P=abc)', 1),
            (r'(?:a|b)', 1),
            (r'[+*?]', 0),
        ]
    )
    def test_is_group(self, atom: Atom, expected: int | bool):
        assert cls._is_atomic(atom) or not atom
        ret = cls._is_group(atom)
        assert ret == bool(expected)

    @pyt.mark.parametrize(
        'atom, expected', [
            (r'a', 0),
            (r'a?', 0),
            (r'a+', 1),
            (r'a*+', 1),
            (r'a*?', 1),
            (r'a{1,}', 1),
            (r'a{0,5}', 1),
            (r'a{0,5}?', 1),
            (r'[abc]', 0),
            (r'[abc]+', 1),
        ]
    )
    def test_is_quantified(self, atom: str, expected: int | bool):
        assert cls._is_atomic(atom) or not atom
        ret = cls._is_quantified(atom)
        assert ret == bool(expected)

    @pyt.mark.parametrize('atom, expected', [
        (r'[cd]', 0),
        (r'[cd]?', 1),
        (r'\?', 0),
    ])
    def test_is_optional(self, atom: Atom, expected: int | bool):
        assert cls._is_atomic(atom) or not atom
        assert cls._is_optional(atom) == bool(expected)

    @pyt.mark.parametrize(
        'atom, expected',
        [
            (r'', 0),
            (r'a', 1),

            # Groups & quantifiers
            (r'(?:abc)', 0),
            (r'(?:abc)+', 0),
            (r'a+', 0),
            (r'a*+', 0),
            (r'\+', 1),
            (r'\++', 0),
            (r'\+{1,}', 0),
            (r'a?', 1),

            # Sets
            (r'[abc]', 1),
            (r'[a-z]', 0),
            (r'[ab--c]', 0),
            (r'[-az]', 1),
            (r'[ab\p{Sc}\P{x}]', 1),
            (r'[\[|\]\[[:lower:]\]]', 1),
            (r'[+*?]', 1),
            (r'[()|]', 1),
            (r'[.^$]', 1),
        ]
    )
    def test_is_simple(self, atom: Atom, expected: int | bool):
        assert cls._is_atomic(atom) or not atom
        assert cls._is_simple(atom) == bool(expected)

    @pyt.mark.parametrize(
        'atom, expected', [
            ('a|b', 1),
            (['a', '|', 'b'], 1),
            ('|', 1),
            (['|'], 1),
            ('abc', 0),
            (['a', 'b', 'c'], 0),
            ('a[bc]d', 0),
        ]
    )
    def test_is_split(self, atom: Atom | Atoms, expected: int | bool, store: RegexStore):
        assert store._is_split(atom) == bool(expected)

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
        ]
    )
    def test_clean_branches(self, branches: list[str], quant: str, expected: list[str], opt: bool):
        ret_branches, is_opt = cls._clean_branches(list(map(cls.atomize, branches)), quant)
        assert list(map(''.join, ret_branches)) == expected
        assert is_opt == opt

    @pyt.mark.parametrize(
        'branches, quant, suf, expected', [
            (['ab', 'cd', 'ef'], '', False, '(?>ab|cd|ef)'),
            (['ab', '(?:cd)', '[ef]'], '', False, '(?:ab|(?:cd)|[ef])'),
            (['', 'cd', 'ef'], '', False, '(?>cd|ef)?'),
            (['', 'cd', 'ef'], '?', False, '(?>cd|ef)?'),
            (['-ef', 'cd', 'ef'], '', False, '(?>-?ef|cd)'),
        ]
    )
    def test_render_branches(self, branches: list[str], quant: str, suf: bool, expected: str):
        ret = cls._render_branches(list(map(cls.atomize, branches)), suf, quant)
        assert ret == expected

    @pyt.mark.parametrize(
        'atoms, expected', [
            (['z', 'y', 'x'], '[xyz]'),
            (['z', '[yx]'], '[xyz]'),
            ([r'[\P{S}z]', '[yx]'], r'[\P{S}xyz]'),
            ([r'(?:x)', r'[yz]', r'[^[:lower:]]', r'[A-Z]'], r'(?:[yz]|(?:x)|[^[:lower:]]|[A-Z])'),
        ]
    )
    def test_join_atoms(self, atoms: list[str], expected: str):
        ret = cls._join_atoms(atoms)
        assert ret == expected

    @pyt.mark.parametrize(
        'text, expected',
        [
            # No split
            ('abc', 1),
            ("(abc)", 1),

            # Simple split
            ("a|b", 2),
            ("(?|a|b)|c", 2),
            ("a|(?>b|c)|d", 3),
            ("a|(?!b|c)", 2),
            ("abc|def|ghi", 3),
            (["a|b", "c|d"], 4),

            # Edge cases
            ("", 0),
            ([], 0),
            ("|", 2),
            ("a|", 2),
            ("|b", 2),
            ("||", 3),
        ]
    )
    def test_split(self, text: str, expected: int, store: RegexStore):
        ret = store.split(text)
        assert len(ret) == expected

    @pyt.mark.parametrize(
        'text, expected',
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
        ]
    )
    def test_split_atom(self, text: str, expected: int | list[str], store: RegexStore):
        ret = store._split_atom(text)
        if isinstance(expected, int):
            assert len(ret) == expected
        elif len(expected) == 0:
            assert len(ret) == 0
        else:
            assert len(ret) == len(expected)
            assert set(map(''.join, ret)) == set(expected)

    @pyt.mark.parametrize(
        'text, expected',
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
                    'i-small-sub', 'i-small-sup', 'b-small-sub', 'b-small-sup', 'b-sub', 'b-sup',
                    'i-sub', 'i-sup', 'small-sub', 'small-sup', 'sub', 'sup'
                ],
            ),
            (r'confirm(?:ation)?', [r'confirm', 'confirmation']),
        ]
    )
    def test_recursive_split(self, text: str, expected: int | list[str], store: RegexStore):
        ret = store.split(text, True)
        if isinstance(expected, int):
            assert len(ret) == expected
        else:
            assert set(ret) == set(expected)

    @pyt.mark.parametrize(
        'definition, expected', [
            (
                ('|&{1,3}', '', ['alpha', '_beta'], r'\b,? ?'),
                r'(?:(?:(?&alpha)|(?&_beta))\b,? ?){1,3}',
            ),
            (
                ('|:-i{0,2}?', ['alpha', 'beta']),
                r'(?-i:alpha|beta){0,2}?',
            ),
            (
                ('|+?', ['one', 'two', ('[ *]:{2,}?', ['alpha', 'beta']), 'three', 'four']),
                r'(?|one|two|(?:alpha *beta){2,}?|three|four)+?',
            ),
            (
                ('|:*', r'', [('|:{1,3}', ['A', 'B'])], r'SUFFIX'),
                r'(?:(?:A|B){1,3}SUFFIX)*',
            ),
            (('[ *]:is', ['ab', 'cd']), r'(?is:ab *cd)'),
        ]
    )
    def test_compose_tuple(self, definition: RgxVal, expected: str, store: RegexStore):
        ret = store.compose(definition)
        assert ret == expected

    @pyt.mark.parametrize(
        'data, expected', [
            (['Alpha', 'Zeta', 'Beta'], r'(?>Alph|Bet|Zet)a'),
            (['Publish', 'Publishing', 'Published'], r'Publish(?>ed|ing)?'),
            (['Publisher', 'Publishing', 'Published'], r'Publish(?>e[dr]|ing)'),
            (['abcx', 'abcy'], r'abc[xy]'),
            (['abxc', 'abyc'], r'ab[xy]c'),
            (['axbc', 'aybc'], r'a[xy]bc'),
            (
                [
                    'Books', 'Company', 'Group', 'House', 'International', 'Library', 'Publishers',
                    'Publishing', 'Publications', 'Productions', 'Press', 'Pictures', 'Studios',
                    'UP'
                ],
                (
                    r'(?>Books|Company|Group|House|International|Library|'
                    r'P(?>(?>icture|r(?>es|oduction))s|ubli(?>cations|sh(?>ers|ing)))|Studios|UP)'
                ),
            ),
            (['is', 'in', 'into'], r'i(?>n(?:to)?|s)'),
            (
                [r'no-(?:footnotes|reliable-sources|significant-coverage)'],
                r'no-(?>(?>footnot|reliable-sourc)es|significant-coverage)',
            ),
            ([r'(?P=_ws)(?:p?p|P[Pp])\.(?!\S)'], r'(?P=_ws)(?:P[Pp]|pp?)\.(?!\S)'),
        ]
    )
    def test_compose_tree(self, data: RgxList, expected: str, store: RegexStore):
        ret = store.compose(('<|>', data))
        assert ret == expected

    def test_router_tree(self, store: RegexStore):
        store.define_router_tree('test', dict(alpha=r'[[:alpha:]]+', nums=r'\d+'))

        text_a = 'abc'
        assert store.match('test', text_a)
        assert store.route_match('test', text_a) == 'alpha'

        text_b = '123'
        assert store.match('test', text_b)
        assert store.route_match('test', text_b) == 'nums'

############
### HEAD ###
############
### STANDARD

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.regex import Atom, GroupKind

cls = Atom


############
### BODY ###
############
class TestAtom:
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
        ],
    )
    def test_atomize(self, text: str, expected: list[str]):
        ret = cls.atomize(text)
        assert ret == tuple(expected)

    @pyt.mark.parametrize(
        'text, body, quant',
        [
            (r'ab[cd]*?ef', 'cd', '*?'),
            (r'ab\[cd\]ef', '', ''),
            (r'ab[(?:cd)+]ef', '(?:cd)+', ''),
            (r'ab[^[:lower:]A-Z]ef', r'^[:lower:]A-Z', ''),
            (r'ab[\[|\]\[[:lower:]\]]+?cd', r'\[|\]\[[:lower:]\]', '+?'),
        ],
    )
    def test_set_iterator(self, text: str, body: str, quant: str):
        ret = next(cls.set_iterator(text), None)  # type: ignore
        if not body:
            assert ret is None
        else:
            assert ret is not None
            assert ret[1:] == (body, quant)

    @pyt.mark.parametrize(
        'text, kind, name, body, quant',
        [
            (r'ab(cd)ef', GroupKind.POSIT, '', 'cd', ''),
            (r'ab(?:cd)+ef', GroupKind.PLAIN, '', 'cd', '+'),
            (r'ab\\(?:cd\\)+ef', GroupKind.PLAIN, '', r'cd\\', '+'),
            (r'ab\(?:cd\)+ef', GroupKind(0), '', '', ''),
            (r'ab[a-b](?:cd)+ef', GroupKind.PLAIN, '', 'cd', '+'),
            (r'ab\[(?:cd)+\]ef', GroupKind.PLAIN, '', 'cd', '+'),
            (r'ab[(?:cd)+]ef', GroupKind(0), '', '', ''),
        ],
    )
    def test_group_iterator(self, text: str, kind: GroupKind, name: str, body: str, quant: str):
        ret = next(cls.group_iterator(text), None)  # type: ignore
        if kind == GroupKind(0):
            assert ret is None
        else:
            assert ret is not None
            assert ret[1:] == (kind, name, body, quant)

    @pyt.mark.parametrize(
        'atom, expected',
        [
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
        ],
    )
    def test_is_quantified(self, atom: str, expected: int | bool):
        assert cls._is_atomic(atom) or not atom
        ret = cls._is_quantified(atom)
        assert ret == bool(expected)

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
        ],
    )
    def test_is_simple(self, atom: Atom, expected: int | bool):
        assert cls._is_atomic(atom) or not atom
        assert cls._is_simple(atom) == bool(expected)

    @pyt.mark.parametrize(
        'atom, expected',
        [
            (r'', 0),
            (r'a', 0),
            (r'\(', 0),
            (r'(abc)', 1),
            (r'(?:abc)', 1),
            (r'(?>abc)', 1),
            (r'(?P=abc)', 1),
            (r'(?:a|b)', 1),
            (r'[+*?]', 0),
        ],
    )
    def test_is_group(self, atom: Atom, expected: int | bool):
        assert cls._is_atomic(atom) or not atom
        ret = cls._is_group(atom)
        assert ret == bool(expected)

    @pyt.mark.parametrize(
        'atom, expected',
        [
            (r'[cd]', 0),
            (r'[cd]?', 1),
            (r'\?', 0),
        ],
    )
    def test_is_optional(self, atom: Atom, expected: int | bool):
        assert cls._is_atomic(atom) or not atom
        assert cls._is_optional(atom) == bool(expected)

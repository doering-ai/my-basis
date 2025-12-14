############
### HEAD ###
############
### STANDARD

### EXTERNAL
import pytest as pyt

### INTERNAL
from ..conftest import boolmap
from my.regex import Atom, GroupKind

cls = Atom


############
### BODY ###
############
class TestAtom:
    # -------------------
    # `0` Initial Methods
    # -------------------
    @pyt.mark.parametrize(
        'expr, expected',
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
    def test_atomize(self, expr: str, expected: list[str]):
        ret = cls.atomize(expr)
        assert ret == tuple(expected)

    # -------------------
    # `-` Private Methods
    # -------------------

    # -------------------
    # `+` Primary Methods
    # -------------------
    @pyt.mark.parametrize(
        'text, expected',
        [
            ('', ''),
        ],
    )
    def test_as_group(self, text: str, expected: str):
        pass

    @pyt.mark.parametrize(
        'text, expected',
        [
            ('', ''),
        ],
    )
    def test_as_set(self, text: str, expected: str):
        pass

    # ------------------
    # `x` Public Methods
    # ------------------
    # ---------------
    # `x1` Properties
    # ---------------
    @pyt.mark.parametrize(
        'expr, expected',
        boolmap(
            true=[r'a+', r'a*+', r'a*?', r'a{1,}', r'a{0,5}', r'a{0,5}?', r'[abc]+'],
            false=[r'a', r'a?', r'[abc]'],
        ),
    )
    def test_quantifier(self, expr: str, expected: bool):
        atom = cls(expr)
        assert atom.has_complex_quantifier == expected

    @pyt.mark.parametrize(
        'expr, expected',
        boolmap(
            true=[r'(abc)', r'(?:abc)', r'(?>abc)', r'(?P=abc)', r'(?:a|b)'],
            false=[r'', r'a', r'\(', r'[+*?]'],
        ),
    )
    def test_is_group(self, expr: str, expected: bool):
        assert cls(expr).is_group == expected

    @pyt.mark.parametrize(
        'expr, expected',
        boolmap(
            true=[],
            false=[],
        ),
    )
    def test_is_set(self, expr: str, expected: bool):
        assert cls(expr).is_set == expected

    @pyt.mark.parametrize(
        'expr, expected',
        boolmap(
            true=[],
            false=[],
        ),
    )
    def test_is_complex_set(self, expr: str, expected: bool):
        assert cls(expr).is_complex_set == expected

    @pyt.mark.parametrize(
        'expr, expected',
        boolmap(
            true=[],
            false=[],
        ),
    )
    def test_is_complex_group(self, expr: str, expected: bool):
        assert cls(expr).is_complex_group == expected

    @pyt.mark.parametrize(
        'expr, expected',
        boolmap(
            true=[
                r'a',
                r'\+',
                r'a?',
                r'[abc]',
                r'[-az]',
                r'[ab\p{Sc}\P{x}]',
                r'[\[|\]\[[:lower:]\]]',
                r'[+*?]',
                r'[()|]',
                r'[.^$]',
            ],
            false=[
                r'',
                r'(?:abc)',
                r'(?:abc)+',
                r'a+',
                r'a*+',
                r'\++',
                r'\+{1,}',
                r'[a-z]',
                r'[ab--c]',
            ],
        ),
    )
    def test_is_simple(self, expr: str, expected: bool):
        assert cls(expr).is_simple == expected

    @pyt.mark.parametrize(
        'expr, body, quant',
        [
            (r'ab[cd]*?ef', 'cd', '*?'),
            (r'ab\[cd\]ef', '', ''),
            (r'ab[(?:cd)+]ef', '(?:cd)+', ''),
            (r'ab[^[:lower:]A-Z]ef', r'^[:lower:]A-Z', ''),
            (r'ab[\[|\]\[[:lower:]\]]+?cd', r'\[|\]\[[:lower:]\]', '+?'),
        ],
    )
    def test_set_iterator(self, expr: str, body: str, quant: str):
        ret = next(cls.set_iterator(expr), None)  # type: ignore
        if not body:
            assert ret is None
        else:
            assert ret is not None
            assert ret[1:] == (body, quant)

    @pyt.mark.parametrize(
        'expr, kind, name, body, quant',
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
    def test_group_iterator(self, expr: str, kind: GroupKind, name: str, body: str, quant: str):
        ret = next(cls.group_iterator(expr), None)  # type: ignore
        if kind == GroupKind(0):
            assert ret is None
        else:
            assert ret is not None
            assert ret[1:] == (kind, name, body, quant)

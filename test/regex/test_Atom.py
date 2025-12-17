############
### HEAD ###
############
### STANDARD

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.regex import Atom
from ..conftest import boolmap

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
            (r'', []),
            (r'abc', [r'a', r'b', r'c']),
            (r'a|b?|c++', [r'a', r'|', r'b?', r'|', r'c++']),
            (r'\d{4,5}\g<1>', [r'\d{4,5}', r'\g<1>']),
        ],
    )
    def test_plain_atomize(self, expr: str, expected: list[str]):
        ret = list(cls.plain_atomize(expr))
        exp = list(map(Atom, expected))
        assert ret == exp

    # -------------------
    # `-` Private Methods
    # -------------------

    # -------------------
    # `+` Primary Methods
    # -------------------

    # ------------------
    # `x` Public Methods
    # ------------------
    # ---------------
    # `x1` Properties
    # ---------------
    @pyt.mark.parametrize(
        'expr, expected',
        [
            (r'a', r''),
            (r'a+', r'+'),
            (r'(?:a|b|c)*+', r'*+'),
            (r'a*?', r'*?'),
            (r'a{1,}', r'{1,}'),
            (r'a{0,5}', r'{0,5}'),
            (r'a{0,5}?', r'{0,5}?'),
            (r'[abc]++', r'++'),
        ],
    )
    def test_quantifier(self, expr: str, expected: bool):
        assert cls(expr).quantifier == expected

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
            true=[r'[abc]', r'[a-z]', r'[+*?]', r'[()|]', r'[.^$]'],
            false=[r'', r'a', r'\[', r'ab', r'(?:abc)'],
        ),
    )
    def test_is_set(self, expr: str, expected: bool):
        assert cls(expr).is_set == expected

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
                r'a{1,5}',
                r'a{1,}',
                r'[a-z]',
                r'[ab--c]',
            ],
        ),
    )
    def test_is_simple(self, expr: str, expected: bool):
        assert cls(expr).is_simple == expected

    @pyt.mark.parametrize(
        'expr, expected',
        boolmap(
            true=[r'a?', r'a*', r'a{0,5}', r'(?:abc)?', r'[abc]*'],
            false=[r'a', r'a+', r'a{1,5}', r'(?:abc)', r'[abc]+'],
        ),
    )
    def test_is_optional(self, expr: str, expected: bool):
        assert cls(expr).is_optional == expected

    # ------------
    # `x2` Methods
    # ------------
    @pyt.mark.parametrize(
        'expr, quantifier, overwrite, expected',
        [
            (r'a', r'+', True, r'a+'),
            (r'a', r'*', True, r'a*'),
            (r'a', r'?', True, r'a?'),
            (r'a', r'{2,5}', True, r'a{2,5}'),
            (r'a+', r'*', True, r'a*'),
            (r'a+', r'?', True, r'a?'),
            (r'a+', r'+', True, r'a+'),
            (r'a+', r'*', False, r'(?:a+)*'),
            (r'(?:abc)', r'+', True, r'(?:abc)+'),
            (r'(?:abc)+', r'*', True, r'(?:abc)*'),
            (r'(?:abc)+', r'?', False, r'(?:(?:abc)+)?'),
        ],
    )
    def test_quantify(self, expr: str, quantifier: str, overwrite: bool, expected: str):
        assert cls(expr).quantify(quantifier, overwrite) == expected

    @pyt.mark.parametrize(
        'expr, expected',
        [
            (r'a', r'a?'),
            (r'a+', r'a*'),
            (r'a*', r'a*'),
            (r'a{1,5}', r'a{0,5}'),
            (r'(?:abc)', r'(?:abc)?'),
            (r'(?:abc)+', r'(?:abc)*'),
        ],
    )
    def test_as_optional(self, expr: str, expected: str):
        assert cls(expr).as_optional() == expected

    @pyt.mark.parametrize(
        'expr, expected',
        [
            (r'a', r'a'),
            (r'a?', r'a'),
            (r'a+', r'a+'),
            (r'a*', r'a+'),
            (r'a{0,5}', r'a{1,5}'),
            (r'(?:abc)?', r'(?:abc)'),
            (r'(?:abc)*', r'(?:abc)+'),
        ],
    )
    def test_as_required(self, expr: str, expected: str):
        assert cls(expr).as_required() == expected

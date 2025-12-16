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


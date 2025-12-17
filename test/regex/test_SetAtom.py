############
### HEAD ###
############
### STANDARD

### EXTERNAL
import pytest as pyt

### INTERNAL
from ..conftest import boolmap
from my.regex import SetAtom

cls = SetAtom


############
### BODY ###
############
class TestSetAtom:
    # -------------------
    # `0` Initial Methods
    # -------------------
    @pyt.mark.parametrize(
        'expr, body, quant',
        [
            (r'[c|d]*?', r'c\|d', r'*?'),
            (r'[(?:cd)+]', r'\(\?:cd\)\+', r''),
            (r'[^[:lower:]A-Z]', r'^[:lower:]A-Z', r''),
            (r'[\[|\]\[[:lower:]\]]+?', r'\[|\]\[[:lower:]\]', r'+?'),
            (r'[abc]', r'abc', r''),
            (r'[a-z]', r'a-z', r''),
            (r'[+*?]', r'\+\*\?', r''),
            (r'[()|]', r'\(\)\|', r''),
            (r'[.^$]', r'\.\^\$', r''),
        ],
    )
    def test_init(self, expr: str, body: str, quant: str):
        atom = cls(data=expr)
        assert atom.body == body
        assert atom.quantifier == quant

    # ------------------
    # `x` Public Methods
    # ------------------
    @pyt.mark.parametrize(
        'expr, expected',
        boolmap(
            true=[
                r'[abc]',
                r'[a-z]',
                r'[-az]',
                r'[ab\p{Sc}\P{x}]',
                r'[\[|\]\[[:lower:]\]]',
                r'[+*?]',
                r'[()|]',
                r'[.^$]',
                r'[abc]?',
            ],
            false=[
                r'[a-z]',
                r'[ab--c]',
                r'[a&&b]',
                r'[a~~b]',
                r'[a||b]',
                r'[^a-z]',
                r'[abc]+',
                r'[abc]*',
                r'[abc]{2,5}',
            ],
        ),
    )
    def test_is_simple(self, expr: str, expected: bool):
        assert cls(data=expr).is_simple == expected

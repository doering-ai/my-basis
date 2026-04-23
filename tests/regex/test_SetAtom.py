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
    # `.` Initial Methods
    # -------------------
    @pyt.mark.parametrize(
        'expr, body, quant',
        [
            (r'[c|d]*?', r'c\|d', r'*?'),
            (r'[(?:cd)+]', r'\(\?:cd\)\+', r''),
            (r'[^[:lower:]A-Z]', r'\^[:lower:]A-Z', r''),
            (r'[\[|\]\[[:lower:]\]]+?', r'\[\|\]\[[:lower:]\]', r'+?'),
            (r'[abc]', r'abc', r''),
            (r'[a-z]', r'a-z', r''),
            (r'[+*?]', r'\+\*\?', r''),
            (r'[()|]', r'\(\)\|', r''),
            (r'[.^$]', r'\.\^\$', r''),
        ],
    )
    def test_init(self, expr: str, body: str, quant: str):
        atom = cls(data=expr)
        assert ''.join(map(str, atom.members)) == body
        assert atom.quantifier == quant

    # ------------------
    # `*` Public Methods
    # ------------------
    @pyt.mark.parametrize(
        'expr, expected',
        boolmap(
            true=[
                r'[abc]',
                r'[-az]',
                r'[ab\p{Sc}\P{x}]',
                r'[\[|\]\[[:lower:]\]]',
                r'[+*?()|.^$]',
                r'[abc]?',
            ],
            false=[
                r'[a-z]',
                r'[^a]',
                r'[ab--c]',
                r'[a&&b]',
                r'[a~~b]',
                r'[a||b]',
                r'[abc]+',
                r'[abc]*',
                r'[abc]{2,5}',
            ],
        ),
    )
    def test_is_simple(self, expr: str, expected: bool):
        assert cls(data=expr).is_simple == expected

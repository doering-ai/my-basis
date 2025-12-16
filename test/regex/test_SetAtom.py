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
    @pyt.mark.parametrize(
        'expr, body, quant',
        [
            (r'[c|d]*?', r'c|d', r'*?'),
            (r'[(?:cd)+]', r'(?:cd)+', r''),
            (r'[^[:lower:]A-Z]', r'^[:lower:]A-Z', r''),
            (r'[\[|\]\[[:lower:]\]]+?', r'\[|\]\[[:lower:]\]', r'+?'),
        ],
    )
    def test_init(self, expr: str, body: str, quant: str):
        atom = cls(data=expr)
        assert atom.body == body
        assert atom.quantifier == quant

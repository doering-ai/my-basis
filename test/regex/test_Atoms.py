############
### HEAD ###
############
### STANDARD

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.regex import Atom, Atoms

cls = Atoms

############
### BODY ###
############
class TestAtoms:
    @pyt.mark.parametrize(
        'data, expected',
        [
            ('a|b', 1),
            (['a', '|', 'b'], 1),
            ('|', 1),
            (['|'], 1),
            ('abc', 0),
            (['a', 'b', 'c'], 0),
            ('a[bc]d', 0),
        ],
    )
    def test_is_split(self, data: Atom | Atoms, expected: int | bool):
        assert ._is_split(atom) == bool(expected)

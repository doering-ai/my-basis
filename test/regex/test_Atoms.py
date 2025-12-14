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
    # -------------------
    # `0` Initial Methods
    # -------------------
    @pyt.mark.parametrize(
        'args,expected',
        [
            ([''], []),
        ],
    )
    def test_init(self, args: list, expected: list[list[int]]):
        pass

    @pyt.mark.parametrize(
        'text, escape, expected',
        [
            ('', ''),
        ],
    )
    def test_atomize(self, text: str, escape: bool, expected: list[str]):
        pass

    # -------------------
    # `-` Private Methods
    # -------------------

    # -------------------
    # `+` Primary Methods
    # -------------------

    # ------------------
    # `x` Public Methods
    # ------------------
    # --------------
    # `x0` Overrides
    # --------------
    def test_bool(self, expr: str, expected: bool):
        pass

    @pyt.mark.parametrize(
        'text, expected',
        [
            ('', ''),
        ],
    )
    def test_set_item(self, text: str, expected: str):
        pass

    # ------------
    # `x1` Properties
    # ------------
    def test_one(self):
        pass

    # ------------
    # `x2` Methods
    # ------------

    @pyt.mark.parametrize(
        'expr, quantifier, overwrite, expected',
        [
            ('', '', False, ''),
        ],
    )
    def test_quantify(self, expr: str, quantifier: str, overwrite: bool, expected: str):
        pass

    @pyt.mark.parametrize(
        'data, expected',
        [
            ('a|b', True),
            (['a', '|', 'b'], True),
            ('|', True),
            (['|'], True),
            ('abc', False),
            (['a', 'b', 'c'], False),
            ('a[bc]d', False),
        ],
    )
    def test_is_split(self, expr: str | Atoms, expected: bool):
        assert cls.is_split(expr) == bool(expected)

    def test_is_atomic(self, expr: str | Atom | Atoms, expected: bool):
        assert cls.is_atomic(expr) == bool(expected)

    def split(self, expr: Atoms):
        pass

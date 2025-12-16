############
### HEAD ###
############
### STANDARD

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.regex import Quantifier

cls = Quantifier


############
### BODY ###
############
class TestQuantifier:
    @pyt.mark.parametrize(
        'lhs, rhs, expected',
        [
            ('', '', ''),
        ],
    )
    def test_join(self, lhs: str, rhs: str, expected: str | None):
        pass

    @pyt.mark.parametrize(
        'data, expected',
        [
            ('', '', ''),
        ],
    )
    def test_as_optional(self, data: str, expected: str | None):
        pass

    @pyt.mark.parametrize(
        'data, expected',
        [
            ('', '', ''),
        ],
    )
    def test_as_required(self, data: str, expected: str):
        pass

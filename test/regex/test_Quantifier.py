############
### HEAD ###
############
### STANDARD

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.regex import Quantifier
from ..conftest import boolmap

cls = Quantifier


############
### BODY ###
############
class TestQuantifier:
    @pyt.mark.parametrize(
        'lhs, rhs, expected',
        [
            (r'{2,3}', r'{3,4}', None),
            (r'{2,3}', r'?', None),
            (r'{1,3}', r'?', r'{0,3}'),
            (r'+', r'+', r'+'),
        ],
    )
    def test_join(self, lhs: str, rhs: str, expected: str | None):
        ret = cls(lhs).join(rhs)
        if expected is None:
            assert ret is None
        else:
            assert ret == expected

    @pyt.mark.parametrize(
        'data, expected',
        [
            (r'', r'?'),
            (r'?', r'?'),
            (r'*', r'*'),
            (r'+', r'*'),
            (r'{1,}', r'{0,}'),
            (r'{1,5}', r'{0,5}'),
            (r'{2,}', None),
            (r'{2,5}', None),
        ],
    )
    def test_as_optional(self, data: str, expected: str | None):
        ret = cls(data).as_optional()
        if expected is None:
            assert ret is None
        else:
            assert ret == expected

    @pyt.mark.parametrize(
        'data, expected',
        [
            (r'', r''),
            (r'+', r'+'),
            (r'*', r'+'),
            (r'?', r''),
            (r'{0,5}', r'{1,5}'),
            (r'*?', r'+?'),
        ],
    )
    def test_as_required(self, data: str, expected: str):
        assert cls(data).as_required() == expected

    @pyt.mark.parametrize(
        'data, expected',
        boolmap(
            true=[r'', r'?'],
            false=[r'+', r'*', r'{1,}', r'{2,5}', r'*?', r'+?'],
        ),
    )
    def test_is_simple(self, data: str, expected: bool):
        assert cls(data).is_simple == expected

    @pyt.mark.parametrize(
        'data, expected',
        boolmap(
            true=[r'?', r'*', r'*?', r'{0,}', r'{0,5}', r'{0,5}?'],
            false=[r'', r'+', r'+?', r'{1,}', r'{2,5}'],
        ),
    )
    def test_is_optional(self, data: str, expected: bool):
        assert cls(data).is_optional == expected

    @pyt.mark.parametrize(
        'data, expected',
        boolmap(
            true=[r'*', r'?', r'{0,}', r'{4,5}'],
            false=[r'*?', r'{0,}?', r'{2,3}?'],
        ),
    )
    def test_is_greedy(self, data: str, expected: bool):
        assert cls(data).is_greedy == expected

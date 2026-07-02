############
### HEAD ###
############
### STANDARD

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.regex import RgxAtom as Atom
from ..conftest import boolmap

cls = Atom


############
### BODY ###
############
class TestAtom:
    def __repr__(self):
        return 'TestAtom'

    # -------------------
    # `.` Initial Methods
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
    # `*` Public Methods
    # ------------------
    @pyt.mark.parametrize(
        'lesser, greater',
        [
            (r'P', r'p'),
            (r'P', r'p?'),
            (r'p', r'p?'),
            (r'p?', r'q'),
        ],
    )
    def test_lt(self, lesser: str, greater: str):
        assert cls(lesser) < cls(greater)
        assert not cls(lesser) > cls(greater)

    # ---------------
    # `*1` Properties
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
            true=[r'a', r'\+', r'a?'],
            false=[r'', r'a+', r'a*+', r'\++', r'a{1,5}', r'a{1,}'],
        ),
    )
    def test_is_simple(self, expr: str, expected: bool):
        assert cls(expr).is_simple == expected

    @pyt.mark.parametrize(
        'expr, expected',
        boolmap(
            true=[r'a?', r'a*', r'a{0,5}', r'a??', r'a*+', r'a*?'],
            false=[r'a', r'a+', r'a{1,5}', r'a+?', r'a+?'],
        ),
    )
    def test_is_optional(self, expr: str, expected: bool):
        assert cls(expr).is_optional == expected

    # ------------
    # `*2` Methods
    # ------------
    @pyt.mark.parametrize(
        'q0, q1, expected',
        [
            # ---- Simple + Simple ----
            (r'', r'', r''),
            (r'?', r'', r'?'),
            (r'', r'?', r'?'),
            (r'?', r'?', r'?'),
            # ---- Simple + Basic ----
            (r'', r'+', r'+'),
            (r'', r'*', r'*'),
            (r'?', r'+', r'*'),
            (r'?', r'*', r'*'),
            # ---- Simple + Ranged ----
            (r'', r'{0,1}', r'{0,1}'),
            (r'', r'{,1}', r'{,1}'),
            (r'', r'{2,5}', r'{2,5}'),
            (r'', r'{2,}', r'{2,}'),
            (r'?', r'{0,1}', r'{0,1}'),
            (r'?', r'{,1}', r'{,1}'),
            (r'?', r'{2,5}', r'{2,5}'),
            (r'?', r'{1,}', r'*'),
            # ---- Basic + Simple ----
            (r'*', r'', r'*'),
            (r'*', r'?', r'*'),
            (r'+', r'', r'+'),
            (r'+', r'?', r'*'),
            # ---- Basic + Basic ----
            (r'*', r'*', r'*'),
            (r'*', r'+', r'*'),
            (r'+', r'*', r'*'),
            (r'+', r'+', r'+'),
            # ---- Basic + Ranged ----
            (r'*', r'{5,6}', r'*'),
            (r'*', r'{0,6}', r'*'),
            (r'+', r'{5,6}', r'+'),
            (r'+', r'{0,6}', r'*'),
            # ---- Ranged + Simple ----
            (r'{1}', r'', r''),
            (r'{1}+', r'', r'{1}+'),
            (r'{1}', r'?', r'?'),
            (r'{1}+', r'?+', r'?+'),
            (r'{1,}', r'?', r'*'),
            (r'{1,5}', r'?', r'{,5}'),
            (r'{2,5}', r'?', None),
            (r'{11,5}', r'?', None),
            (r'{,5}', r'?', r'{,5}'),
            # ---- Ranged + Basic ----
            (r'{1}?', r'*?', r'*?'),
            (r'{1,}', r'*', r'*'),
            (r'{,1}', r'*', r'*'),
            (r'{1,5}', r'*', r'*'),
            (r'{2,5}', r'*', None),
            (r'{1}+', r'++', r'++'),
            (r'{1,}', r'+', r'+'),
            (r'{,1}', r'+', r'*'),
            (r'{1,5}', r'+', r'+'),
            (r'{2,5}', r'+', r'{2,}'),
            # ---- Ranged + Ranged ----
            (r'{1}+', r'{0,1}', r'?+'),
            (r'{1}+', r'{,1}', r'?+'),
            (r'{1}+', r'{2,5}', r'{2,5}+'),
            (r'{2,5}', r'{2,5}', r'{4,25}'),
            (r'{1,5}', r'{2,5}', r'{2,25}'),
            (r'{1,}', r'{2,10}', r'{2,}'),
            (r'{1,10}', r'{2,}', r'{2,}'),
            # ---- Possessive / Lazy ----
            (r'*+', r'*', r'*+'),
            (r'{1}?', r'+?', r'+?'),
            (r'{1,}+', r'*+', r'*+'),
            (r'??', r'', r'??'),
            (r'?+', r'', r'?+'),
            (r'', r'??', r'??'),
            (r'', r'?+', r'?+'),
            (r'', r'{2,}+', r'{2,}+'),
            (r'?', r'{0,1}?', r'{0,1}?'),
            (r'*?', r'+?', r'*?'),
            (r'*+', r'*+', r'*+'),
            (r'++', r'*+', r'*+'),
            (r'+?', r'+?', r'+?'),
            (r'++', r'+?', None),
        ],
    )
    def test_quantify(self, q0: str, q1: str, expected: str | None):
        old = cls(rf'a{q0}')
        new = old.quantify(q1, overwrite=False)
        if expected is None:
            assert new.quantifier == q1
            assert new.is_group and new.base[:-1].endswith(q0)
        else:
            assert new.quantifier == expected

    def test_quantify__overwrite(self):
        old = cls(r'a{1,5}')
        new = old.quantify(r'?', overwrite=True)
        assert new == r'a?'

    @pyt.mark.parametrize(
        'expr, expected',
        [
            (r'a', r'a?'),
            (r'a+', r'a*'),
            (r'a*', r'a*'),
            (r'a{1,5}', r'a{,5}'),
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
            (r'a?+', r'a{1}+'),
        ],
    )
    def test_as_required(self, expr: str, expected: str):
        assert cls(expr).as_required() == expected

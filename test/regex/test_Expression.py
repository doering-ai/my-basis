############
### HEAD ###
############
### STANDARD

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.regex import Atom, Expression, GroupKind
from ..conftest import boolmap

cls = Expression


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
        'expr, escape, expected',
        [
            # Plain expressions
            (r'abc', [r'a', r'b', r'c']),
            (r'a.b*c++\d{0,}', [r'a', r'.', r'b*', r'c++', r'\d{0,}']),
            # Group Expressions
            (r'(?=abc)', [r'(?=abc)']),
            (r'a(bc)d', [r'a', r'(bc)', r'd']),
            (r'(?=ab)(?<!cd)', [r'(?=ab)', r'(?<!cd)']),
            (r'a(b(c)d)e', [r'a', r'(b(c)d)', r'e']),
            # Set Expressions
            (r'[abc]de[f\d]', [r'[abc]', r'd', r'e', r'[f\d]']),
            (r'[[:alpha:]]+[A[:lower:]Z]', ['[[:alpha:]]+', r'[A[:lower:]Z]']),
            # Combined expressions
            (r'a(b[c|d]e)f', [r'a', r'(b[c|d]e)', r'f']),
            (r'a[bc(d|e)f]g', [r'a', r'[bc(d|e)f]', r'g']),
            # Edge cases
            ('', []),
            ('()', ['()']),
            (r'[()|]', [r'[()|]']),
            (r'|\||', ['|', r'\|', '|']),
        ],
    )
    def test_atomize(self, expr: str, escape: bool, expected: list[str]):
        ret = cls.atomize(expr)
        assert ret == tuple(expected)

    # -------------------
    # `-` Private Methods
    # -------------------

    # -------------------
    # `+` Primary Methods
    # -------------------
    @pyt.mark.parametrize(
        'expr, kind, name, body, quant',
        [
            (r'ab(cd)ef', GroupKind.POSIT, '', 'cd', ''),
            (r'ab(?:cd)+ef', GroupKind.PLAIN, '', 'cd', '+'),
            (r'ab\\(?:cd\\)+ef', GroupKind.PLAIN, '', r'cd\\', '+'),
            (r'ab\(?:cd\)+ef', GroupKind(0), '', '', ''),
            (r'ab[a-b](?:cd)+ef', GroupKind.PLAIN, '', 'cd', '+'),
            (r'ab\[(?:cd)+\]ef', GroupKind.PLAIN, '', 'cd', '+'),
            (r'ab[(?:cd)+]ef', GroupKind(0), '', '', ''),
        ],
    )
    def test_group_iterator(self, expr: str, kind: GroupKind, name: str, body: str, quant: str):
        ret = next(cls.group_iterator(expr), None)  # type: ignore
        if kind == GroupKind(0):
            assert ret is None
        else:
            assert ret is not None
            assert ret[1:] == (kind, name, body, quant)

    # ------------------
    # `x` Public Methods
    # ------------------
    # --------------
    # `x0` Overrides
    # --------------
    def test_bool(self, expr: str, expected: bool):
        pass

    @pyt.mark.parametrize(
        'expr, expected',
        [
            ('', ''),
        ],
    )
    def test_set_item(self, expr: str, expected: str):
        pass

    # ---------------
    # `x1` Properties
    # ---------------
    def test_first(self):
        pass

    def test_last(self):
        pass

    def test_one(self):
        pass

    def test_spans(self):
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
        'expr, expected',
        boolmap(
            true=['a|b', ['a', '|', 'b'], '|', ['|']],
            false=['abc', ['a', 'b', 'c'], 'a[bc]d'],
        ),
    )
    def test_is_split(self, expr: str | Expression, expected: bool):
        assert cls.is_split(expr) == bool(expected)

    @pyt.mark.parametrize(
        'expr, expected',
        boolmap(
            true=[],
            false=[],
        ),
    )
    def test_is_atomic(self, expr: str | Atom | Expression, expected: bool):
        assert cls.is_atomic(expr) == bool(expected)

    def split(self, expr: Expression):
        pass

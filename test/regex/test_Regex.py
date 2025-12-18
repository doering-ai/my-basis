############
### HEAD ###
############
### STANDARD

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.regex import Atom, Regex
from ..conftest import boolmap

cls = Regex


############
### BODY ###
############
class TestRegex:
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
        'expr, expected',
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
            (r'[abc]?', [r'[abc]?']),
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
    def test_atomize(self, expr: str, expected: list[str]):
        ret = list(cls.atomize(expr))
        assert list(map(str, ret)) == expected

    # -------------------
    # `-` Private Methods
    # -------------------

    # -------------------
    # `+` Primary Methods
    # -------------------
    @pyt.mark.parametrize(
        'expr, expected_kind, expected_body, expected_quant',
        [
            (r'ab(cd)ef', 'POSIT', 'cd', ''),
            (r'ab(?:cd)+ef', 'PLAIN', 'cd', '+'),
            (r'ab\\(?:cd\\)+ef', 'PLAIN', r'cd\\', '+'),
            (r'ab[a-b](?:cd)+ef', 'PLAIN', 'cd', '+'),
            (r'ab\[(?:cd)+\]ef', 'PLAIN', 'cd', '+'),
        ],
    )
    def test_group_iterator(
        self, expr: str, expected_kind: str, expected_body: str, expected_quant: str
    ):
        ret = next(cls.group_iterator(expr), None)
        assert ret is not None
        assert ret.kind.name == expected_kind
        assert ret.body == expected_body
        assert ret.quantifier == expected_quant

    # ------------------
    # `x` Public Methods
    # ------------------
    # --------------
    # `x0` Overrides
    # --------------
    @pyt.mark.parametrize(
        'expr, expected',
        boolmap(
            true=[r'a', r'abc', r'(?:test)', r'[abc]'],
            false=[r'', r''],
        ),
    )
    def test_bool(self, expr: str, expected: bool):
        assert bool(cls(expr)) == expected

    @pyt.mark.parametrize(
        'expr, index, value, expected',
        [
            (r'abc', 0, r'x', r'xbc'),
            (r'abc', 1, r'y', r'ayc'),
            (r'abc', 2, r'z', r'abz'),
        ],
    )
    def test_set_item(self, expr: str, index: int, value: str, expected: str):
        atoms = cls(expr)
        atoms[index] = value
        assert str(atoms) == expected

    # ---------------
    # `x1` Properties
    # ---------------
    @pyt.mark.parametrize(
        'expr, expected',
        [
            (r'abc', r'a'),
            (r'(?:test)def', r'(?:test)'),
            (r'[xyz]abc', r'[xyz]'),
            (r'', r''),
        ],
    )
    def test_first(self, expr: str, expected: str):
        assert str(cls(expr).first) == expected

    @pyt.mark.parametrize(
        'expr, expected',
        [
            (r'abc', r'c'),
            (r'def(?:test)', r'(?:test)'),
            (r'abc[xyz]', r'[xyz]'),
            (r'', r''),
        ],
    )
    def test_last(self, expr: str, expected: str):
        assert str(cls(expr).last) == expected

    @pyt.mark.parametrize(
        'expr, expected',
        [
            (r'a', r'a'),
            (r'(?:test)', r'(?:test)'),
            (r'[xyz]', r'[xyz]'),
        ],
    )
    def test_one(self, expr: str, expected: str):
        assert str(cls(expr).one) == expected

    @pyt.mark.parametrize(
        'expr, expected',
        [
            (r'abc', [(0, 1), (1, 2), (2, 3)]),
            (r'a(?:bc)', [(0, 1), (1, 7)]),
            (r'[abc]d', [(0, 5), (5, 6)]),
        ],
    )
    def test_spans(self, expr: str, expected: list[tuple[int, int]]):
        assert cls(expr).spans == expected

    # ------------
    # `x2` Methods
    # ------------
    @pyt.mark.parametrize(
        'expr, quantifier, overwrite, expected',
        [
            (r'a', r'+', False, r'a+'),
            (r'abc', r'*', False, r'(?:abc)*'),
            (r'(?:test)', r'?', False, r'(?:test)?'),
            (r'', r'+', False, r''),
        ],
    )
    def test_quantify(self, expr: str, quantifier: str, overwrite: bool, expected: str):
        assert str(cls.quantify(expr, quantifier, overwrite)) == expected

    @pyt.mark.parametrize(
        'expr, expected',
        boolmap(
            true=[r'a|b', cls('a|b'), '|'],
            false=['abc', cls('abc'), r'a[bc]d'],
        ),
    )
    def test_is_split(self, expr: str | Regex, expected: bool):
        assert cls.is_split(expr) == bool(expected)

    @pyt.mark.parametrize(
        'expr, expected',
        boolmap(
            true=[r'a', r'(?:test)', r'[abc]', r'(?:a|b)'],
            false=[r'abc', r'a|b'],
        ),
    )
    def test_is_atomic(self, expr: str | Atom | Regex, expected: bool):
        assert cls.is_atomic(expr) == bool(expected)

    @pyt.mark.parametrize(
        'expr, expected',
        [
            (r'a|b', [r'a', r'b']),
            (r'a|b|c', [r'a', r'b', r'c']),
            (r'abc|def', [r'abc', r'def']),
            (r'(?:test)|foo', [r'(?:test)', r'foo']),
            # NOOP
            (r'abc', [r'abc']),
            (r'(?:abc|cde)', [r'(?:abc|cde)']),
        ],
    )
    def test_split(self, expr: str, expected: list[str]):
        assert list(map(str, cls(expr).split())) == expected

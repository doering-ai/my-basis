############
### HEAD ###
############
### STANDARD

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.regex import GroupAtom, GroupKind
from ..conftest import boolmap

cls = GroupAtom


############
### BODY ###
############
class TestGroupAtom:
    # -------------------
    # `0` Initial Methods
    # -------------------
    @pyt.mark.parametrize(
        'data, kind, start, body, quant',
        [
            # Basics
            (r'(abc)', GroupKind.POSIT, '(', 'abc', ''),
            (r'(?:def)', GroupKind.PLAIN, '(?:', 'def', ''),
            # Inline flags
            (r'(?im:def)', GroupKind.PLAIN, '(?im:', 'def', ''),
            # Odd types
            (r'(?>xyz)', GroupKind.ATOMS, '(?>', 'xyz', ''),
            (r'(?=test)', GroupKind.AHEAD, '(?=', 'test', ''),
            (r'(?!test)', GroupKind.NOT_AHEAD, '(?!', 'test', ''),
            (r'(?<=test)', GroupKind.BEHIND, '(?<=', 'test', ''),
            (r'(?<!test)', GroupKind.NOT_BEHIND, '(?<!', 'test', ''),
            (r'(?P<name>value)', GroupKind.PARAM, '(?P<', 'value', ''),
            # Quantifiers
            (r'(?:abc)+', GroupKind.PLAIN, '(?:', 'abc', '+'),
            (r'(?:abc)*?', GroupKind.PLAIN, '(?:', 'abc', r'*?'),
            (r'(?:abc){2,5}', GroupKind.PLAIN, '(?:', 'abc', r'{2,5}'),
            (r'(?(DEFINE)(?P<name>value))', GroupKind.PARAM, '(?(DEFINE', '(?P<name>value)', ''),
        ],
    )
    def test_init(self, data: str, kind: GroupKind, start: str, body: str, quant: str):
        atom = cls(data=data)
        assert atom.kind == kind
        assert atom.start == start
        assert atom.body == body
        assert atom.quantifier == quant

    @pyt.mark.parametrize(
        'data, expected_name',
        [
            (r'(?P<foo>bar)', 'foo'),
            (r'(?P<name123>value)', 'name123'),
            (r'(?P<test_name>content)', 'test_name'),
        ],
    )
    def test_named_groups(self, data: str, expected_name: str):
        atom = cls(data=data)
        assert atom.name == expected_name

    @pyt.mark.parametrize(
        'data, expected_flags',
        [
            (r'(?i)', {'i'}),
            (r'(?smi)', {'s', 'm', 'i'}),
            (r'(?-i)', {'-', 'i'}),
            (r'(?i-s)', {'i', '-', 's'}),
            (r'(?i:abc)', {'i'}),
            (r'(?smi:test)', {'s', 'm', 'i'}),
        ],
    )
    def test_flags(self, data: str, expected_flags: set[str]):
        atom = cls(data=data)
        assert atom.flags == expected_flags

    # ------------------
    # `x` Public Methods
    # ------------------
    @pyt.mark.parametrize(
        'data, expected',
        [
            (r'(?:abc)', r'(?:abc)'),
            (r'(?:def)+', r'(?:def)+'),
            (r'(?P<name>value)', r'(?P<name>value)'),
            (r'(?>test)*?', r'(?>test)*?'),
        ],
    )
    def test_str(self, data: str, expected: str):
        assert str(cls(data=data)) == expected

    @pyt.mark.parametrize(
        'data, expected',
        boolmap(
            true=[
                r'(?:a)',
                r'(?:ab)',
                r'(?>test)',
            ],
            false=[
                r'(?:a)+',
                r'(?:ab)*',
                r'(?>test)?',
                r'(?:a|b)',
                r'(capture)',
                r'(?P<name>value)',
            ],
        ),
    )
    def test_is_simple(self, data: str, expected: bool):
        assert cls(data=data).is_simple == expected

    @pyt.mark.parametrize(
        'data, expected',
        [
            (r'(?:abc)', ''),
            (r'(?i:test)', '(?i)'),
            (r'(?smi:value)', '(?ims)'),
            (r'(?s:foo)', '(?s)'),
            (r'(plain)', ''),
        ],
    )
    def test_inline_flags(self, data: str, expected: str):
        assert str(cls(data=data).inline_flags) == expected

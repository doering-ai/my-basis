############
### HEAD ###
############
### STANDARD

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.regex import GroupKind

cls = GroupKind


############
### BODY ###
############
class TestGroupKind:
    @pyt.mark.parametrize(
        'value, expected',
        [
            ('(', cls.POSIT),
            ('(?', cls.FLAGS),
            ('(?:', cls.PLAIN),
            ('(?>', cls.ATOMS),
            ('(?P<', cls.NAMED),
            ('(?&', cls.INVOC),
            ('(?P&', cls.INVOC),
            ('(?P>', cls.INVOC),
            ('(?P=', cls.SUBST),
            ('(?|', cls.RESET),
            ('(?=', cls.AHEAD),
            ('(?!', cls.NOT_AHEAD),
            ('(?<=', cls.BEHIND),
            ('(?<!', cls.NOT_BEHIND),
            ('(?(DEFINE)', cls.DEFINE),
            # Test with full groups
            ('(?:abc)', cls.PLAIN),
            ('(?>foo)', cls.ATOMS),
            ('(?P<name>', cls.NAMED),
            # Invalid/empty
            ('', cls(0)),
        ],
    )
    def test_read(self, value: str, expected: cls):
        assert cls.read(value) == expected

    @pyt.mark.parametrize(
        'kind, expected',
        [
            (cls.POSIT, '('),
            (cls.PLAIN, '(?:'),
            (cls.FLAGS, '(?'),
            (cls.ATOMS, '(?>'),
            (cls.NAMED, '(?P<'),
            (cls.INVOC, '(?P>'),
            (cls.SUBST, '(?P='),
            (cls.RESET, '(?|'),
            (cls.AHEAD, '(?='),
            (cls.NOT_AHEAD, '(?!'),
            (cls.BEHIND, '(?<='),
            (cls.NOT_BEHIND, '(?<!'),
            (cls.DEFINE, '(?(DEFINE)'),
        ],
    )
    def test_prefix(self, kind: cls, expected: str):
        assert kind.prefix == expected

    @pyt.mark.parametrize(
        'kind, mask, expected',
        [
            (cls.NAMED, cls._NAMED, True),
            (cls.INVOC, cls._NAMED, True),
            (cls.PLAIN, cls._NAMED, False),
            (cls.AHEAD, cls._LOOKAHEADS, True),
            (cls.NOT_AHEAD, cls._LOOKAHEADS, True),
            (cls.BEHIND, cls._LOOKAHEADS, False),
            (cls.BEHIND, cls._LOOKBEHINDS, True),
            (cls.NOT_BEHIND, cls._LOOKBEHINDS, True),
            (cls.AHEAD, cls._LOOK, True),
            (cls.BEHIND, cls._LOOK, True),
            (cls.NOT_AHEAD, cls._LOOK, True),
            (cls.NOT_BEHIND, cls._LOOK, True),
            (cls.PLAIN, cls._LOOK, False),
            (cls.PLAIN, cls._SPLITTABLE, True),
            (cls.ATOMS, cls._SPLITTABLE, True),
            (cls.NAMED, cls._SPLITTABLE, False),
            (cls.PLAIN, cls._SIMPLE, True),
            (cls.ATOMS, cls._SIMPLE, True),
            (cls.NAMED, cls._SIMPLE, False),
        ],
    )
    def test_combined_flags(self, kind: cls, mask: cls, expected: bool):
        assert bool(kind in mask) == expected

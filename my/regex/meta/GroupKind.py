############
### HEAD ###
############
### STANDARD
from typing import override
from enum import Flag, auto

### EXTERNAL
import regex as re

### INTERNAL
from ...types import MyEnum
from .meta_rgxs import NO_ESC, FLAGS as _FLAGS


############
### BODY ###
############
class GroupKind(MyEnum, Flag):
    """A flag representing one or more "kinds" of regex groups (capturing, lookahead, etc.).

    The flags with underlines at the start of their names are unions of the main kinds, exported
    for caller convenience when filtering by multiple flag types at once.
    """

    # Basics
    POSIT = auto()  #: Positional capturing group -- `r'(...)'`.
    PLAIN = auto()  #: Positional non-capturing group -- `r'(?:...)'`.
    FLAGS = auto()  #: Custom flag group for setting regex flags -- `r'(?msi)'`
    ATOMS = auto()  #: Atomic group -- `r'(?>...)'`.
    RESET = auto()  #: Branch reset group -- `r'(?|...)'`.

    # Captures
    NAMED = auto()  #: Named capturing group -- `r'(?P<name>...)'`.
    INVOC = auto()  #: Reuse capturing group -- `r'(?P&name)'`/`r'(?P>name)'`.
    SUBST = auto()  #: Backreference to a capturing group -- `r'(?P=name)'`

    # Lookarounds
    AHEAD = auto()  #: Positive lookahead assertion -- `r'(?=...)'`.
    BEHIND = auto()  #: Positive lookbehind assertion -- `r'(?<=...)'`.
    NOT_AHEAD = auto()  #: Negative lookahead assertion -- `r'(?!...)'`.
    NOT_BEHIND = auto()  #: Negative lookbehind assertion -- `r'(?<!...)'`.
    DEFINE = auto()  #: Group for defining subpatterns without capturing -- `r'(?(DEFINE)...)'`.

    # OTHER
    CONDN = auto()  #: Named conditional -- `(?(1)...|...)`.
    CONDL = auto()  #: Lookaround conditional -- `(?(?=...)...|...)`.

    _NAMED = NAMED | INVOC | SUBST  #: Combined flag for all named groups
    _LOOKAHEADS = AHEAD | NOT_AHEAD  #: Union of lookahead groups
    _LOOKBEHINDS = BEHIND | NOT_BEHIND  #: Union of lookbehind groups
    _LOOK = AHEAD | BEHIND | NOT_AHEAD | NOT_BEHIND  #: Union of all lookaround groups.
    _SPLITTABLE = PLAIN | ATOMS | AHEAD | BEHIND | RESET  #: Union of branch-compatible groups.
    _SIMPLE = PLAIN | ATOMS  #: Union of simple non-capturing groups

    @override
    @classmethod
    def read(cls, value: str | int | list | MyEnum) -> 'GroupKind':
        """Parse a value into a GroupKind, additionally recognizing regex group prefixes.

        Beyond the member names, integers, and lists handled by `MyEnum.read`, strings that are
        not member names are interpreted as group prefixes: `'('` alone denotes a positional
        capturing group, while `'(?'`-prefixed strings are matched against the known prefix
        patterns (e.g. `'(?:'` -> PLAIN, `'(?='` -> AHEAD).

        Args:
            value: Member name, group prefix string, integer flag value, list of values, or
                existing enum member. Falsy input yields the empty flag.
        Returns:
            Corresponding GroupKind flag.
        Raises:
            ValueError: If a string is neither a member name nor a recognized group prefix.
        """
        if not value:
            return cls(0)
        elif isinstance(value, MyEnum):
            return cls(value.value)
        elif isinstance(value, str):
            if (_v := value.upper().strip()) in cls.__members__:
                return cls.__members__[_v]
            if not value.startswith('('):
                raise ValueError(f'GroupKind prefix must start with "(", got {value!r}.')
            elif not value.startswith('(?'):
                return GroupKind.POSIT
            elif kind := next((kind for kind, rgx in _PREFIXES if rgx.match(value[2:])), None):
                return kind
            else:
                raise ValueError(f'Unrecognized GroupKind prefix: {value!r}.')

        # Fallback to plain read, though it is likely to fail
        ret = super().read(value)
        assert isinstance(ret, GroupKind), f'GroupKind.read() returned obj of type {type(ret)}.'
        return ret


_PREFIXES: list[tuple[GroupKind, re.Pattern]] = [
    # (GroupKind.POSIT, re.compile(r'$')),
    (GroupKind.FLAGS, re.compile(rf'(?:{_FLAGS}:?)?$')),
    (GroupKind.PLAIN, re.compile(rf'{_FLAGS}?:')),
    (GroupKind.ATOMS, re.compile(r'>')),
    (GroupKind.NAMED, re.compile(r'P<')),
    (GroupKind.INVOC, re.compile(r'P[>&]|&')),
    (GroupKind.SUBST, re.compile(r'P=')),
    (GroupKind.RESET, re.compile(r'\|')),
    (GroupKind.AHEAD, re.compile(r'=')),
    (GroupKind.NOT_AHEAD, re.compile(r'!')),
    (GroupKind.BEHIND, re.compile(r'<=')),
    (GroupKind.NOT_BEHIND, re.compile(r'<!')),
    (GroupKind.DEFINE, re.compile(r'\(DEFINE\)')),
    (GroupKind.CONDN, re.compile(r'\(\\?[-+\w]+\)')),
    (GroupKind.CONDL, re.compile(rf'\(<?[=!][^\n]*?{NO_ESC}\)')),
]

NO_KIND = GroupKind(0)

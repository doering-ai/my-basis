############
### HEAD ###
############
### STANDARD
from typing import override
from enum import Flag, auto

### EXTERNAL

### INTERNAL
from ...types import MyEnum


############
### BODY ###
############
class GroupKind(MyEnum, Flag):
    """A flag representing one or more "kinds" of regex groups (capturing, lookahead, etc.).

    The flags with underlines at the start of their names are unions of the main kinds, exported
    for caller convenience when filtering by multiple flag types at once.
    """

    # Basics
    POSIT = auto()  #: Positional capturing group -- `(...)`.
    PLAIN = auto()  #: Positional non-capturing group -- `(?:...)`.
    FLAGS = auto()  #: Custom flag group for setting regex flags -- `(?msi)`
    ATOMS = auto()  #: Atomic group -- `(?>...)`.
    MULTI = auto()  #: Branch reset group -- `(?|...)`.

    # Captures
    PARAM = auto()  #: Named capturing group -- `(?P<name>...)`.
    INVOC = auto()  #: Reuse capturing group -- `(?&name)`/`(?P&name)`/`(?P>name)`.
    SUBST = auto()  #: Backreference to a capturing group -- `(?P=name)`

    # Lookarounds
    AHEAD = auto()  #: Positive lookahead assertion -- `(?=...)`.
    BEHIND = auto()  #: Positive lookbehind assertion -- `(?<=...)`.
    NOT_AHEAD = auto()  #: Negative lookahead assertion -- `(?!...)`.
    NOT_BEHIND = auto()  #: Negative lookbehind assertion -- `(?<!...)`.
    DEFINE = auto()  #: Group for defining subpatterns without capturing.

    _NAMED = PARAM | INVOC | SUBST  #: Combined flag for all named groups
    _LOOKAHEADS = AHEAD | NOT_AHEAD  #: Union of lookahead groups
    _LOOKBEHINDS = BEHIND | NOT_BEHIND  #: Union of lookbehind groups
    _LOOK = AHEAD | BEHIND | NOT_AHEAD | NOT_BEHIND  #: Union of all lookaround groups.
    _SPLITTABLE = PLAIN | ATOMS | AHEAD | BEHIND | MULTI  #: Union of branch-compatible groups.
    _SIMPLE = PLAIN | ATOMS  #: Union of simple non-capturing groups

    @override
    @classmethod
    def read(cls, value: str | int | list | MyEnum) -> 'GroupKind':
        if isinstance(value, str):
            for kind, prefixes in reversed(_PREFIXES):
                if any(value.startswith(prefix) for prefix in prefixes):
                    return kind
        ret = super().read(value)
        assert isinstance(ret, GroupKind), f'GroupKind.read() returned obj of type {type(ret)}.'
        return ret

    @property
    def prefix(self) -> str:
        """The standard prefix string for this group kind (e.g. `(?=`, `(`, `(?>`, etc)."""
        return next((prefixes[0] for kind, prefixes in _PREFIXES if kind == self), '(')


_PREFIXES: list[tuple[GroupKind, list[str]]] = [
    (GroupKind.POSIT, ['(']),
    (GroupKind.FLAGS, ['(?']),
    (GroupKind.PLAIN, ['(?:']),
    (GroupKind.ATOMS, ['(?>']),
    (GroupKind.PARAM, ['(?P<']),
    (GroupKind.INVOC, ['(?P>', '(?P&', '(?&']),
    (GroupKind.SUBST, ['(?P=']),
    (GroupKind.MULTI, ['(?|']),
    (GroupKind.AHEAD, ['(?=']),
    (GroupKind.NOT_AHEAD, ['(?!']),
    (GroupKind.BEHIND, ['(?<=']),
    (GroupKind.NOT_BEHIND, ['(?<!']),
    (GroupKind.DEFINE, ['(?(DEFINE)']),
]

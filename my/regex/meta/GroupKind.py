############
### HEAD ###
############
### STANDARD
from typing import Self
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

    Attributes:
        POSIT: Positional capturing group -- `(...)`.
        PLAIN: Positional non-capturing group -- `(?:...)`.
        FLAGS: Custom flag group for setting regex flags -- `(?msi)`
        ATOMS: Atomic group -- `(?>...)`.
        MULTI: Branch reset group -- `(?|...)`.
        PARAM: Named capturing group -- `(?P<name>...)`.
        INVOC: Reuse capturing group -- `(?&name)`/`(?P&name)`/`(?P>name)`.
        SUBST: Backreference to a capturing group -- `(?P=name)`
        AHEAD: Positive lookahead assertion -- `(?=...)`.
        BEHIND: Positive lookbehind assertion -- `(?<=...)`.
        NOT_AHEAD: Negative lookahead assertion -- `(?!...)`.
        NOT_BEHIND: Negative lookbehind assertion -- `(?<!...)`.
        DEFINE: Group for defining subpatterns without capturing.
        _NAMED: Combined flag for all named groups (`PARAM | INVOC | SUBST`).
        _LOOKAHEADS: Combined flag for lookahead groups (`AHEAD | NOT_AHEAD`).
        _LOOKBEHINDS: Combined flag for lookbehind groups (`BEHIND | NOT_BEHIND`).
        _LOOK: Combined flag for all lookaround groups.
        _SPLITTABLE: Combined flag for groups that can be split into branches.
        _SIMPLE: Combined flag for simple non-capturing groups (`PLAIN | ATOMS`).
    """

    # Basics
    POSIT = auto()  # positional capturing
    PLAIN = auto()  # Positional non-capturing
    FLAGS = auto()  # Custom sections, usually inline flags
    ATOMS = auto()  # Atomic
    MULTI = auto()  # 'Branch Reset'

    # Captures
    PARAM = auto()  # Definition of a named capturing group
    INVOC = auto()  # Invocation of any capturing group
    SUBST = auto()  # Substitution of the results of a previous capturing group

    # Lookarounds
    AHEAD = auto()  # Lookahead
    BEHIND = auto()  # Lookbehind
    NOT_AHEAD = auto()  # Negative lookahead
    NOT_BEHIND = auto()  # Negative lookbehind
    DEFINE = auto()  # Definition Section

    _NAMED = PARAM | INVOC | SUBST
    _LOOKAHEADS = AHEAD | NOT_AHEAD
    _LOOKBEHINDS = BEHIND | NOT_BEHIND
    _LOOK = AHEAD | BEHIND | NOT_AHEAD | NOT_BEHIND
    _SPLITTABLE = PLAIN | ATOMS | AHEAD | BEHIND | MULTI
    _SIMPLE = PLAIN | ATOMS

    @classmethod
    def read(cls, value: str | int | list | Self) -> Self:  # ty:ignore[invalid-method-override]
        if isinstance(value, str):
            for kind, prefixes in reversed(_PREFIXES):
                if any(value.startswith(prefix) for prefix in prefixes):
                    return kind  # type: ignore[return-value]
            return cls(0)
        return super().read(value)

    @property
    def prefix(self) -> str:
        # return next((pre for pre, kind in PREFIXES.items() if self & kind), '(')
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

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
    """
    Describes a regex group's kind.

    This enumeration classifies different types of regex groups including capturing,
    non-capturing, lookahead, lookbehind, and specialized group types. Uses bitwise
    flags to allow combining multiple group properties.

    Attributes:
        POSIT: Positional capturing group, e.g., (rgx).
        PLAIN: Positional non-capturing group, e.g., (?:rgx).
        FLAGS: Custom flag group for setting regex flags.
        INLINE: Inline flags in plain groups, e.g., (?i:rgx).
        ATOMS: Atomic group, e.g., (?>rgx).
        MULTI: Branch reset group, e.g., (?|rgx).
        PARAM: Named capturing group, e.g., (?P<name>rgx).
        INVOC: Reuse capturing group, e.g., (?P=name) or (?&name).
        AHEAD: Positive lookahead assertion, e.g., (?=rgx).
        BEHIND: Positive lookbehind assertion, e.g., (?<=rgx).
        NOT_AHEAD: Negative lookahead assertion, e.g., (?!rgx).
        NOT_BEHIND: Negative lookbehind assertion, e.g., (?<!rgx).
        _NAMED: Combined flag for all named groups (PARAM | INVOC).
        _LOOKAHEADS: Combined flag for lookahead groups (AHEAD | NOT_AHEAD).
        _LOOKBEHINDS: Combined flag for lookbehind groups (BEHIND | NOT_BEHIND).
        _LOOK: Combined flag for all lookaround groups.
        _SPLITTABLE: Combined flag for groups that can be split into branches.
        _SIMPLE: Combined flag for simple non-capturing groups (PLAIN | ATOMS).
    """

    POSIT = auto()  # positional capturing
    PLAIN = auto()  # Positional non-capturing
    FLAGS = auto()  # Custom sections, usually inline flags
    INLINE = auto()  # Inline flags in plain groups
    ATOMS = auto()  # Atomic
    MULTI = auto()  # 'Branch Reset'
    PARAM = auto()  # Named capturing
    INVOC = auto()  # Reuse capturing
    AHEAD = auto()  # Lookahead
    BEHIND = auto()  # Lookbehind
    NOT_AHEAD = auto()  # Negative lookahead
    NOT_BEHIND = auto()  # Negative lookbehind

    _NAMED = PARAM | INVOC
    _LOOKAHEADS = AHEAD | NOT_AHEAD
    _LOOKBEHINDS = BEHIND | NOT_BEHIND
    _LOOK = AHEAD | BEHIND | NOT_AHEAD | NOT_BEHIND
    _SPLITTABLE = PLAIN | ATOMS | AHEAD | BEHIND | MULTI
    _SIMPLE = PLAIN | ATOMS

    @classmethod
    def read(cls, value: str | int | list | Self) -> Self:  # ty:ignore[invalid-method-override]
        if isinstance(value, str):
            for prefix, kind in reversed(GROUP_KIND_MAP.items()):
                if value.startswith(prefix):
                    return kind
            return cls(0)
        return super().read(value)


GROUP_KIND_MAP = {
    '(': GroupKind.POSIT,
    '(?': GroupKind.FLAGS,
    '(?:': GroupKind.PLAIN,
    '(?>': GroupKind.ATOMS,
    '(?P<': GroupKind.PARAM,
    '(?P=': GroupKind.INVOC,
    '(?&': GroupKind.INVOC,
    '(?|': GroupKind.MULTI,
    '(?=': GroupKind.AHEAD,
    '(?!': GroupKind.NOT_AHEAD,
    '(?<=': GroupKind.BEHIND,
    '(?<!': GroupKind.NOT_BEHIND,
}

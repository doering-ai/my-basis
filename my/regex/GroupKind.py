############
### HEAD ###
############
### STANDARD
from enum import Flag, auto

### EXTERNAL

### INTERNAL


############
### BODY ###
############
class GroupKind(Flag):
    """
    Describes a regex group's kind.

    This enumeration classifies different types of regex groups including capturing,
    non-capturing, lookahead, lookbehind, and specialized group types. Uses bitwise
    flags to allow combining multiple group properties.

    Attributes:
        POSIT: Positional capturing group, e.g., (pattern).
        PLAIN: Positional non-capturing group, e.g., (?:pattern).
        FLAGS: Custom flag group for setting regex flags.
        INLINE: Inline flags in plain groups, e.g., (?i:pattern).
        ATOMS: Atomic group, e.g., (?>pattern).
        MULTI: Branch reset group, e.g., (?|pattern).
        PARAM: Named capturing group, e.g., (?P<name>pattern).
        INVOC: Reuse capturing group, e.g., (?P=name) or (?&name).
        AHEAD: Positive lookahead assertion, e.g., (?=pattern).
        BEHIND: Positive lookbehind assertion, e.g., (?<=pattern).
        NOT_AHEAD: Negative lookahead assertion, e.g., (?!pattern).
        NOT_BEHIND: Negative lookbehind assertion, e.g., (?<!pattern).
        _NAMED: Combined flag for all named groups (PARAM | INVOC).
        _LOOKAHEADS: Combined flag for lookahead groups (AHEAD | NOT_AHEAD).
        _LOOKBEHINDS: Combined flag for lookbehind groups (BEHIND | NOT_BEHIND).
        _LOOK: Combined flag for all lookaround groups.
        _SPLITTABLE: Combined flag for groups that can be split into branches.
        _SIMPLE: Combined flag for simple non-capturing groups (PLAIN | ATOMS).
    """
    POSIT = auto()  # positional capturing
    PLAIN = auto()  # Positional non-capturing
    FLAGS = auto()  # Custom flag
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

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
    """ Describes a regex group's kind. """
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

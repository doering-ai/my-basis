############
### HEAD ###
############
### STANDARD
import functools as ft

### EXTERNAL
import regex as re

### INTERNAL
from ...utils import ut
from ...types import Buffer

############
### DATA ###
############
RegexBuffer = ft.partial(Buffer.new, fence_rgxs=['arrays'])

#: Lookbehind asserting that the preceding character is not an (unescaped) backslash escape.
NO_ESC = r'(?<!^\\|[^\\]\\)'
#: Consuming counterpart of `NO_ESC`: matches a start-of-string, non-backslash, or double-escape.
NON_ESC = r'(?:^|[^\\]|\\\\)'
#: An optional quantifier of any form (`?`, `*+`, `{2,5}?`, ...), matched atomically.
QUANT = r'(?>\?|[*+][?+]?|\{\d+(?:,\d*)?\}[?+]?)?'
#: A named capture of inline-flag syntax (e.g. `smi`, `i-x`), as found inside `(?...)` groups.
FLAGS = r'(?P<flags>-?[afiLmsuxwif]+|[afiLmsuxwif]+-[afiLmsuxwif]+)'

############
### BODY ###
############
#: Dictionary of meta-regex patterns used for parsing and analyzing regular expressions:
#: the primary decomposition patterns (`set`, `group`, `atom`), their second-order helpers
#: (`quant`, `set_operator`, `inline_flags`, ...), and the `struct_mark` pattern behind the
#: `RegexStore` composition DSL. Each value is a compiled pattern, ready to match::
#:
#:     >>> from my import META_RGXS
#:     >>> META_RGXS['quant'].search('ab{2,5}?cd')[0]
#:     '{2,5}?'
META_RGXS: dict[str, re.Pattern] = ut.regex_dict(
    # ---------------
    # Building Blocks
    # ---------------
    NO_ESC=NO_ESC,
    NON_ESC=NON_ESC,
    QUANT=QUANT,
    FLAGS=FLAGS,
    # ---------------------
    # Primary decomposition
    # ---------------------
    set=ut.multi_rgx(r'(?P<start>\[)', rf'(?P<end>\]{QUANT})', pre=NO_ESC),
    group=ut.multi_rgx(
        rf'(?P<start>\((?:\?(?>{FLAGS}?:|[>|]|<?[=!]|P[=<>&]|[&]|\((?>DEFINE|\\?[-+\w]+|<?[=!][^\n]*?{NO_ESC})\))?)?)',
        rf'(?P<end>\){QUANT})',
        pre=NO_ESC,
    ),
    atom=ut.multi_rgx(
        ut.multi_rgx(  # Escaped characters
            r'\d+|g<\d+>',
            r'L<\w+>',
            r'[Pp]\{[[:alpha:]]+\}',
            r'.',
            pre=r'\\',
        ),
        r'(?<!\[)\[(?s:[^\\\[\]]++|\\.|\[.+?\])*\](?!\])',  # Character sets
        r'[^\\]',  # Any other single character
        pre=NO_ESC,
        suf=QUANT,
    ),
    # -------------------------------------------
    # Second-order decomposition (parts of atoms)
    # -------------------------------------------
    quant=ut.multi_rgx(
        r'[?*+]',
        r'\{(?=,?\d)\d*,?\d*\}',
        pre=NO_ESC,
        suf=r'[?+]?',
    ),
    opt_quant=r'^(?:[?*]|{0?)',
    set_operator=rf'^\[?(?:\^|[^\[].*?{NO_ESC}(?>--?|~~|&&|\|\|))',
    inline_flags=rf'{NO_ESC}\(\?{FLAGS}:',
    special_characters=NO_ESC + r'([+*?()|.^$])',
    no_set=rf'(?<!{NON_ESC}\[[^\]]{{0,8}})',
    no_set_suf=rf'(?!\]|[^\[]{{0,8}}{NON_ESC}\])',
    # -----------------
    # DSL specification
    # -----------------
    struct_mark=''.join(
        [
            r'(?P<divis><\|>|\||\[.*?\])?',
            r'(?P<group>[:>&|]|<?[=!]|P<\w+>)?',
            rf'{FLAGS}?(?P<quant>{QUANT})',
        ]
    ),
    # -------------
    # Miscellaneous
    # -------------
    url_detritus=ut.multi_rgx(
        ''.join(
            [
                r'^(?:\S*?archive\S*?\/\d{14}\/)?',
                r'(?:\b(?i:https?:\/\/|www\w*\.){1,2})?'
                r'(?=\S{4,}$)',
            ]
        ),
        r'#[^\/]+$',
        r'[.,\'"\/]+$',
    ),
)

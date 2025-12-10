############
### HEAD ###
############
### STANDARD

### EXTERNAL
import regex as re

### INTERNAL
from ...utils import ut

re.DEFAULT_VERSION = re.VERSION1

############
### DATA ###
############
NO_ESC = r'(?<!^\\|[^\\]\\)'
NON_ESC = r'(?:^|[^\\]|\\\\)'
QUANT = r'(?>[*+]|\{\d+(?:,\d*)?\})?[?+]?'
FLAGS = r'(?P<flags>-?[afiLmsuxwif]+|[afiLmsuxwif]+-[afiLmsuxwif]+)'

META_RGXS: dict[str, re.Pattern] = ut.regex_dict(
    dict(
        # Primary decomposition
        set=ut.multi_rgx(r'(?P<start>\[)', rf'(?P<end>\]{QUANT})', pre=NO_ESC),
        group=ut.multi_rgx(
            rf'(?P<start>\((?:\?(?>[:>&|]|<?[=!]|P[=<]|{FLAGS}:)?)?)',
            rf'(?P<end>\){QUANT})',
            pre=NO_ESC,
        ),
        atom=ut.multi_rgx(
            ut.multi_rgx(
                r'\d+|g<\d+>',
                r'L<\w+>',
                r'[Pp]\{[[:alpha:]]+\}',
                r'.',
                pre=r'\\',
            ),
            r'(?<!\[)\[(?s:[^\\\[\]]+|\\.|\[.+?\])*\](?!\])',
            r'[^\\]',
            pre=NO_ESC,
            suf=QUANT,
        ),
        # Second-order decomposition (parts of atoms)
        quant=ut.multi_rgx(
            r'\?',
            r'[*+][?+]?',
            r'\{\d+(?:,\d*)?\}[?+]?',
            pre=NO_ESC,
            suf=r'$',
        ),
        set_operator=rf'^\[?(?:\^|[^\[].*?{NO_ESC}(?>--?|~~|&&|\|\|))',
        inline_flags=rf'{NO_ESC}\(\?{FLAGS}:',
        special_characters=NO_ESC + r'([+*?()|.^$])',
        no_set=rf'(?<!{NON_ESC}\[[^\]]{{0,8}})',
        no_set_suf=rf'(?!\]|[^\[]{{0,8}}{NON_ESC}\])',
        # DSL specification
        struct_mark=''.join(
            [
                r'(?P<divis><\|>|\||\[.*?\])?',
                r'(?P<group>[:>&|]|<?[=!]|P<\w+>)?',
                rf'{FLAGS}?(?P<quant>{QUANT})',
            ]
        ),
    )
)

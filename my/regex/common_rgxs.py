############
### HEAD ###
############
### STANDARD

### EXTERNAL

### INTERNAL
from .RegexStore import RegexStore
from .meta import META_RGXS


############
### BODY ###
############
#: Store of miscellaneous general patterns, for direct and/or indirect use.
COMMON_RGXS = RegexStore.new(
    options=dict(
        separator='',
        lazy_load=True,
    ),
    # ----------------
    # General patterns
    # ----------------
    _nw=r'[\W_]',
    _delim=r'^|$|[[\W_]--[-.\s]]',
    _ws=r' ?(?<![&[:alnum:]])',
    _we=r'(?![&[:alnum:]])',
    _period=('[]:', [('|<=', [r'[^[:alpha:]]', r'[[:alpha:]]{3}']), r'\.(?P>_we)']),
    _dot=('[]:', [('|<!', [r'[^[:alpha:]]', r'[[:alpha:]]{3}']), r'\.(?P>_we)']),
    # ------------
    # Web patterns
    # ------------
    _http=r'\b(?i:https?:\/\/|www\w*\.){1,2}',
    tld=r'(?<=[[:lower:]])\.[a-z]{2,4}(?![[:lower:]])',
    url=(
        [
            r'(?<!\]\()\b',
            ('|:', [r'(?P>_http)[^\s\[\]]+', r'[^\s\[\]\/]{3,}(?P>tld)\/[^\s\[\]]+']),
        ],
        RegexStore.format_url,
    ),
    #: Recursive helper matching parenthesis-balanced content (e.g. `foo_(bar)_baz`), so `md_url`
    #: below doesn't truncate a link target at its first inner `)` -- see the `(?R)`-recursive
    #: `parens` pattern in `Buffer.RGXS` for the sibling idiom on the simpler `regex_dict` system;
    #: this is the RegexStore-DSL equivalent, invoked as a subroutine via `(?P>_balanced_parens)`.
    _balanced_parens=r'(?:[^()\n]|\((?P>_balanced_parens)\))*+',
    md_url=r'(?<![!\[])\[ *+(?P<alias>[^\]\n]+?) *+\]\((?P<target>(?P>_balanced_parens))\)',
    # Numeric patterns
    _roman_numeral=[
        r'(?i)(?<![[:alnum:]])(?=[IVXLCDM])',
        r'M*',
        ('|:?', [r'CM', r'DC{1,3}', r'C?D', r'C{1,3}']),
        ('|:?', [r'XC', r'LX{1,3}', r'X?L', r'X{1,3}']),
        ('|:?', [r'IX', r'VI{1,3}', r'I?V', r'I{1,3}']),
        r'(?![[:alnum:]])',
    ],
    # -----------------
    # ISO Date Patterns
    # -----------------
    y=r'[01]?\d{3}|20\d\d|\d\d',
    m=r'0?[1-9]|1[0-2]',
    d=r'0[1-9]|[12]?\d|3[0-1]',
    _date=r'\b(?P>y)[-\/.](?P>m)(?:[-\/.](?P>d))?\b',  # Preferred ymd only
    _symbolic_date=(
        '|:',
        [
            r'(?P>y)[-/.](?P>m)(?:[-/.](?P>d))?',
            r'(?:(?P>d)[-/.])?(?P>m)[-/.](?P>y)',
            r'(?P>m)[-/.](?P>d)[-/.](?P>y)',
        ],
    ),
    # --------------------
    # Atomic date patterns
    # --------------------
    day=(
        r'(?i)\b(?P>d)(?:st|nd|rd|th)?\b',
        lambda s: s[:2] if len(s) > 1 and s[1].isdigit() else s[0],
    ),
    month=(
        '|:i',
        r'\b',
        [
            r'jan(?:uary)?',
            r'feb(?:ruary)?',
            r'mar(?:ch)?',
            'apr(?:il)?',
            'may',
            'june?',
            'july?',
            'aug(?:ust)?',
            'sep(?:t(?:em(?:ber)?)?)?',
            'oct(?:ob(?:er)?)?',
            'nov(?:em(?:ber)?)?',
            'dec(?:em(?:ber)?)?',
        ],
        r'\b',
    ),
    season=r'(?i),? ?\b(?:fall|autumn|winter|spring|summer)\b,? ?',
    #: Bounded to `20\d\d` (not a bare `\d{4}`) so the pattern still declines to match obvious
    #: nonsense like `3456` or `9999` -- but open-ended within the 21st century, unlike the old
    #: `20[01]\d|202[0-6]` split, which silently stopped matching any year from 2027 onward.
    year=(
        r'(?<![[:alnum:]])(?:1?\d\d\d|20\d\d|\'\d\d)(?=$|[\W_a-p])',
        lambda s: f'20{s[1:]}' if s.startswith("'") else s,
    ),
    epoch=r',? ?(?:(?:B\.?)?C\.?\.?E|A\.?D\.?)',
    # -----------------------
    # Molecular date patterns
    # -----------------------
    _sep=r' ?[-[:alpha:]]* ?',
    _years=[
        ('|<=', [r'^', r'[ \(]']),
        r'(?P>year)[a-z]?',
        ('|:?', r' ?- ?', [r'(?P>year)', r'\d\d', r'present'], ''),
        r'(?P>epoch)?',
        ('|=', [r'$', r'[\/ .,\)]']),
    ],
    _months=r',? ?(?P>month)(?:(?P>_sep)(?P>month))?,? ?',
    _day_month=r'(?:(?P>day) ?(?P>month)?(?P>_sep))?(?P>day) (?P>month),? ?',
    _month_day=r',? ?(?P>month) (?P>day)(?:(?P>_sep)(?P>day)(?: (?P>month))?)?,? ?',
    _ymd_date=[
        (
            '|:',
            [
                [r'(?P>_years)', ('|&?', ['season', '_month_day', '_months'])],
                ('|&', [r'_month_day', '_months']),
            ],
        ),
        r'(?:\/.+)?',
    ],
    _mdy_date=[
        (
            '|:',
            [
                [('|&?', ['season', '_month_day', '_months']), r'(?P>_years)'],
                ('|&', [r'_month_day', '_months']),
            ],
        ),
        r'(?:\/.+)?',
    ],
    _dmy_date=[
        (
            '|:',
            [
                [('|&?', ['season', '_day_month', '_months']), r'(?P>_years)'],
                ('|&', [r'_day_month', '_months']),
            ],
        ),
        r'(?:\/.+)?',
    ],
    _latent_date=(
        '|:',
        '',
        [
            [r'(?P>_years)', ('|&?', ['season', '_month_day', '_months'])],
            [('|&', ['season', '_day_month', '_month_day', '_months']), r'(?P>_years)?'],
        ],
        r'(?:\/.+)?',
    ),
    # -----------------
    # Detritus patterns
    # -----------------
    #: Re-exported from `META_RGXS` (single source of truth) so downstream consumers can reach
    #: it via the public `COMMON_RGXS` surface, not just the internal meta parser.
    url_detritus=META_RGXS['url_detritus'],
    # --------------
    # Prose patterns
    # --------------
    _preposition=(
        '<|>i',
        r'(?P>_ws)',
        [
            'a',
            'an',
            'as',
            'at',
            'and',
            'also',
            'by',
            'from',
            'for',
            'is',
            'in',
            'into',
            'or',
            'of',
            'on',
            'onto',
            'to',
            'the',
            'than',
            'through',
            'thru',
            'up',
            'upon',
            'unto',
            'until',
            'via',
            'with',
            'within',
            'without',
            '&',
        ],
        r'(?P>_we)',
    ),
)

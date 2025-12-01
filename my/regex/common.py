############
### HEAD ###
############
### STANDARD

### EXTERNAL

### INTERNAL
from .RegexStore import RegexStore, RgxVal


############
### BODY ###
############
def format_url(target: str) -> str:
    return COMMON_RGXS['url_detritus'].sub('', target).strip('/. ')


def atom(*contents: RgxVal) -> RgxVal:
    if not contents:
        raise ValueError('No content provided')
    elif len(contents) > 1:
        return ('[]:', r'(?P=_ws)', list(contents), r'(?P=_we)')

    content = contents[0]

    if isinstance(content, str):
        return rf'(?P=_ws){content}(?P=_we)'
    elif isinstance(content, list):
        return [r'(?P=_ws)', *content, r'(?P=_we)']
    elif isinstance(content, tuple):
        mark, body = '', ''
        prefix, suffix = '', ''
        if len(content) == 2:
            mark, body = content  # type: ignore
            prefix, suffix = '', ''
        elif len(content) == 4:
            mark, prefix, body, suffix = content  # type: ignore
        else:
            raise ValueError(f'Invalid content tuple: {content}')

        if mark[-1] in '*+' or '>' in mark:
            return ('[]:', [r'(?P=_ws)', content, r'(?P=_we)'])  # type: ignore
        else:
            return (mark, rf'(?P=_ws){prefix}', body, rf'{suffix}(?P=_we)')  # type: ignore
    else:
        raise ValueError(f'Invalid content: {content}')


############
### DATA ###
############
COMMON_RGXS = RegexStore.new(
    options=dict(
        separator='',
    ),
    # General patterns
    _nw=r'[\W_]',
    _delim=r'^|$|[[\W_]--[-.\s]]',
    _ws=r' ?(?<![&[:alnum:]])',
    _we=r'(?![&[:alnum:]])',
    _period=('[]:', [('|<=', [r'[^[:alpha:]]', r'[[:alpha:]]{3}']), r'\.(?P=_we)']),
    _dot=('[]:', [('|<!', [r'[^[:alpha:]]', r'[[:alpha:]]{3}']), r'\.(?P=_we)']),
    # Web patterns
    _http=r'\b(?i:https?:\/\/|www\w*\.){1,2}',
    tld=r'(?<=[[:lower:]])\.[a-z]{2,4}(?![[:lower:]])',
    url=(
        [
            r'(?<!\]\()\b',
            ('|:', [r'(?P=_http)[^\s\[\]]+', r'[^\s\[\]\/]{3,}(?P=tld)\/[^\s\[\]]+']),
        ],
        format_url,
    ),
    md_url=r'(?<![!\[])\[ *(?P<alias>[^\]\n]+?) *\]\((?P<target>[^\)\n]+?)\)',
    # Numeric patterns
    _roman_numeral=[
        r'(?i)(?<![[:alnum:]])(?=[IVXLCDM])',
        r'M*',
        ('|:?', [r'CM', r'DC{1,3}', r'C?D', r'C{1,3}']),
        ('|:?', [r'XC', r'LX{1,3}', r'X?L', r'X{1,3}']),
        ('|:?', [r'IX', r'VI{1,3}', r'I?V', r'I{1,3}']),
        r'(?![[:alnum:]])',
    ],
    # Symbolic Date Patterns
    y=r'[01]?\d{3}|20[012]\d|\d\d',
    m=r'[01]?\d',
    d=r'[0123]?\d',
    _date=r'(?P=y)[-\/.](?P=m)(?:[-\/.](?P=d))?',  # Preferred ymd only
    _symbolic_date=(
        '|:',
        [
            r'(?P=y)[-/.](?P=m)(?:[-/.](?P=d))?',
            r'(?:(?P=d)[-/.])?(?P=m)[-/.](?P=y)',
            r'(?P=m)[-/.](?P=d)[-/.](?P=y)',
        ],
    ),
    # Atomic date patterns
    day=(
        r'(?i)\b[0123]?\d(?:st|nd|rd|th)?\b',
        lambda s: s[:2] if len(s) > 1 and s[1].isdigit() else s[0],
    ),
    month=r'(?i)\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b',
    season=r'(?i),? ?\b(?:fall|autumn|winter|spring|summer)\b,? ?',
    year=(
        r'(?<![[:alnum:]])(?:1?\d\d\d|20[01]\d|202[0-6]|\'\d\d)(?=$|[\W_a-p])',
        lambda s: f'20{s[1:]}' if s.startswith("'") else s,
    ),
    epoch=r',? ?(?:(?:B\.?)?C\.?\.?E|A\.?D\.?)',
    # Molecular date patterns
    _sep=r' ?[-[:alpha:]]* ?',
    _years=[
        ('|<=', [r'^', r'[ \(]']),
        r'(?P=year)[a-z]?',
        ('|:?', r' ?- ?', [r'(?P=year)', r'\d\d', r'present'], ''),
        r'(?P=epoch)?',
        ('|=', [r'$', r'[\/ .,\)]']),
    ],
    _months=r',? ?(?P=month)(?:(?P=_sep)(?P=month))?,? ?',
    _day_month=r'(?:(?P=day) ?(?P=month)?(?P=_sep))?(?P=day) (?P=month),? ?',
    _month_day=r',? ?(?P=month) (?P=day)(?:(?P=_sep)(?P=day)(?: (?P=month))?)?,? ?',
    _ymd_date=[
        (
            '|:',
            [
                [r'(?P=_years)', ('|&?', ['season', '_month_day', '_months'])],
                ('|&', [r'_month_day', '_months']),
            ],
        ),
        r'(?:\/.+)?',
    ],
    _mdy_date=[
        (
            '|:',
            [
                [('|&?', ['season', '_month_day', '_months']), r'(?P=_years)'],
                ('|&', [r'_month_day', '_months']),
            ],
        ),
        r'(?:\/.+)?',
    ],
    _dmy_date=[
        (
            '|:',
            [
                [('|&?', ['season', '_day_month', '_months']), r'(?P=_years)'],
                ('|&', [r'_day_month', '_months']),
            ],
        ),
        r'(?:\/.+)?',
    ],
    _latent_date=(
        '|:',
        '',
        [
            [r'(?P=_years)', ('|&?', ['season', '_month_day', '_months'])],
            [('|&', ['season', '_day_month', '_month_day', '_months']), r'(?P=_years)?'],
        ],
        r'(?:\/.+)?',
    ),
    # Detritus patterns
    url_detritus=(
        '|>',
        [
            r'^(?:\S*?archive\S*?\/\d{14}\/)?(?P=_http)?(?=\S{4,}$)',
            r'(?:#[^\/]+|[.,\'"])$',
        ],
    ),
    # Prose patterns
    _preposition=(
        '<|>i',
        r'(?P=_ws)',
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
        r'(?P=_we)',
    ),
)

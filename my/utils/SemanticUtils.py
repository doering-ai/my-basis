############
### HEAD ###
############
### STANDARD
from typing import Callable, Literal, ClassVar
import keyword

### EXTERNAL
import regex as re

### INTERNAL
from .IterUtils import iut


############
### BODY ###
############
class SemanticUtils:
    # ------------------
    # `0` ROMAN NUMERALS
    # ------------------
    ROMAN_ARR: ClassVar = ['M', 'D', 'C', 'L', 'X', 'V', 'I']
    ROMAN_MAP: ClassVar = dict(
        M=1000,
        D=500,
        C=100,
        L=50,
        X=10,
        V=5,
        I=1,
    )

    QUAD_RGX = re.compile(r'C{4}|X{4}|I{4}')
    ROMAN_RGX = re.compile(r'(?i)(?:M{1,4}|CM|C?D|D?C{1,3}|XC|X?L|L?X{1,3}|IX|I?V|V?I{1,3})')

    @classmethod
    def decimal_to_roman(cls, decimal: int) -> str:
        ans = ''
        for char, val in cls.ROMAN_MAP.items():
            while decimal >= val:
                ans += char
                decimal -= val

            if decimal == 0:
                break

        # Fix quads of tens-places (e.g. IIII -> IV, XXXX -> XL, CCCC -> CD)
        for match in reversed(list(cls.QUAD_RGX.finditer(ans))):
            char = match[0][0]
            d_idx = cls.ROMAN_ARR.index(char)
            x0, x1 = match.span()
            half = cls.ROMAN_ARR[d_idx - 1]
            if x0 > 0 and ans[x0 - 1] == half:
                ans = ans[: x0 - 1] + char + cls.ROMAN_ARR[d_idx - 2] + ans[x1:]
            else:
                ans = ans[:x0] + char + half + ans[x1:]

        return ans

    @classmethod
    def roman_to_decimal(cls, roman: str) -> int:
        ans = 0
        last_index = 0
        for match in cls.ROMAN_RGX.finditer(roman):
            if match.start() != last_index:
                return 0
            else:
                last_index = match.end()

            v = [cls.ROMAN_MAP[char] for char in match[0]]
            n_unique = len(set(v))
            if n_unique == 2:
                mod = v[0] * (-1 if v[1] > v[0] else 1)
                main = v[1] * (len(v) - 1)
                ans += main + mod
            elif n_unique == 1:
                ans += v[0] * len(v)
            else:
                return 0
        if last_index != len(roman):
            return 0

        return ans

    # -----------
    # `1` AMOUNTS
    # -----------
    BASELINES: ClassVar = [(10**9, 'B', 'GB'), (10**6, 'M', 'MB'), (10**3, 'K', 'KB'), (1, '', 'B')]

    @classmethod
    def format_amount(cls, amount: int, unit: Literal['num', 'mem'] = 'num', width: int = 0) -> str:
        index = iut.find(cls.BASELINES, lambda trip: amount >= trip[0])
        if index > -1:
            suffix = str(cls.BASELINES[index][1 if unit == 'num' else 2])
            content = round(amount / cls.BASELINES[index][0])
            if width:
                return f'{content:>{width - len(suffix)}.{width - 3}f}{suffix}'
            else:
                return f'{content}{suffix}'
        return f'{amount}'

    # -----------------
    # `2` PLURALIZATION
    # -----------------
    SINGULAR_MAP: ClassVar[list[tuple[str, Callable]]] = [
        # I. Singletons
        (r'^(un|sub|self|meta)$', lambda t: t),
        (r'^(nucleus|knowledge|nexus|network)$', lambda t: t),
        (r'^(stratum|society|identity|geist)$', lambda t: t),
        # II. Irregulars
        (r'^(media|species|evidence|series|equipment)$', lambda t: t),
        (r'^genera$', lambda t: 'genus'),
        (r'^people$', lambda t: 'person'),
        (r'^synopses$', lambda t: 'synopsis'),
        (r'^(bu|ga|bia)sses$', lambda t: t[:-3]),
        # III. Archaics
        (r'(rt|d)ices$', lambda t: t[:-4] + 'ex'),
        (r'(mena|mata)$', lambda t: t[:-1] + 'on'),
        (r'(an?t|[xn]im|cul)a$', lambda t: t[:-1] + 'um'),
        (r'theses$', lambda t: t[:-2] + 'is'),
        # IV. Regulars
        (r'ies$', lambda t: t[:-3] + 'y'),
        (r'(canvas|[^oa]us|ss|x|[rt]ch)es$', lambda t: t[:-2]),
        (r'(lea|li|el)ves$', lambda t: t[:-3] + 'f'),
        # V. Base Case
        (r's$', lambda t: t[:-1]),
    ]

    @classmethod
    def to_singular(cls, plural: str) -> str:
        plural = plural.lower()
        for regex, handler in cls.SINGULAR_MAP:
            if re.search(regex, plural):
                singular = handler(plural)
                assert len(singular) > 0, f'Empty singular form for {plural}'
                return singular

        raise ValueError(f'Failed to convert {plural} to singular form.')

    # ---------------
    # `3` IDENTIFIERS
    # ---------------
    TS_KEYWORDS: ClassVar[list[str]] = [
        'break',
        'case',
        'catch',
        'class',
        'const',
        'continue',
        'debugger',
        'default',
        'delete',
        'do',
        'else',
        'export',
        'extends',
        'false',
        'finally',
        'for',
        'function',
        'if',
        'import',
        'in',
        'instanceof',
        'new',
        'null',
        'return',
        'super',
        'switch',
        'this',
        'throw',
        'true',
        'try',
        'typeof',
        'var',
        'void',
        'while',
        'with',
        'let',
        'static',
        'yield',
        'await',
        'enum',
        'implements',
        'interface',
        'package',
        'private',
        'protected',
        'public',
    ]

    @classmethod
    def validate_identifier(cls, *symbols: str) -> None:
        for sym in symbols:
            assert not keyword.iskeyword(sym), f'Symbol {sym} is invalid (Python keyword)'
            assert sym.isidentifier(), f'Symbol {sym} is invalid (not a valid python identifier)'
            assert sym not in cls.TS_KEYWORDS, f'Symbol {sym} is invalid (TypeScript keyword)'


mut = SemanticUtils

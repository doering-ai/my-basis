############
### HEAD ###
############
### STANDARD
from typing import Literal, ClassVar
from collections.abc import Callable
import keyword
import itertools as it

### EXTERNAL
import regex as re

### INTERNAL (NOTE: If adding new internal imports, update the comments in `__init__.py`)
from .IterUtils import iter_utils
from .TextUtils import text_utils

re.DEFAULT_VERSION = re.VERSION1


############
### BODY ###
############
class SemanticUtils:
    """Methods for semantic-y tasks (i.e. related to data's contant rather than its form)."""

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
        """Convert decimal integer to Roman numeral notation.

        Handles subtractive notation (e.g., IV, IX, XL, XC, CD, CM).

        Args:
            decimal: Integer to convert (typically 1-3999).
        Returns:
            Roman numeral string representation.
        """
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
        """Convert Roman numeral notation to decimal integer.

        Validates format and handles subtractive notation.

        Args:
            roman: Roman numeral string (case-insensitive).
        Returns:
            Decimal integer value, or 0 if invalid format.
        """
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
        """Format large numbers with SI suffixes (K, M, B) or memory units (KB, MB, GB).

        Args:
            amount: Number to format.
            unit: Format type - 'num' for numeric (K/M/B) or 'mem' for memory (KB/MB/GB).
            width: Fixed width for formatting (default: 0 for no fixed width).
        Returns:
            Formatted string with appropriate suffix.
        """
        index = iter_utils.find(cls.BASELINES, lambda trip: amount >= trip[0])
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
    type Singularizer = tuple[re.Pattern, Callable[[str], str]]
    SINGULAR_MAP: ClassVar[list[Singularizer]] = text_utils.regex_array(
        # ======================
        # I. SPECIFIC IRREGULARS
        # ======================
        (r'(?i)^people$', lambda _: 'person'),
        (r'(?i)^media$', lambda _: 'medium'),
        (r'(?i)^genera$', lambda _: 'genus'),
        (r'(?i)^corpora$', lambda _: 'corpus'),
        (r'(?i)^opera$', lambda _: 'opus'),
        (r'(?i)^criteria$', lambda _: 'criterion'),
        # =====================
        # II. NO-CHANGE PLURALS
        # =====================
        (
            r'(?i)^(species|evidence|series|equipment|sheep|deer|fish|moose|salmon|trout|means|aircraft|spacecraft|offspring|crossroads|headquarters)$',
            lambda t: t,
        ),
        # ============================
        # III. VOWEL-CHANGE IRREGULARS
        # ============================
        (r'(?i)^men$', lambda _: 'man'),
        (r'(?i)^women$', lambda _: 'woman'),
        (r'(?i)^teeth$', lambda _: 'tooth'),
        (r'(?i)^feet$', lambda _: 'foot'),
        (r'(?i)^geese$', lambda _: 'goose'),
        (r'(?i)^mice$', lambda _: 'mouse'),
        (r'(?i)^lice$', lambda _: 'louse'),
        #### -EN PLURALS ####
        (r'(?i)^oxen$', lambda _: 'ox'),
        (r'(?i)^children$', lambda _: 'child'),
        (r'(?i)^brethren$', lambda _: 'brother'),
        # ==============
        # V. LATIN/GREEK
        # ==============
        (r'(?i)(cact|fung|foc|nucle|radi|alumn|stimul|syllab|termin)i$', lambda t: t[:-1] + 'us'),
        (r'(?i)(formul|antenn|larv|vertebr|alg|nebul|amoeb)ae$', lambda t: t[:-1]),
        (r'(?i)(append|matr)ices$', lambda t: t[:-4] + 'ix'),
        (r'(?i)(vert|vort|ind|cod|ap)ices$', lambda t: t[:-4] + 'ex'),
        (
            r'(?i)(dat|medi|bacteri|curricul|memorand|strat|addend|spectr|errat|millenni|aquari)a$',
            lambda t: t[:-1] + 'um',
        ),
        (
            r'(?i)(analys|bas|cris|thes|ax|hypothes|synops|oas|parenthes|ellips|diagnos|synthes|neuros)es$',
            lambda t: t[:-2] + 'is',
        ),
        #### IRREGULARS ####
        (r'(?i)^phenomena$', lambda _: 'phenomenon'),
        (r'(?i)^automata$', lambda _: 'automaton'),
        (r'(?i)^polyhedra$', lambda _: 'polyhedron'),
        # ========================
        # X. DOUBLE CONSONANT + ES
        # ========================
        (r'(?i)^quizzes$', lambda _: 'quiz'),  # quiz doubles to quizzes
        (r'(?i)^(bu|ga|bia)sses$', lambda t: t[:-3]),  # busses, gasses, biasses
        (r'(?i)^(gas|bus)es$', lambda t: t[:-2]),  # gases, buses (American spelling)
        # ===========================
        # XI. REGULAR ENGLISH PLURALS
        # ===========================
        # Consonant + y → ies
        (r'(?i)([^aeiou])ies$', lambda t: t[:-3] + 'y'),
        # -f/-fe → -ves (specific words ending in -fe)
        (r'(?i)(kni|wi|li)ves$', lambda t: t[:-3] + 'fe'),
        # -f/-fe → -ves (words ending in -f)
        (r'(?i)(lea|el|wol|cal|hal|shel|thie|loa|scar)ves$', lambda t: t[:-3] + 'f'),
        # -o → -oes
        (r'(?i)([^aeiou])oes$', lambda t: t[:-2]),
        # -es for words ending in s/x/z/ch/sh
        (r'(?i)(ss|x|[sz]h|ch|z)es$', lambda t: t[:-2]),
        # -us/-os exceptions that use -es/-os (not Latin -i)
        (r'(?i)(campus|virus|bonus|chorus|octopus)es$', lambda t: t[:-2]),
        (r'(?i)(photo|piano|memo|solo|studio|radio|zoo)s$', lambda t: t[:-1]),
        # ==============
        # XII. BASE CASE
        # ==============
        (r'(?i)s$', lambda t: t[:-1]),
    )

    @classmethod
    def to_singular(cls, plural: str, overrides: list[Singularizer] | None = None) -> str:
        """Convert plural English word to singular form.

        Handles regular plurals, irregulars, and archaic forms.

        Args:
            plural: Plural word to convert (case-insensitive).
            overrides: Optional list of (regex, handler) pairs to override default rules.
        Returns:
            Singular form of the word.
        Raises:
            ValueError: If no singularization rule matches.
            AssertionError: If result is empty string.
        """
        if overrides is None:
            overrides = []
        for regex, handler in it.chain(overrides, cls.SINGULAR_MAP):
            if regex.search(plural) is not None:
                singular = handler(plural)
                assert len(singular) > 0, f'Empty singular form for {plural}'
                # Preserve case based on input
                if len(plural) > 1:
                    if plural[1].isupper():  # All caps (e.g., "MEN" or "CITIES")
                        singular = singular.upper()
                    elif plural[0].isupper():  # Title case (e.g., "Men" or "Cities")
                        singular = singular[0].upper() + singular[1:]
                return singular

        raise ValueError(f'Failed to convert {plural} to singular form.')

    @staticmethod
    def to_ordinal(num: int | str) -> str:
        """Convert number to ordinal string (e.g., 1 -> '1st', 2 -> '2nd').

        Args:
            num: Integer or string representation of integer.
        Returns:
            Ordinal string with suffix (st/nd/rd/th), or empty string if input is '0' or empty.
        Raises:
            AssertionError: If input is not a valid integer string after stripping zeros.
        """
        num = str(num).lstrip('0')
        if len(num) == 0:
            return ''
        assert num.isdigit(), f'Input {num} is not a valid integer string.'

        if num[-1] > '3':
            ordinal = 'th'
        elif re.search(r'(?<!1)1$', num):
            ordinal = 'st'
        elif re.search(r'(?<!1)2$', num):
            ordinal = 'nd'
        elif re.search(r'(?<!1)3$', num):
            ordinal = 'rd'
        else:
            ordinal = 'th'

        return f'{num}{ordinal}'

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
        """Validate that symbols are valid identifiers in Python and TypeScript.

        Args:
            *symbols: Symbol names to validate.
        Raises:
            AssertionError: If any symbol is a keyword or invalid identifier.
        """
        for sym in symbols:
            assert not keyword.iskeyword(sym), f'Symbol {sym} is invalid (Python keyword)'
            assert sym.isidentifier(), f'Symbol {sym} is invalid (not a valid python identifier)'
            assert sym not in cls.TS_KEYWORDS, f'Symbol {sym} is invalid (TypeScript keyword)'


semantic_utils = SemanticUtils

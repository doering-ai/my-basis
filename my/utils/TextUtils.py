############
### HEAD ###
############
### STANDARD
from typing import Callable, Iterable, Literal, ClassVar
import textwrap
import itertools as it
import functools as ft

### EXTERNAL
import regex as re
from regex import Pattern, Match
from unidecode import unidecode
import pydantic as pyd

### INTERNAL
from ..infra import T
from .IterUtils import iter_utils


############
### BODY ###
############
class TextUtils:
    RGXS: ClassVar[dict[str, Pattern]] = {}

    # ------------------------
    # `0` MANIPULATION & REGEX
    # ------------------------
    @staticmethod
    def replace(string: str, *args: tuple[str | Pattern, str | Callable[[Match[str]], str]]) -> str:
        """
        Apply multiple regex replacements sequentially to a string.

        Args:
            string: Input string to transform.
            *args: Tuples of (pattern, replacement) for sequential application.
        Returns:
            String with all replacements applied in order.
        """
        for pattern, repl in args:
            string = re.sub(pattern, repl, string)
        return string

    @staticmethod
    def split_into(text: str, pattern: str | Pattern, n: int = 2, rhs: bool = True) -> list[str]:
        """
        Split string using regex into exactly n parts, padding as needed.

        Args:
            text: String to split.
            pattern: Regex pattern to split by.
            n: Exact number of parts to return (must be > 1).
            rhs: If True, pad on right; if False, pad on left (default: True).
        Returns:
            List of exactly n strings, padded with empty strings if needed.
        Raises:
            AssertionError: If n <= 1 or split operation fails.
        """
        if not text:
            return [''] * n

        assert n > 1, f'Passed invalid array length `{n}` to split_into(); must be > 1.'
        parts = re.split(pattern, text, n - 1)
        if delta := n - len(parts):
            if rhs:
                parts.extend([''] * delta)
            else:
                parts = ([''] * delta) + parts
        assert len(parts) == n, (
            f'Failed to correctly split {text} by {pattern} into {n}, got {parts}'
        )
        return parts

    @staticmethod
    def regex_dict(
        expressions: dict[T, str | tuple[str, ...] | Pattern] | dict[T, str] | None = None,
        compile_function: Callable[..., Pattern] = re.compile,
    ) -> dict[T, Pattern]:
        """
        Compile string patterns in a expressions to compiled regex Pattern objects.

        Args:
            expressions: A mapping of string names to regular expressions (compiled or otherwise).
            compile_function: Function to compile patterns (default: re.compile).
        Returns:
            The expressions mapping with all values now compiled.
        """
        if expressions is None:
            expressions = {}
        ret = {}
        for key, val in expressions.items():
            if isinstance(val, Pattern):
                ret[key] = val
            else:
                ret[key] = compile_function(val)
        return ret

    @staticmethod
    def regex_array(
        array: Iterable[tuple[str | Pattern, str]],
        compile_function: Callable[..., Pattern] = re.compile,
    ) -> list[tuple[Pattern, str]]:
        """
        Compile raw expressions associated with keys into a list of two-tuples, effectively mapping
        `pattern: name`.

        Args:
            array: Iterable of (pattern, replacement) tuples.
            compile_function: Function to compile patterns (default: re.compile).
        Returns:
            List of (compiled_pattern, replacement) tuples.
        """
        ret = []
        for key, val in array:
            if isinstance(key, Pattern):
                ret.append((key, val))
            else:
                ret.append((compile_function(key), val))
        return ret

    @staticmethod
    def spaced_rgx(expr: str) -> str:
        """
        Convert space-separated expression to flexible whitespace regex.

        Args:
            expr: Space-separated expression.
        Returns:
            Pattern with spaces replaced by \\s* for flexible matching.
        """
        return r'\s*'.join(' '.split(expr))

    @staticmethod
    def multi_rgx(
        *expressions: str | list[str],
        branching: bool = False,
        sep: str = r' ?',
        pre: str = '',
        suf: str = '',
    ) -> str:
        """
        Combine two or more regular expressions into a single "branching" group that matches any of
        the passed expressions.

        Args:
            *expressions: Regex patterns (strings or lists of strings).
            sep: Separator for joining list patterns (default: r' ?').
            pre: Prefix to add before combined pattern (default: '').
            suf: Suffix to add after combined pattern (default: '').
            branching: If True, use branching group (resets group names b/w branches)
        Returns:
            Combined regex pattern in group format (?:|...) or (?:...).
        """
        parts = [(expr if isinstance(expr, str) else sep.join(expr)) for expr in expressions]
        contents = r'|'.join(parts)
        return rf'{pre}(?{"|" if branching else ":"}{contents}){suf}'

    # --------------
    # `1` FORMATTING
    # --------------
    @staticmethod
    def wrap(line: str, prefix: str = '', char: str = '-', width: int = 2) -> str:
        """
        Wrap a line of text with decorative borders.

        Args:
            line: Text to wrap.
            prefix: Prefix for each line (default: '').
            char: Character for border (default: '-').
            width: Padding width on each side (default: 2).
        Returns:
            Multi-line string with text wrapped in decorative borders.
        """
        n = (len(line) + 2 + 2 * width) if width else len(line)
        wrapper = prefix + (char * n)
        return '\n'.join(
            [
                '',
                wrapper,
                prefix + (f'{char * width} {line} {char * width}' if width else line),
                wrapper,
            ]
        )

    @staticmethod
    def indent(text: str, n: int = 4) -> str:
        """
        Indent all lines in text by n spaces.

        Args:
            text: Text to indent.
            n: Number of spaces to indent (default: 4).
        Returns:
            Indented text, or original if n is 0.
        """
        if not n:
            return text
        return textwrap.indent(text, ' ' * n)

    @staticmethod
    def unindent(text: str, n: int = 4) -> str:
        """
        Remove up to n*4 leading spaces from each line.

        Args:
            text: Text to unindent.
            n: Number of indent levels to remove (default: 4, removes up to 16 spaces).
        Returns:
            Unindented text.
        """
        fn = ft.partial(re.compile(rf'^ {{1,{n * 4}}}').sub, '')
        return '\n'.join(map(fn, text))

    @staticmethod
    def strip_quotes(string: str) -> str:
        """
        Remove surrounding quotes and emphasis markers from string.

        Strips matching pairs of ', ", *, and _ characters.

        Args:
            string: String to strip.
        Returns:
            String with surrounding quotes/emphasis removed.
        """
        string = string.strip()
        while len(string) > 2 and (c := string[0]) in '_*\'"':
            if c == string[-2] and not string[-1].isalnum():
                string = string[:-1]

            if c == string[-1]:
                string = string.strip(c).strip()
            else:
                break

        return string

    @classmethod
    def _clean_nonwords(cls, string: str) -> str:
        """
        Clean non-word characters from string using standard replacements.

        Internal method that normalizes newlines, punctuation, spaces, and hyphens.

        Args:
            string: String to clean.
        Returns:
            Cleaned string with normalized spacing and punctuation.
        """
        return cls.replace(
            string,
            (cls.RGXS['newlines'], ' '),
            (cls.RGXS['punctuation'], ''),
            (cls.RGXS['nonwords'], '_'),
            (cls.RGXS['spaces'], '-'),
            (cls.RGXS['multihyphens'], '-'),
        ).strip('_-')

    @classmethod
    def clean_string(cls, string: str, case: Literal['lower', 'none', 'upper'] = 'lower') -> str:
        """
        Fully clean and normalize a string for use as identifier or slug.

        Applies unidecode, strips whitespace, cleans non-words, and applies case conversion.

        Args:
            string: String to clean.
            case: Case conversion - 'lower', 'upper', or 'none' (default: 'lower').
        Returns:
            Cleaned and normalized string suitable for identifiers.
        """
        ret = iter_utils.build(string, unidecode, str.strip, cls._clean_nonwords)
        if case == 'lower':
            return ret.lower()
        elif case == 'upper':
            return ret.upper()
        else:
            return ret

    @classmethod
    def to_words(cls, text: str) -> list[str]:
        """
        Extract all words from text using regex word boundary matching.

        Args:
            text: Text to extract words from.
        Returns:
            List of word strings.
        """
        return list(cls.RGXS['word'].findall(text))

    @staticmethod
    def line_num(article: str, pos: int | str) -> int:
        """
        Calculate line number from character position or substring.

        Args:
            article: Text to search within.
            pos: Character position (int) or substring to find (str).
        Returns:
            Line number (1-indexed).
        """
        if isinstance(pos, int):
            return article.count('\n', 0, pos) + 1
        else:
            return article.count('\n', 0, article.index(pos)) + 1

    @staticmethod
    def parse_domain(url: str, default: str = '') -> str:
        """
        Extract domain name from URL, removing 'www.' prefix.

        Args:
            url: URL string to parse.
            default: Default value if parsing fails (default: '').
        Returns:
            Domain name without 'www.' prefix, or default if parsing fails.
        """
        if url:
            try:
                if host := pyd.HttpUrl(url).host:
                    return host.replace('www.', '')
            except Exception:
                pass
        return default

    @staticmethod
    def wrap_paragraphs(text: str, width: int = 100) -> str:
        """
        Wrap text to specified width, breaking on whitespace.

        Args:
            text: Text to wrap.
            width: Maximum line width (default: 100).
        Returns:
            Wrapped text.
        """
        return textwrap.fill(text, width=width)

    @classmethod
    def unwrap_paragraphs(cls, text: str) -> str:
        """
        Unwrap and normalize paragraph text, joining wrapped lines intelligently.

        Handles hyphenated line breaks, prose detection, and comment prefixes.

        Args:
            text: Text with potentially wrapped paragraphs.
        Returns:
            Unwrapped text with proper spacing and line breaks.
        """
        text = textwrap.dedent(text.strip('\n'))
        text = cls.RGXS['comment_prefix'].sub('', text)
        lines = text.splitlines()
        prose_mask = [bool(cls.RGXS['prose_line'].match(line)) for line in lines]

        acc = lines[0].strip()
        for (prev, prev_is_prose), (cur, cur_is_prose) in it.pairwise(
            zip(lines, prose_mask, strict=True)
        ):
            if not (_stripped := cur.strip()):
                acc += '\n'
            elif prev_is_prose and cur_is_prose:
                if prev.endswith('-') and _stripped[0].isalpha():
                    acc += _stripped
                else:
                    acc += f' {_stripped}'
            elif cur_is_prose:
                acc += f'\n{_stripped}'
            else:
                acc += f'\n{cur}'

        return acc


TextUtils.RGXS = TextUtils.regex_dict(
    dict(
        # General
        comment_prefix=r'(?m)^ ?[*](?: |$)',
        prose_line=r' *[[:punct:]]*([[:alpha:]]|\d+[^\d.])',
        word=r'\w+',
        # Cleaning
        newlines=r'\n+',
        punctuation=r'[\'".]+|(?<=\d),+(?=\d)',
        nonwords=r' *[^-\w\s]+ *',  # All non-whitespace breaks are underlines
        spaces=r' +',  # Spaces are just hyphens
        multihyphens=r'-{2,}',
    )
)

text_utils = TextUtils

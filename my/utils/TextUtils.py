############
### HEAD ###
############
### STANDARD
from typing import Literal, ClassVar, overload
from collections.abc import Callable, Mapping, Hashable
import textwrap
import itertools as it

### EXTERNAL
from regex import Pattern, Match
from unidecode import unidecode
import pydantic as pyd
import regex as re

### INTERNAL
# NOTE: If adding new internal imports, update the comments in `__init__.py`
from ._UtilsBase import _UtilsBase
from .IterUtils import iter_utils


############
### BODY ###
############
class TextUtils(_UtilsBase):
    """Methods that clean, search, split, and otherwise interact with strings.

    Parts of this class overlap in scope with `RegexStore` (namely `regex_dict()`), but ultimately
    present a much more lightweight interface for simple (or dependency-sensitive...) regex tasks.
    As with the store, all regex compiled through these methods supports the regex module's
    [extended regex syntax](./regex.extended_syntax.md).
    """

    RGXS: ClassVar[dict[str, Pattern]] = {}  # written at bottom of file

    # ------------------------
    # `0` MANIPULATION & REGEX
    # ------------------------
    @staticmethod
    def replace(string: str, *args: tuple[str | Pattern, str | Callable[[Match[str]], str]]) -> str:
        """Apply multiple regex replacements sequentially to a string.

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
        """Split string using regex into exactly n parts, padding as needed.

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
    def regex_dict[K: Hashable, V = str](
        expressions: Mapping[K, V | Pattern] | None = None,
        compile_function: Callable[[V], Pattern] = re.compile,  # type: ignore
        **kwargs: V | Pattern,
    ) -> dict[K, Pattern]:
        """Compile the expression strings in the given dictionary, mapping names to Patterns.

        Args:
            expressions: A mapping of string names to regular expressions (compiled or otherwise).
            compile_function: Function to compile patterns (default: re.compile).
            **kwargs: Additional named patterns to include.
        Returns:
            The expressions mapping with all values now compiled.
        """
        ret = {}
        _expr: dict[K, str | V | Pattern] = dict(expressions or {}) | kwargs  # type: ignore
        for key, val in _expr.items():
            if isinstance(val, Pattern):
                ret[key] = val
            else:
                ret[key] = compile_function(val)  # type: ignore
        return ret

    @overload
    @staticmethod
    def regex_array(*args: tuple[str | Pattern, str]) -> list[tuple[Pattern, str]]: ...

    @overload
    @staticmethod
    def regex_array[V = str](
        *args: tuple[str | Pattern, V],
        compile_function: Callable[..., Pattern] = re.compile,
    ) -> list[tuple[Pattern, V]]: ...

    @staticmethod
    def regex_array[V = str](
        *args: tuple[str | Pattern, V],
        compile_function: Callable[..., Pattern] = re.compile,
    ) -> list[tuple[Pattern, V]]:
        """Compile the expressions in a list of two-tuples, effectively mapping Patterns to strings.

        Args:
            array: Iterable of (pattern, replacement) tuples.
            *args: Additional (pattern, replacement) tuples to include.
            compile_function: Function to compile patterns (default: re.compile).
        Returns:
            List of (compiled_pattern, replacement) tuples.
        """
        ret = []
        for key, val in args:
            if not isinstance(key, Pattern):
                key = compile_function(key)
            ret.append((key, val))
        return ret

    @staticmethod
    def multi_rgx(
        *expressions: str | list[str],
        branching: bool = False,
        sep: str = r' ?',
        pre: str = '',
        suf: str = '',
    ) -> str:
        """Combine expression clauses into a single alternating group that matches any of them.

        Args:
            *expressions: Regex patterns to be combined.
            sep: Separator for joining list patterns (default: ` ?`).
            pre: Prefix to add before combined pattern (default: empty).
            suf: Suffix to add after combined pattern (default: empty).
            branching: If True, use branching group (resets group names b/w branches)
        Returns:
            Combined regex pattern in group format ``(?|...)`` or ``(?:...)``.
        """
        parts = [(expr if isinstance(expr, str) else sep.join(expr)) for expr in expressions]
        contents = r'|'.join(parts)
        return rf'{pre}(?{"|" if branching else ":"}{contents}){suf}'

    # --------------
    # `1` FORMATTING
    # --------------
    @staticmethod
    def wrap(line: str, prefix: str = '', char: str = '-', width: int = 2) -> str:
        """Wrap a line of text with decorative borders.

        Args:
            line: Text to wrap.
            prefix: Prefix for each line (default: empty).
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
        """Indent all lines in text by n spaces.

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
        """Remove up to n*4 leading spaces from each line.

        Args:
            text: Text to unindent.
            n: Number of indent levels to remove (default: 4, removes up to 16 spaces).
        Returns:
            Unindented text.
        """
        assert n > 0, 'Number of indent levels to remove must be > 0.'
        return re.compile(rf'(?m)^ {{1,{n * 4}}}').sub('', text)

    @staticmethod
    def strip_quotes(string: str) -> str:
        """Remove surrounding *matched* quotes and emphasis markers (`'"*_`) from the string.

        Args:
            string: The text content to strip.
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
        """Clean non-word characters from string using standard replacements.

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
        """Fully clean and normalize a string for use as identifier or slug.

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
        """Extract all words from text using regex word boundary matching.

        Args:
            text: Text to extract words from.
        Returns:
            List of word strings.
        """
        return list(cls.RGXS['word'].findall(text))

    @staticmethod
    def line_num(article: str, pos: int | str) -> int:
        """Calculate line number from character position or substring.

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
        """Extract domain name from URL, removing 'www.' prefix.

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
        """Wrap text to specified width, breaking on whitespace.

        Args:
            text: Text to wrap.
            width: Maximum line width (default: 100).
        Returns:
            Wrapped text.
        """
        return textwrap.fill(text, width=width)

    @classmethod
    def unwrap_paragraphs(cls, text: str) -> str:
        """Unwrap and normalize paragraph text, joining wrapped lines intelligently.

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


if not TextUtils.RGXS:
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
"""An alias of `TextUtils`, cased so as to imply static usage."""

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
        for pattern, repl in args:
            string = re.sub(pattern, repl, string)
        return string

    @staticmethod
    def split_into(text: str, pattern: str | Pattern, n: int = 2, rhs: bool = True) -> list[str]:
        """
        Splits a string using regex a given number of times AT MINIMUM, padding on the left or right
        for any missing values.

        Args:
            text: The string to split.
            pattern: The regex pattern to split by.
            n: The EXACT number of parts to split into.
            rhs: If True, pad on the right; if False, pad on the left.
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
        dictionary: dict[T, str | tuple[str, ...] | Pattern] | dict[T, str] | None = None,
        compile_function: Callable[..., Pattern] = re.compile,
    ) -> dict[T, Pattern]:
        if dictionary is None:
            dictionary = {}
        ret = {}
        for key, val in dictionary.items():
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
        ret = []
        for key, val in array:
            if isinstance(key, Pattern):
                ret.append((key, val))
            else:
                ret.append((compile_function(key), val))
        return ret

    @staticmethod
    def spaced_rgx(pattern: str) -> str:
        return r'\s*'.join(' '.split(pattern))

    @staticmethod
    def multi_rgx(*rgxs: str | list[str], sep: str = r' ?', branching: bool = False) -> str:
        parts = [(rgx if isinstance(rgx, str) else sep.join(rgx)) for rgx in rgxs]
        contents = r'|'.join(parts)
        return rf'(?{"|" if branching else ":"}{contents})'

    # --------------
    # `1` FORMATTING
    # --------------

    @staticmethod
    def wrap(line: str, prefix: str = '', char: str = '-', width: int = 2) -> str:
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
        if not n:
            return text
        return textwrap.indent(text, ' ' * n)

    @staticmethod
    def unindent(text: str, n: int = 4) -> str:
        """Unindent each line in the given string or iterable of strings by n tabs."""
        fn = ft.partial(re.compile(rf'^ {{1,{n * 4}}}').sub, '')
        return '\n'.join(map(fn, text))

    @staticmethod
    def wrap_paragraphs(text: str, width: int = 100) -> str:
        return textwrap.fill(text, width=width)

    @clasmethod
    def unwrap_paragraphs(cls, text: str) -> str:
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

    @staticmethod
    def strip_quotes(string: str) -> str:
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
        ret = iter_utils.build(string, unidecode, str.strip, cls._clean_nonwords)
        if case == 'lower':
            return ret.lower()
        elif case == 'upper':
            return ret.upper()
        else:
            return ret

    @classmethod
    def to_words(cls, text: str) -> list[str]:
        return list(cls.RGXS['word'].findall(text))

    @staticmethod
    def line_num(article: str, pos: int | str) -> int:
        if isinstance(pos, int):
            return article.count('\n', 0, pos) + 1
        else:
            return article.count('\n', 0, article.index(pos)) + 1

    @staticmethod
    def parse_domain(url: str, default: str = '') -> str:
        if url:
            try:
                if host := pyd.HttpUrl(url).host:
                    return host.replace('www.', '')
            except Exception:
                pass
        return default


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

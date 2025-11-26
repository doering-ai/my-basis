############
### HEAD ###
############
### STANDARD
from typing import Iterator, Literal, ClassVar, Iterable, Callable, Sequence, Annotated
from collections import deque
import itertools as it
import textwrap

### EXTERNAL
import pydantic as pyd
import regex as re
from regex import Match, Pattern
import logfire
import numpy as np
import numpy.typing as npt

### INTERNAL
from ..base import utils as ut
from .Span import Span

############
### DATA ###
############
Pair = tuple[Span, Span]

# Shape: (n, 2) where n is number of spans
SpanArray = npt.NDArray[np.int_]

# Shape: (m, 2, 2) where m is number of pairs
PairArray = npt.NDArray[np.int_]


def no_spans() -> SpanArray:
    """Return an empty array of shape (0, 2)"""
    return np.empty((0, 2), dtype=int)


NO_ESC = r'(?<!(?:^|[^\\])\\)'
DEBUG = False


############
### BODY ###
############
class Buffer(pyd.BaseModel):
    BUFF_LEN: int = 1
    NO_ESC: ClassVar[str] = NO_ESC
    RGXS: ClassVar[dict[str, Pattern]] = ut.regex_dict(
        dict(
            bactic=NO_ESC + rf'(?s:`[^`\n]+{NO_ESC}`|```.+?{NO_ESC}```)',
            nowiki=NO_ESC + r'(?si:<nowiki>.+?<\/nowiki>)',
            parens=NO_ESC + r'\((?s:[^\(\)\\]+|\\.|(?R))*\)',
            blocks=NO_ESC + r'{{(?s:[^{}\\]+|\\.|(?R))*}}',
            arrays=NO_ESC + r'(?<!\[)\[(?s:[^\\\[\]]+|\\.|\[.+?\])*\](?!\])',
        )
    )

    text: list[str] = ['']
    uid: str = ''  # optional

    fences: Annotated[SpanArray, ut.pyd_schemify(np.ndarray)] = pyd.Field(default_factory=no_spans)
    fence_rgxs: list[str] = []
    fence_rgx: ut.Regex | None = pyd.Field(default=None, exclude=True)

    @pyd.model_validator(mode='after')
    def _validate(self) -> 'Buffer':
        assert len(self.text) == self.BUFF_LEN
        if len(self.fence_rgxs) > 0:
            self.fence_rgx = re.compile(
                ut.multi_rgx(
                    *[
                        self.RGXS[rgx].pattern if rgx in self.RGXS else rgx
                        for rgx in self.fence_rgxs
                    ]
                )
            )
            if self.fences.size == 0:
                self.fences = self.build_fences()
        return self

    @pyd.model_serializer
    def serialize(self) -> str:
        return self.text[0]

    @classmethod
    def new(cls, text: 'list[str] | str | Buffer | None' = None, **kwargs) -> 'Buffer':
        if kwargs.pop('no_fence', '') or 'fence_rgxs' not in kwargs:
            kwargs['fence_rgxs'] = []

        if isinstance(text, str):
            text = [text]
        elif isinstance(text, Sequence):
            text = [text[0]]
        elif not text:
            text = ['']
        elif isinstance(text, Buffer):
            text = [text.text[0]]
        return cls(text=text, **kwargs)

    def memcopy(self) -> 'Buffer':
        return Buffer.new(self.text[0], fence_rgxs=self.fence_rgxs, fences=np.copy(self.fences))

    @property
    def lines(self) -> list[str]:
        return self.text[0].splitlines()

    @property
    def has_fences(self) -> bool:
        return self.fences.size > 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Buffer):
            return self.text[0] == other.text[0]
        elif isinstance(other, str):
            return self.text[0] == other
        else:
            return False

    def __hash__(self) -> int:
        return hash(self.text[0])

    def __bool__(self) -> bool:
        return len(self.text[0]) > 0

    def __add__(self, other: 'Buffer | str') -> 'Buffer':
        if isinstance(other, Buffer):
            return Buffer(text=[self.text[0] + other.text[0]])
        elif isinstance(other, str):
            return Buffer(text=[self.text[0] + other])
        else:
            raise TypeError(f'Cannot concatenate Buffer with {type(other)}')

    def __iadd__(self, other: 'Buffer | str') -> 'Buffer':
        if isinstance(other, Buffer):
            self.text[0] += other.text[0]
        elif isinstance(other, str):
            self.text[0] += other
        else:
            raise TypeError(f'Cannot concatenate Buffer with {type(other)}')
        return self

    def set(self, text: str) -> 'Buffer':
        self.text[0] = text
        self.fences = self.build_fences()
        return self

    def insert(self, pos: int, new: str) -> None:
        self._replace_span(Span(pos, pos), new)

    def replace(
        self,
        old: Span | tuple[int, int] | str | Pattern,
        new: str,
        count: int = 0,
        diff: int = 0,
    ) -> 'Buffer':
        if isinstance(old, Pattern):
            self._replace_pattern(old, new, count)
        elif isinstance(old, (tuple, Span)):
            self._replace_span(old, new, diff)
        else:
            self._replace_string(old, new, count, diff)
        return self

    def drop(self, old: str | Span | tuple[int, int]) -> 'Buffer':
        self.replace(old, '')
        return self

    def clear(self) -> 'Buffer':
        self.text[0] = ''
        if self.has_fences:
            self.fences = no_spans()
        return self

    def strip(self, chars: str = '') -> 'Buffer':
        n_left = len(list(it.takewhile(lambda x: x in chars, self.text[0])))
        n_right = len(list(it.takewhile(lambda i: self[i] in chars, range(-1, -len(self), -1))))
        if n_left or n_right:
            end = len(self) - n_right
            self.text[0] = self.text[0][n_left:end]

            if self.has_fences:
                if self.fences[0][0] < n_left or self.fences[-1][1] > end:
                    self.fences = self.build_fences()
                elif n_left:
                    self.fences -= n_left

        return self

    WRITE_MAP: ClassVar[list[tuple[Pattern, str]]] = [
        (re.compile(r'[\s[:punct:]]'), ' '),
        (re.compile(r'\n'), '\n'),
        (re.compile(r'^\n|\n\n|\n$'), '\n\n'),
    ]

    def write(self, span: Span, text: str | Iterable[str], spacing: int = 0, **kwargs) -> None:
        """
        Wraps a given string output in preparation for it to be inserted into the article.
        Offers four distinct spacing modes:
            spacing=0: No spacing
            spacing=1: Ensures space or newline exists before and after
            spacing=2: Ensures newline exists before and after
            spacing=3: Ensures two newlines (i.e. an empty line) exists before and after
        """
        if not text:
            self.drop(span)
            return

        assert 0 <= spacing < len(self.WRITE_MAP), f'Invalid spacing: {spacing}'
        test, char = self.WRITE_MAP[spacing]
        n = len(char)
        x0, x1 = span
        if n == 1:
            pre = char if (x0 > 0 and not test.fullmatch(self[x0 - 1 : x0])) else ''
            post = char if (x1 < len(self) and not test.fullmatch(self[x1 : x1 + 1])) else ''
        elif n > 1:
            pre, post = '', ''
            if x0 > 0:
                _text = self[max(x0 - n, 0) : x0]
                pre = char[len(ut.shared_suffix(char, _text)) :]
            if x1 < len(self):
                _text = self[x1 : min(x1 + n, len(self))]
                post = char[: n - len(ut.shared_prefix(char, _text))]

        newtext = ''.join(
            [
                pre,
                text if isinstance(text, str) else char.join(text),
                post,
            ]
        )
        self._replace_span(span, newtext, **kwargs)

    def _replace_span(self, old: Span | tuple[int, int], new_text: str, diff: int = 0) -> None:
        # Record initial state
        start, end = old
        if end == 0 and not new_text:
            return

        # Perform the replacement
        self.text[0] = self.text[0][:start] + new_text + self.text[0][end:]

        if self.fence_rgx is not None:
            len_old = end - start
            self.update_fences(start, len_old, len(new_text) - len_old, diff)

    def update_fences(self, start: int, len_old: int, delta: int, diff: int = 0) -> None:
        # Refresh fences for this region -- build anew, or just shift future ones
        if self.fence_rgx is None:
            return

        pre, post = self.split_spans(self.fences, Span(start, start + len_old), delta)
        if diff == 0:
            # I. Handle fences in new text, or that appeared b/c of old text
            b0 = pre[-1][1] if pre.size > 0 else 0
            b1 = post[0][0] if post.size > 0 else len(self)
            new = self.build_fences(self[b0:b1], b0)
        else:
            # II. Handle simple translations given by a static diff distance
            pre_rows = pre.shape[0]
            post_rows = self.fences.shape[0] - post.shape[0]
            new = self.fences[pre_rows:post_rows] + diff

        self.fences = np.concatenate((pre, new, post))

    def _replace_string(self, old: str, new: str, count: int = 0, diff: int = 0) -> None:
        i, cur = 0, 0
        while count == 0 or i < count:
            if (start := self.text[0].find(old, cur)) == -1:
                return
            else:
                end = start + len(old)
                self._replace_span(Span(start, end), new)
                cur = len(new) - len(old) + start + 1
                i += 1

    def _replace_pattern(self, rgx: Pattern, new: str, count: int = 0) -> None:
        for i, match in enumerate(self.rgx_iterator(rgx)):
            if count and i >= count:
                break
            self._replace_span(match.span(), rgx.sub(new, match[0]))

    def __str__(self) -> str:
        return self.serialize()

    def __len__(self) -> int:
        return len(self.text[0])

    def __getitem__(self, key: int | slice) -> str:
        return self.text[0][key]

    def slice(self, start: int, end: int) -> str:
        return self.text[0][start:end]

    def __contains__(self, val: str) -> bool:
        return val in self.text[0]

    def is_fenced(self, x: int | Span) -> bool:
        """
        Check if the given span intersects with any of the fenced spans. Uses numpy for speed.
        NOTE: Fences are assumed to always be bigger than spans -- a ref span that *includes* a
        fence will pass successfully.
        """
        if self.fence_rgx is None:
            return False
        elif isinstance(x, int):
            return bool(((self.fences[:, 0] <= x) & (self.fences[:, 1] > x)).any())
        else:
            return any(map(self.is_fenced, (x[0], x[1] - 1)))

    def build_fences(self, text: str | None = None, offset: int = 0) -> SpanArray:
        if self.fence_rgx is None:
            return no_spans()

        if text is None:
            text = self.text[0]
        if len(text) < 3:
            return no_spans()

        spans = np.array([match.span() for match in self.fence_rgx.finditer(text)], dtype=int)
        return (spans + offset) if spans.size > 0 else no_spans()

    @staticmethod
    def split_spans(
        source: SpanArray | list[Span],
        ref_span: Span,
        delta: int,
    ) -> tuple[SpanArray, SpanArray]:
        """
        Split spans into those that come before the reference span and those after, applying a
        shift to the latter array

        Args:
            source: Array of spans with shape (n, 2)
            ref_span: Reference span (start, end)
            delta: Amount to shift spans after the reference

        Returns:
            tuple of (pre_spans, shifted_post_spans)
        """
        if not isinstance(source, np.ndarray):
            source = np.array(source)

        return (
            source[source[:, 1] <= ref_span[0]],
            source[source[:, 0] >= ref_span[1]] + delta,
        )

    @staticmethod
    def shift_spans(spans: SpanArray | list[Span], delta: int, pos: int = 0) -> None:
        """
        Shift spans by a given delta, starting from a given position.

        Args:
            spans: Array of spans with shape (n, 2)
            delta: Amount to shift spans
            pos: Position to start shifting from
        """
        if isinstance(spans, np.ndarray):
            fulls = spans[:, 0] >= pos
            partials = ~fulls & (spans[:, 1] > pos)
            if fulls.any():
                spans[fulls] += delta
            if partials.any():
                spans[partials, 1] += delta
        else:
            for i, (s0, s1) in enumerate(spans):
                if s0 >= pos:
                    spans[i] += delta
                elif s1 > pos:
                    spans[i] = spans[i] + (0, delta)

    def find_chads(self, rgx: Pattern, b0: int = 0, b1: int = -1) -> tuple[list[Span], list[Span]]:
        """
        A subsection of pair_iterator's functionality that searches for one or more "hanging chads",
        representing unmatched delimiters of the given regex pair.
        """
        pos = b0
        b1 = b1 if b1 != -1 else len(self)
        starts: list[Span] = []
        ends: list[Span] = []
        while match := rgx.search(self.text[0][:b1], pos):
            params = match.groupdict()
            span = Span(match.span())
            s0, pos = span

            if self.is_fenced(s0) or params.get('is_complete', None):
                # Skip fenced regions
                continue

            elif params.get('start', ''):
                starts.append(span)
            elif len(starts) == 0:
                ends.append(span)
            else:
                starts.pop()

        return starts, ends

    def raw_pair_iterator(
        self,
        rgx: Pattern,
        mode: Literal['all', 'roots', 'leaves'] = 'all',
        b0: int = 0,
        b1: int = -1,
    ) -> Iterator[Pair]:
        # II. Use a stack of "start" ranges to find matching pairs
        starts: deque[Span] = deque()
        pos = b0
        b1 = b1 if b1 != -1 else len(self)

        while match := rgx.search(self.text[0], pos):
            oldlen = len(self)
            params = match.groupdict()
            span = Span(match.span())
            s0, pos = span

            if pos > b1:
                logfire.debug(f'Hit bound {b1}')
                break

            elif self.is_fenced(s0):
                # Skip fenced regions
                continue

            elif params.get('is_complete', None):
                # Yield self-closing starts without an end attached
                yield span, Span((span[1], span[1]))

            elif params.get('start', ''):
                # A start -- stack and continue
                starts.append(span)
                continue

            elif len(starts) == 0:
                if DEBUG:
                    print(f'ERROR -- unmatched ENDS for\n"""\n{self.text[0]}\n""":')

                assert len(starts) != 0, (
                    f'Encountered unmatched end: "...{self.slice(max(0, s0 - 48), pos)}"'
                )
            else:
                # An end -- pop the most recent start from the stack to match
                start, end = (starts.pop(), span)

                # Only yield if the mode matches our current depth
                if mode == ('roots' if starts else 'leaves'):
                    continue
                yield start, end

            if delta := len(self) - oldlen:
                pos += delta
                b1 += delta

        if len(starts) > 0:
            if DEBUG:
                print(f'ERROR -- unmatched starts for\n"""\n{self.text[0]}\n""":')
                for s0, s1 in starts:
                    print(f'\t@`{s0}`: "{self[s0 : s1 + 48]}..."')
                print('')
                assert len(starts) == 0
            s0, s1 = starts[0]
            assert len(starts) == 0, (
                f'Left {len(starts)} unmatched starts, e.g. "{self[s0 : s1 + 20]}..."'
            )

    def find_pair_match(
        self,
        rgx: Pattern,
        pos: int,
        b0: int = 0,
        b1: int = -1,
    ) -> tuple[Span, str, str, str] | None:
        """
        Find the matching start or end to the given pair member, returning None if nothing is found.
        """
        for span, start, body, end in self.pair_iterator(rgx, 'all', b0, b1):
            if pos in span:
                return span, start, body, end
        return None

    def yield_pair(self, pair: Pair) -> tuple[Span, str, str, str]:
        (s0, s1), (e0, e1) = pair
        return Span((s0, e1)), self[s0:s1], self[s1:e0], self[e0:e1]

    def pair_iterator(
        self,
        rgx: Pattern,
        mode: Literal['all', 'roots', 'leaves'] = 'all',
        b0: int = 0,
        b1: int = -1,
    ) -> Iterator[tuple[Span, str, str, str]]:
        """ """
        yield from map(self.yield_pair, self.raw_pair_iterator(rgx, mode, b0, b1))

    def rgx_iterator(
        self,
        rgx: Pattern | str,
        recursive: bool = False,
        b0: int = 0,
        b1: int = -1,
    ) -> Iterator[Match]:
        if isinstance(rgx, str):
            rgx = self.RGXS.get(rgx, re.compile(rgx))

        pos = b0
        b1 = b1 if b1 != -1 else len(self)
        while match := rgx.search(self.text[0], pos):
            x0, x1 = match.span()
            if x1 > b1:
                logfire.debug(f'Hit bound {b1}')
                break

            # Record initial length
            last_len = len(self)

            # Yield last match, allowing caller to modify it
            yield match

            # Continue on to the next match (if present)
            pos = x0 if recursive else x1
            if delta := len(self) - last_len:
                if not recursive:
                    pos += delta
                b1 += delta

    def match(self, rgx: Pattern, *args, **kwargs) -> Match | None:
        return rgx.match(self.text[0], *args, **kwargs)

    def search(self, rgx: Pattern, *args, **kwargs) -> Match | None:
        return rgx.search(self.text[0], *args, **kwargs)

    def findall(self, rgx: Pattern, *args, **kwargs) -> list[tuple[str, ...]]:
        return rgx.findall(self.text[0], *args, **kwargs)

    def sub(self, rgx: Pattern, new: str, count: int = 0) -> None:
        self.replace(rgx, new, count)

    def apply(self, *functions: Callable[[str], str], b0: int = 0, b1: int = -1) -> 'Buffer':
        """
        Apply a function to the text in the buffer.
        """
        if b1 == -1:
            b1 = len(self)

        for function in functions:
            if b0 == b1:
                return self

            last_len = len(self)
            self.replace((b0, b1), function(self[b0:b1]))
            if delta := len(self) - last_len:
                b1 += delta

        return self

    def linespan(self, pos: int) -> Span:
        """Find the start and end of the line on which pos sits."""
        assert 0 <= pos < len(self), f'Position {pos} is out of bounds'
        text = self.text[0]
        start = text.rfind('\n', 0, pos + 1) + 1
        if start == -1:
            start = 0
        end = text.find('\n', start)
        if end == -1:
            end = len(text)
        return Span(start, end)

    def dedent(self) -> 'Buffer':
        self.text[0] = textwrap.dedent(self.text[0])
        return self

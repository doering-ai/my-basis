############
### HEAD ###
############
### STANDARD
from typing import Literal, ClassVar, Annotated, Self
from collections.abc import Iterator, Iterable, Callable, Sequence
from collections import deque
import itertools as it
import more_itertools as mi
import textwrap

### EXTERNAL
import pydantic as pyd
import regex as re
from regex import Match, Pattern
import numpy as np
import numpy.typing as npt

### INTERNAL
from ..utils import ut
from .Span import Span

############
### DATA ###
############
Pair = tuple[Span, Span]

# Shape: (n, 2) where n is number of spans
SpanArray = npt.NDArray[np.int_]


def _no_spans() -> SpanArray:
    return np.empty((0, 2), dtype=int)


NO_ESC = r'(?<!(?:^|[^\\])\\)'
DEBUG = False

PairMode = Literal['all', 'roots', 'leaves']


############
### BODY ###
############
class Buffer(pyd.BaseModel):
    """A mutable text container optimized for iterative string modification.

    Unlike immutable Python strings, buffers support in-place regex replacement while iterating over
    matches via functions such as `rgx_iterator()`. This enables complex text transformations that
    would otherwise require multiple passes or awkward index tracking.

    Buffers also implement **"fencing"** to exclude certain regions from regex matching. Fences are
    defined by patterns (like code blocks in markdown) and stored as numpy arrays of span pairs for
    efficient lookup. When text is modified, the fence positions intersecting and/or following the
    changed span are efficiently updated, allowing for worry-free use by the caller. The typical
    usecase is for fenced code blocks in markdown or wikitext, which is where they get their name.

    Finally, the class provides **pair-matching functionality** for finding balanced pairs of
    delimiters as simple as parens or as complex as HTML tags, handling nesting and self-closing
    delimiters along the way.

    Some functionality is also included for identifying "[hanging] chads", which refer to unmatched
    pair delimiters that are assumed to represent syntax errors in the original content.
    """

    BUFF_LEN: ClassVar[int] = 1
    NO_ESC: ClassVar[str] = NO_ESC
    RGXS: ClassVar[dict[str, Pattern]] = ut.regex_dict(
        dict(
            bactic=NO_ESC + rf'(?s:`[^`\n]+{NO_ESC}`|```.+?{NO_ESC}```)',
            parens=NO_ESC + r'\((?s:[^\(\)\\]+|\\.|(?R))*\)',
            arrays=NO_ESC + r'(?<!\[)\[(?s:[^\\\[\]]+|\\.|\[.+?\])*\](?!\])',
            braces=NO_ESC + r'{(?s:[^{}\\]+|\\.|(?R))*}',
            blocks=NO_ESC + r'{{(?s:[^{}\\]+|\\.|(?R))*}}',
            nowiki=NO_ESC + r'(?si:<nowiki>.+?<\/nowiki>)',
        )
    )
    WRITE_MAP: ClassVar[list[tuple[Pattern, str]]] = ut.regex_array(
        [
            (r'[\s[:punct:]]', ' '),
            (r'\n', '\n'),
            (r'^\n|\n\n|\n$', '\n\n'),
        ]
    )

    #: The primary content of each instance. Should always be read via `__str__` for clarity,
    #: and modified exclusively via the API (`replace()`, `insert()`, `drop()`, etc.).
    text: list[str] = ['']

    #: Optional identifier for use by the caller.
    uid: str = ''

    #: Spans within the text that are skipped during iteration.
    #: Can be useful to access, but direct modification during iteration is heavily discouraged.
    fences: Annotated[SpanArray, ut.pyd_schemify(np.ndarray)] = pyd.Field(default_factory=_no_spans)

    #: The regex patterns used to define fences in this buffer.
    #: Also accepts the names of some default patterns -- see `new()` for details.
    fence_rgxs: list[str] = []

    fence_rgx: ut.RegexField | None = pyd.Field(default=None, exclude=True)

    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyd.model_validator(mode='after')
    def _setup_fencing(self) -> Self:
        """Compiles a fence regex (if necessary) and builds the initial fences."""
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
                self.fences = self._build_fences()
        return self

    @pyd.model_serializer
    def serialize(self) -> str:
        """Serialize the Buffer instance to a string."""
        return self.text[0]

    @classmethod
    def new(
        cls,
        text: list[str] | str | Self | None = None,
        uid: str = '',
        fence_rgxs: list[str] | None = None,
        no_fence: bool = False,
    ) -> Self:
        """The primary interface for creating new Buffers, providing flexible argument conversion.

        The `fence_rgx` parameter allows the caller to control exactly what content-if any-will be
        ignored while iterating through this buffer. For ease of use, 6 prewritten patterns can be
        identified by name:

        1. bactic: `` `...` ``
        2. parens: `(...)`
        3. arrays: `[...]`
        4. braces: `{...}`
        5. blocks: `{{...}}`
        6. nowiki: `<nowiki>...</nowiki>`

        If you're creating lots of Buffers with the same `fence_rgx`s, it may make sense to define a
        partial constructor, e.g.: `functools.partial(Buffer.new, fence_rgxs=['arrays'])`.

        Args:
            text: The string to coerce into the new buffer's initial value.
            uid: An optional identifier for the new buffer.
            fence_rgxs: A list of regex patterns (or names of default patterns) to use as fences.
            no_fence: If set to True, disables fence calculation even if `fence_rgx` is given.
        Returns:
            A new Buffer instance (with fences calculated if possible).
        """
        if no_fence or fence_rgxs is None:
            fence_rgxs = []

        if isinstance(text, str):
            text = [text]
        elif isinstance(text, Sequence):
            text = [text[0]]
        elif not text:
            text = ['']
        elif isinstance(text, Buffer):
            text = [text.text[0]]
        return cls(text=text, uid=uid, fence_rgxs=fence_rgxs)

    def memcopy(self) -> Self:
        """Create a deep copy of this Buffer instance without recalculating fences."""
        return self.__class__(
            text=[self.text[0]],
            fence_rgxs=self.fence_rgxs,
            fences=np.copy(self.fences),
            uid=self.uid,
        )

    # -------------------
    # `-` Private Methods
    # -------------------
    def _replace_span(self, old: Span | tuple[int, int], new_text: str, diff: int = 0) -> None:
        """Replace a span of text with new text, updating fences as necessary.

        Args:
            old: The span (start, end) to replace.
            new_text: The new text to insert.
            diff: When set, indicates that any fences found within the old text are still there, but
                have simply moved by this static amount.
        """
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
        """(Re-)calculates the fence spans for the given region.

        Handles both fences that are completely internal to the region, and fences that cross one of
        the boundaries. Sometimes, new cross-boundary fences can form where none existed before.

        No changes are needed for fences that contain the region entirely; the normal index shifting
        after a replacement handles that case on its own.

        Args:
            start: The start position of the replaced region.
            len_old: The length of the old text that was replaced.
            delta: The change in length (new length - old length).
            diff: When set, indicates that any fences found within the old text are still there, but
                have simply moved by this static amount.
        """
        if self.fence_rgx is None:
            return

        pre, post = self._split_spans(self.fences, Span(start, start + len_old), delta)
        n, n_pre, n_post = self.fences.shape[0], pre.shape[0], post.shape[0]
        if diff == 0:
            # I. Handle fences in new text, or that appeared b/c of old text
            b0 = pre[-1][1] if n_pre else 0
            b1 = post[0][0] if n_post else len(self)
            new = self._build_fences(self[b0:b1], b0)
        else:
            # II. Simply shift any existing fences in this region by the given static `diff`
            new = self.fences[n_pre : n - n_post] + diff

        self.fences = np.concatenate((pre, new, post))

    def _replace_string(self, old: str, new: str, count: int = 0, diff: int = 0) -> None:
        """Replace one or more occurrences of a substring with new text, updating fences.

        Args:
            old: The substring to replace.
            new: The new text to insert.
            count: The maximum number of replacements to make (0 for all).
            diff: When set, indicates that any fences found within the old text are still there, but
                have simply moved by this static amount.
        """
        assert count >= 0, 'Count must be non-negative'
        i, cur = 0, 0
        while count == 0 or i < count:
            if (start := self.text[0].find(old, cur)) == -1:
                return
            else:
                end = start + len(old)
                self._replace_span(Span(start, end), new)
                cur = len(new) - len(old) + start + 1
                i += 1

    def _replace_regex(self, rgx: Pattern, new: str, count: int = 0) -> None:
        """Replaces occurrences of a regex pattern with new text, updating fences.

        Regex variable substitution is performed as usual for each match.

        Args:
            rgx: The regex pattern to replace.
            new: The new text to insert.
            count: The maximum number of replacements to make (0 for all).
        """
        for i, match in enumerate(self.rgx_iterator(rgx)):
            if count and i >= count:
                break
            self._replace_span(match.span(), rgx.sub(new, match[0]))

    def _yield_pair(self, pair: Pair) -> tuple[Span, str, str, str]:
        """Helper function that formats the given pair of spans into a helpful 4-tuple.

        Args:
            pair: A tuple of spans representing the start and end delimiters.
        Returns:
            1. The full span from the start of the first delimiter to the end of the second.
            2. The text of the start delimiter.
            3. The text between the delimiters.
            4. The text of the end delimiter.
        """
        (s0, s1), (e0, e1) = pair
        return Span((s0, e1)), self[s0:s1], self[s1:e0], self[e0:e1]

    def _is_fenced(self, x: int | Span) -> bool:
        """Efficiently check if the given span intersects with any of the fenced spans.

        NOTE: Fences are assumed to always be bigger than spans -- a ref span that *includes* one or
        more fence delimeters will pass successfully. This should never come up for sane usecases.

        Args:
            x: The position or span to check.
        Returns:
            True if the position/span is within any fence, else False.
        """
        if self.fence_rgx is None:
            return False
        elif isinstance(x, int):
            return bool(((self.fences[:, 0] <= x) & (self.fences[:, 1] > x)).any())
        else:
            return any(map(self._is_fenced, (x[0], x[1] - 1)))

    def _build_fences(self, text: str | None = None, offset: int = 0) -> SpanArray:
        """Build the fence spans for the given text, or the buffer's text if none is given.

        Args:
            text: The text to search for fences. If None, uses the buffer's text.
            offset: An offset to add to all found spans.
        Returns:
            An array of fence spans with shape (n, 2).
        """
        if self.fence_rgx is None:
            return _no_spans()

        if text is None:
            text = self.text[0]
        if len(text) < 3:
            return _no_spans()

        spans = np.array([match.span() for match in self.fence_rgx.finditer(text)], dtype=int)
        return (spans + offset) if spans.size > 0 else _no_spans()

    @staticmethod
    def _split_spans(
        source: SpanArray | list[Span],
        ref_span: Span,
        delta: int,
    ) -> tuple[SpanArray, SpanArray]:
        """Updates a list of spans in reaction to a change in another span's length.

        Split spans into those that come before the "reference" span and those after, so that a
        positional shift can be applied to the indicies in the latter array.

        Args:
            source: Array of spans with shape `(n, 2)`.
            ref_span: The span of text that changed in length.
            delta: The amount the identified text changed in length.
        Returns:
            Tuple of numpy arrays of the form `(pre_spans, post_spans)`
        """
        if not isinstance(source, np.ndarray):
            source = np.array(source)
        assert not isinstance(source, list)

        return (
            source[source[:, 1] <= ref_span[0]],
            source[source[:, 0] >= ref_span[1]] + delta,
        )

    @staticmethod
    def _shift_spans(spans: SpanArray | list[Span], delta: int, pos: int = 0) -> None:
        """Shift spans by a given delta, starting from a given position.

        Args:
            spans: Array of spans with shape (n, 2)
            delta: Amount to shift spans
            pos: Position to start shifting from
        """
        if isinstance(spans, np.ndarray):
            assert not isinstance(spans, list)
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

    # -------------------
    # `+` Primary Methods
    # -------------------
    def raw_pair_iterator(
        self,
        rgx: Pattern,
        mode: PairMode = 'all',
        b0: int = 0,
        b1: int = -1,
    ) -> Iterator[Pair]:
        """Finds all the "pairs" of text delimiters with the given fruit, handling edge cases.

        See `pair_iterator()` for full usage details.

        Args:
            rgx: The regex pattern defining the pair delimiters.
            mode: `'all'` by default, `'roots'` to exclude nested pairs, or `'leaves'` for the
                opposite.
            b0: The positive, inclusive start bound for searching.
            b1: The positive, exclusive end bound for searching, or -1 to search the whole text.
        Yields:
            Tuples of spans representing the start and end delimiters.
        """
        pos = b0
        b1 = b1 if b1 != -1 else len(self)
        starts: deque[Span] = deque()

        # Iterate using the regex library's native positional search(), adjusting for modifications
        while match := rgx.search(self.text[0], pos):
            oldlen = len(self)
            params = match.groupdict()
            span = Span(match.span())
            s0, pos = span

            if pos > b1:
                # I.i. Exit when we hit the end bound
                break

            elif self._is_fenced(s0):
                # I.ii. Ignore any matches within "fenced" regions
                continue

            elif params.get('is_complete', None):
                # II.i. Yield self-closing starts (e.g. '<span />')
                yield span, Span((span[1], span[1]))

            elif params.get('start', ''):
                # II.ii. We've found the start of a new pair; record it and continue
                starts.append(span)
                continue

            elif len(starts) == 0:
                # III.i. We've found an end, but don't have any recorded starts to match it to
                if DEBUG:
                    print(f'ERROR -- unmatched ENDS for\n"""\n{self.text[0]}\n""":')

                assert len(starts) != 0, (
                    f'Encountered unmatched end: "...{self.slice(max(0, s0 - 48), pos)}"'
                )
            else:
                # III.ii. We've found an end, which matches the top-most element of the start stack
                #         If the mode doesn't match our current nested depth, ignore the pair
                start, end = (starts.pop(), span)
                if mode == ('roots' if starts else 'leaves'):
                    continue
                yield start, end

            # IV. Adjust for any changes made by the caller to the buffer during iteration
            if delta := len(self) - oldlen:
                pos += delta
                b1 += delta

        # V. If we still have unmatched starts on the stack, raise an error
        if remaining := len(starts):
            err_text = f'Found {remaining} unmatched starts'
            err_lines = (f'`{s0}`: "{self[s0:s1]}"{self[s1 : s1 + 16]}...' for s0, s1 in starts)
            if DEBUG:
                err_text = '\n'.join(
                    [
                        err_text + ', e.g.:',
                        *(f'\t{s}' for s in err_lines),
                        f'\n...in text:\n"""\n{self.text[0]}\n"""',
                    ]
                )
            else:
                err_text += f', e.g. {mi.first(err_lines)}'
            raise ValueError(err_text)

    # ------------------
    # `*` Public Methods
    # ------------------
    @property
    def lines(self) -> list[str]:
        """The number of distinct lines in the buffer."""
        return self.text[0].splitlines()

    @property
    def has_fences(self) -> bool:
        """Whether the buffer has any fences at the moment.

        To see if fences are *configured*, use `bool(buffer.fence_rgx)` instead.
        """
        return self.fences.size > 0

    @property
    def fence_spans(self) -> Iterator[Span]:
        """An iterator over the current fence spans."""
        for s0, s1 in self.fences:
            yield Span((s0, s1))

    def __repr__(self) -> str:
        contents = []
        if len(self) > 50:
            contents.append(f'"{self.text[0][:50]}..."')
        else:
            contents.append(f'"{self.text[0]}"')

        contents.append(f'len={len(self)}')
        if self.uid:
            contents.append(f'uid="{self.uid}"')

        return 'Buffer(' + ', '.join(contents) + ')'

    def __str__(self) -> str:
        return self.serialize()

    def __len__(self) -> int:
        return len(self.text[0])

    def __getitem__(self, key: int | slice) -> str:
        return self.text[0][key]

    def slice(self, start: int, end: int = -1) -> str:
        """Convenience getter for slicing the buffer's text."""
        if end == -1:
            end = len(self)
        return self.text[0][start:end]

    def __contains__(self, val: str) -> bool:
        return val in self.text[0]

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

    def __add__(self, other: Self | str) -> Self:
        cls = type(self)
        if isinstance(other, Buffer):
            return cls(text=[self.text[0] + other.text[0]])
        elif isinstance(other, str):
            return cls(text=[self.text[0] + other])
        else:
            raise TypeError(f'Cannot concatenate Buffer with {type(other)}')

    def __iadd__(self, other: Self | str) -> Self:
        if isinstance(other, Buffer):
            self.text[0] += other.text[0]
        elif isinstance(other, str):
            self.text[0] += other
        else:
            raise TypeError(f'Cannot concatenate Buffer with {type(other)}')
        return self

    def replace(
        self,
        old: Span | tuple[int, int] | str | Pattern,
        new: str,
        count: int = 0,
        diff: int = 0,
    ) -> Self:
        """Replace the specified text with the new text, updating internal trackers as necessary.

        ```{tip} Prefer to pass a precalculated span if you have it, to prevent rework.
        ```

        Args:
            old: The substring, span, or regex pattern to replace.
            new: The new text to insert.
            count: The maximum number of replacements to make (0 for all). NOOP for spans.
            diff: When set, indicates that any fences found within the old text are still there, but
                have simply moved by this static amount.
        Returns:
            The modified Buffer instance (for convenient access and/or builder patterns).
        """
        if isinstance(old, Pattern):
            self._replace_regex(old, new, count)
        elif isinstance(old, (tuple, Span)):
            self._replace_span(old, new, diff)
        else:
            self._replace_string(old, new, count, diff)
        return self

    def insert(self, pos: int, new: str) -> None:
        """Convenience setter for replacing an empty span with new text.

        Args:
            pos: The position to insert the new text at.
            new: The new text to insert.
        """
        self._replace_span(Span(pos, pos), new)

    def drop(self, old: str | Span | tuple[int, int]) -> Self:
        """Convenience setter for removing the specified text from the buffer.

        Args:
            old: The substring or span to remove.
        """
        self.replace(old, '')
        return self

    def set(self, text: str) -> Self:
        """Convenience setter for replacing the entire content of the buffer at once.

        Args:
            text: The new text to set the buffer to.
        """
        self.text[0] = text
        self.fences = self._build_fences()
        return self

    def clear(self) -> Self:
        """Convenience setter for clearing the entire content of the buffer at once."""
        self.text[0] = ''
        if self.has_fences:
            self.fences = _no_spans()
        return self

    def strip(self, chars: str = '') -> Self:
        """Performantly strip the buffer of leading/trailing characters.

        Args:
            chars: The characters to strip. Defaults to whitespace.
        Returns:
            The same (modified) Buffer instance.
        """
        chars = chars or ' \t\n\r\v\f'
        n_left = len(list(it.takewhile(lambda x: x in chars, self.text[0])))
        n_right = len(list(it.takewhile(lambda i: self[i] in chars, range(-1, -len(self), -1))))
        if n_left or n_right:
            end = len(self) - n_right
            self.text[0] = self.text[0][n_left:end]

            if self.has_fences:
                if self.fences[0][0] < n_left or self.fences[-1][1] > end:
                    self.fences = self._build_fences()
                elif n_left:
                    self.fences -= n_left

        return self

    def match(self, rgx: Pattern, *args, **kwargs) -> Match | None:
        """Wrapper for regex.match()."""
        return rgx.match(self.text[0], *args, **kwargs)

    def search(self, rgx: Pattern, *args, **kwargs) -> Match | None:
        """Wrapper for regex.search()."""
        return rgx.search(self.text[0], *args, **kwargs)

    def findall(self, rgx: Pattern, *args, **kwargs) -> list[tuple[str, ...]]:
        """Wrapper for regex.findall()."""
        return rgx.findall(self.text[0], *args, **kwargs)

    def sub(self, rgx: Pattern, new: str, count: int = 0) -> None:
        """Direct wrapper for _replace_regex(), defined to match the base regex interface.

        Args:
            rgx: The regex pattern to replace.
            new: The new text to insert.
            count: The maximum number of replacements to make (0 for all).
        """
        self.replace(rgx, new, count)

    def apply(self, *functions: Callable[[str], str], b0: int = 0, b1: int = -1) -> Self:
        """Iteratively maps one or more functions to the text in this buffer, modifying it.

        Args:
            functions: One or more functions that take a string and return a string.
            b0: The positive, inclusive start bound.
            b1: The positive, exclusive end bound, or -1 to apply up to the end of the text.
        Returns:
            The modified Buffer instance (for convenient access and/or builder patterns).
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

    def dedent(self) -> Self:
        """Dedents all text evenly, so that the line with the fewest spaces starts at column 0."""
        self.text[0] = textwrap.dedent(self.text[0])
        return self

    def write(self, span: Span, text: str | Iterable[str], spacing: int = 0, diff: int = 0) -> None:
        """Wraps a given string output in preparation for it to be inserted into the article.

        Offers four distinct spacing modes:
        - 0: No spacing
        - 1: Ensures space or newline exists before and after
        - 2: Ensures newline exists before and after
        - 3: Ensures two newlines (i.e. an empty line) exists before and after

        Args:
            span: The span of text to replace.
            text: The text to insert, either as a single string or an iterable of strings to join.
            spacing: The spacing mode to use (0-3).
            diff: When set, indicates that any fences found within the old text are still there, but
                have simply moved by this static amount.
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
        self._replace_span(span, newtext, diff)

    def find_chads(self, rgx: Pattern, b0: int = 0, b1: int = -1) -> tuple[list[Span], list[Span]]:
        """Searches for one or more "hanging chads" -- unmatched delimiters of the given regex pair.

        See `find_pair_match()` for details on pairs in general.

        Args:
            rgx: The regex pattern with the named groups 'start' and 'end'.
            b0: The positive, inclusive start bound for searching.
            b1: The positive, exclusive end bound for searching, or -1 to search the whole text.
        Returns:
            A tuple of two lists: (unmatched_starts, unmatched_ends)
        """
        pos = b0
        b1 = b1 if b1 != -1 else len(self)
        starts: list[Span] = []
        ends: list[Span] = []
        while match := rgx.search(self.text[0][:b1], pos):
            params = match.groupdict()
            span = Span(match.span())
            s0, pos = span

            if self._is_fenced(s0) or params.get('is_complete', None):
                # Skip fenced regions
                continue

            elif params.get('start', ''):
                starts.append(span)
            elif len(starts) == 0:
                ends.append(span)
            else:
                starts.pop()

        return starts, ends

    def find_pair_match(
        self,
        rgx: Pattern,
        pos: int,
        b0: int = 0,
        b1: int = -1,
    ) -> tuple[Span, str, str, str] | None:
        """Find the the given substrings "partner", handling nesting & other edge cases.

        Args:
            rgx: The regex pattern with the named groups 'start' and 'end'.
            pos: The position of the known delimiter.
            b0: The start bound for searching.
            b1: The end bound for searching.
        Returns:
            `(full_span, start_text, body_text, end_text)` if a match is found, else `None`.
        """
        for span, start, body, end in self.pair_iterator(rgx, 'all', b0, b1):
            if pos in span:
                return span, start, body, end
        return None

    def pair_iterator(
        self,
        rgx: Pattern,
        mode: PairMode = 'all',
        b0: int = 0,
        b1: int = -1,
    ) -> Iterator[tuple[Span, str, str, str]]:
        """Iterate through matching "pairs" of delimiters, handling nesting and other edge cases.

        Like the other Buffer iterators, this method supports a read+write paradigm where callers
        modify the buffer's text while they iterate over it. To make this possible, it is assumed
        that the caller will only ever modify the last-yielded span of text during each iteration.

        It also respects the 'fence' spans specified during initialization, such as code blocks in
        Markdown files or character sets in regular expressions.

        Args:
            rgx: The regex pattern with the named groups 'start' and 'end'.
            mode: 'all' by default, 'roots' to exclude nested pairs, or 'leaves' for the opposite.
            b0: The positive, inclusive start bound for searching.
            b1: The positive, exclusive end bound for searching, or -1 to search the whole text.
        Yields:
            Tuples of spans representing the start and end delimiters.
        """
        yield from map(self._yield_pair, self.raw_pair_iterator(rgx, mode, b0, b1))

    def rgx_iterator(
        self,
        rgx: Pattern | str,
        recursive: bool = False,
        b0: int = 0,
        b1: int = -1,
    ) -> Iterator[Match]:
        """Iterate over all matches of the given regex pattern in the buffer.

        Like the other Buffer iterators, this method supports a read+write paradigm where callers
        modify the buffer's text while they iterate over it. To make this possible, it is assumed
        that the caller will only ever modify the last-yielded match of text during each iteration.

        It also respects the 'fence' spans specified during initialization, such as code blocks in
        Markdown files or character sets in regular expressions.

        Args:
            rgx: The regex pattern to search for (compiled or as a plain string).
            recursive: If set, overlapping matches are also found.
            b0: The positive, inclusive start bound for searching.
            b1: The positive, exclusive end bound for searching, or -1 to search the whole text.
        """
        if isinstance(rgx, str):
            rgx = self.RGXS.get(rgx, re.compile(rgx))

        pos = b0
        b1 = b1 if b1 != -1 else len(self)
        while match := rgx.search(self.text[0], pos):
            x0, x1 = match.span()
            if x1 > b1:
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

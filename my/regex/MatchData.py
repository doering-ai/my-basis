############
### HEAD ###
############
### STANDARD
from typing import ClassVar, Self, Any, override
import functools as ft

### EXTERNAL
from regex import Match
import pydantic as pyd

### INTERNAL
from ..utils import ut
from ..types import Span, Predicate


############
### BODY ###
############
class MatchData(Predicate):
    r"""Ergonomic container for regex search results, especially those with repeated groups.

    Extends Predicate to STORE captured group values while also maintaining a reference
    to the original match object for accessing spans, positions, and matched text.

    Provides cached properties for common match attributes like start, end, and text.

    Examples:
        Wrap a match and access its repeated captures ergonomically::

            >>> import regex as re
            >>> data = MatchData(match=re.fullmatch(r'(?:(?P<w>\w+) ?)+', 'ab cd'))
            >>> data['w']
            ['ab', 'cd']
            >>> data.at('w')
            'cd'
            >>> data.text, data.start, data.end
            ('ab cd', 0, 5)

        Empty results are falsy, so lookups chain cleanly::

            >>> bool(MatchData())
            False
    """

    match: ut.MatchField | None = None
    duplicates: bool = True

    # -------------------
    # `.` Initial Methods
    # -------------------
    @override
    @classmethod
    def new(
        cls,
        *args: Any,
        match: Match | None = None,
        **kwargs: Any,
    ) -> Self:
        r"""Construct a new MatchData, coercing mapping-like arguments and binding a source match.

        Duplicates are always enabled so repeated capture groups accumulate their values; empty
        group names and empty value lists are dropped.

        Args:
            *args: Mapping-like objects to merge into the captured group data.
            match: Original regex match object, retained for span/position/text access.
            **kwargs: Additional group values to merge.
        Returns:
            New MatchData holding the merged group data.
        Examples:
            Merge mapping-like arguments, accumulating repeated keys::

                >>> from my import MatchData
                >>> MatchData.new(dict(k=['v1']), k='v2')
                MatchData({'k': ['v1', 'v2']})

            Bind a source match to expose its captures, spans, and text::

                >>> import regex as re
                >>> MatchData.new(match=re.fullmatch(r'(?:(?P<word>\w+) ?)+', 'one two three'))
                MatchData("one two three" -> {'word': ['one', 'two', 'three']})
        """
        ret = cls(duplicates=True, overwrite=False, match=match)
        for arg in (*args, kwargs):
            ret._process_arg(arg)
        ret.data = {k: v for k, v in ret.data.items() if k and v}
        return ret

    @pyd.model_validator(mode='after')
    def _validate_matchdata(self) -> Self:
        """Populate the group data from the source match when none was provided explicitly."""
        if not self.data and self.match is not None:
            self.data: dict[str, list[str]] = self.match.capturesdict()
        return self

    # -------------------
    # `-` Private Methods
    # -------------------

    # -------------------
    # `+` Primary Methods
    # -------------------
    CACHED_PROPERTIES: ClassVar[set[str]] = {'flat', 'span', 'start', 'end', 'text', 'size'}

    @ft.cached_property
    def flat(self) -> dict[str, str]:
        r"""A flat dictionary of the last non-empty value for each group.

        Examples:
            Flatten repeated captures down to their final values::

                >>> import regex as re
                >>> from my import MatchData
                >>> data = MatchData(match=re.fullmatch(r'(?:(?P<word>\w+) ?)+', 'one two three'))
                >>> data['word']
                ['one', 'two', 'three']
                >>> data.flat
                {'word': 'three'}
                >>> (data.text, data.span, data.size)
                ('one two three', Span(0, 13), 13)
        """
        return {key: val for key in self.data.keys() if (val := self.at(key))}

    @ft.cached_property
    def span(self) -> Span:
        """The span of the match if present; otherwise the null span (0, 0)."""
        return Span._fast(*self.match.span()) if self.match else Span._fast(0, 0)

    @ft.cached_property
    def start(self) -> int:
        """The start index of the match if present; otherwise 0."""
        return self.match.start() if self.match else 0

    @ft.cached_property
    def end(self) -> int:
        """The end index of the match if present; otherwise 0."""
        return self.match.end() if self.match else 0

    @ft.cached_property
    def text(self) -> str:
        """The text of the match if present; otherwise an empty string."""
        return self.match[0] if self.match else ''

    @ft.cached_property
    def size(self) -> int:
        """The number of characters matched."""
        return len(self.text)

    # ------------------
    # `*` Public Methods
    # ------------------
    def __repr__(self) -> str:
        if self.match is not None:
            return f'MatchData("{self.text}" -> {self.data})'
        else:
            return f'MatchData({self.data})'

    def print(self, indent: str = '') -> None:
        r"""Print captured groups in a formatted table.

        Args:
            indent: String to prepend to each line for indentation.
        Examples:
            Repeated captures print as lists, single captures as scalars::

                >>> import regex as re
                >>> from my import MatchData
                >>> data = MatchData(match=re.fullmatch(r'(?:(?P<word>\w+) ?)+', 'one two three'))
                >>> data.print(indent='  ')
                  word: ['one', 'two', 'three']
        """
        width = min(max(map(len, self.keys())), 48)
        print(
            '\n'.join(
                [
                    f'{indent}{key:>{width}}: {values[0] if len(values) == 1 else values}'
                    for key, values in self.items()
                ]
            )
        )

    def set_to(self, other: 'MatchData | None') -> None:
        """Replace this MatchData's contents with another's, clearing caches.

        Args:
            other: MatchData to copy from, or None to clear.
        """
        self.data = {key: [*values] for key, values in other.items()} if other else {}
        self.match = other.match if other is not None else None
        ut.clear_cached_properties(self, *self.CACHED_PROPERTIES)

    def clear(self) -> None:
        """Clear all match data and captured groups."""
        self.set_to(None)

    def starts(self, field: str) -> list[int]:
        """Return the start indices of every capture of the specified field."""
        if self.match is None or field not in self:
            return []
        return self.match.starts(field)

    def spans(self, field: str) -> list[Span]:
        r"""Return the spans of every capture of the specified field.

        Examples:
            Locate every capture of a repeated group (see also `starts()` and `ends()`)::

                >>> import regex as re
                >>> from my import MatchData
                >>> data = MatchData(match=re.fullmatch(r'(?:(?P<word>\w+) ?)+', 'one two three'))
                >>> data.spans('word')
                [Span(0, 3), Span(4, 7), Span(8, 13)]
                >>> data.starts('word')
                [0, 4, 8]
                >>> data.ends('word')
                [3, 7, 13]
        """
        if self.match is None or field not in self:
            return []
        return [Span._fast(*s) for s in self.match.spans(field)]

    def ends(self, field: str) -> list[int]:
        """Return the end indices of every capture of the specified field."""
        if self.match is None or field not in self:
            return []
        return self.match.ends(field)

    def matches(self, other: 'MatchData') -> bool:
        r"""Determine if two MatchData objects have the same set of capture group names.

        Args:
            other: MatchData to compare against.
        Returns:
            True if both have the same keys (ignoring values and order).
        Examples:
            Compare the captured shape, not the captured values::

                >>> import regex as re
                >>> from my import MatchData
                >>> data = MatchData(match=re.fullmatch(r'(?:(?P<word>\w+) ?)+', 'one two three'))
                >>> MatchData(data={'word': ['x']}).matches(data)
                True
        """
        lhs, rhs = set(self.keys()), set(other.keys())
        nulls = (not lhs, not rhs)
        if all(nulls):
            return True
        elif any(nulls):
            return False
        else:
            return not bool(lhs ^ rhs)

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
    """Ergonomic container for regex search results, especially those with repeated groups.

    Extends Predicate to STORE captured group values while also maintaining a reference
    to the original match object for accessing spans, positions, and matched text.

    Provides cached properties for common match attributes like start, end, and text.
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
        ret = cls(duplicates=True, overwrite=False, match=match)
        for arg in (*args, kwargs):
            ret._process_arg(arg)
        ret.data = {k: v for k, v in ret.data.items() if k and v}
        return ret

    @pyd.model_validator(mode='after')
    def _validate_matchdata(self) -> Self:
        """Ensure that all captured group values are lists when duplicates are allowed."""
        if not self.data and self.match is not None:
            self.data: dict[str, list[str]] = self.match.capturesdict()
        return self

    # -------------------
    # `-` Private Methods
    # -------------------

    # -------------------
    # `+` Primary Methods
    # -------------------
    CACHED_PROPERTIES: ClassVar[set[str]] = {'data', 'span', 'start', 'end', 'text', 'size'}

    @ft.cached_property
    def flat(self) -> dict[str, str]:
        """Returns a flat dictionary of the last non-empty value for each group."""
        return {key: val for key in self.data.keys() if (val := self.at(key))}

    @ft.cached_property
    def span(self) -> Span:
        """Returns the span of the match if present; otherwise returns the null span (0, 0)."""
        return Span(self.match.span() if self.match else (0, 0))

    @ft.cached_property
    def start(self) -> int:
        """Returns the start index of the match if present; otherwise returns 0."""
        return self.match.start() if self.match else 0

    @ft.cached_property
    def end(self) -> int:
        """Returns the end index of the match if present; otherwise returns 0."""
        return self.match.end() if self.match else 0

    @ft.cached_property
    def text(self) -> str:
        """Returns the text of the match if present; otherwise returns an empty string."""
        return self.match[0] if self.match else ''

    @ft.cached_property
    def size(self) -> int:
        """Returns the number of characters matched."""
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
        """Print captured groups in a formatted table.

        Args:
            indent: String to prepend to each line for indentation.
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
        """Returns the start indices of the match for the specified field."""
        if self.match is None or field not in self:
            return []
        return self.match.starts(field)

    def spans(self, field: str) -> list[Span]:
        """Returns the spans of the match for the specified field."""
        if self.match is None or field not in self:
            return []
        return list(map(Span, self.match.spans(field)))

    def ends(self, field: str) -> list[int]:
        """Returns the end indices of the match for the specified field."""
        if self.match is None or field not in self:
            return []
        return self.match.ends(field)

    def matches(self, other: 'MatchData') -> bool:
        """Determine if two MatchData objects have the same set of capture group names.

        Args:
            other: MatchData to compare against.
        Returns:
            True if both have the same keys (ignoring values and order).
        """
        lhs, rhs = set(self.keys()), set(other.keys())
        nulls = (not lhs, not rhs)
        if all(nulls):
            return True
        elif any(nulls):
            return False
        else:
            return not bool(lhs ^ rhs)

############
### HEAD ###
############
### STANDARD
from typing import ClassVar

### EXTERNAL
import regex as re

### INTERNAL
from ..infra import Series, DELIM


############
### BODY ###
############
class Span(tuple[int, int]):
    """
    An immutable half-open interval [start, end) representing a text range.

    Spans are tuples of two integers where the first is inclusive and the second is
    exclusive. They support arithmetic, containment checks, intersection testing,
    and merging operations. Can be constructed from various formats including strings
    like "10-20" or "432-3" (abbreviated form).
    """
    DELIM_RGX: ClassVar[re.Pattern] = re.compile(r' ?[-,\/]+ ?')

    def __new__(cls, arg0: 'Series|int|float|str|Span' = -1, arg1: int | str = -1):
        if isinstance(arg0, Span):
            return arg0

        if isinstance(arg0, Series):
            # I. Handle tuple input
            assert len(arg0) == 2, 'Tuple must have exactly 2 elements'
            assert not isinstance(arg0, set), 'Tuple cannot be a set'
            x0, x1 = int(arg0[0]), int(arg0[1])

        elif isinstance(arg0, str):
            # II. Handle string input with delimiters
            parts = cls.DELIM_RGX.split(arg0)
            assert 0 < len(parts) <= 2, f'Cannot parse span from string: {arg0}'
            if len(parts) == 2:
                x0, x1 = int(parts[0]), int(parts[1])
            else:
                x0, x1 = int(arg0), int(arg1 if arg1 != -1 else arg0)

        elif arg0 == arg1:
            # III. Handle empty parameters and points
            x0 = x1 = max(int(arg0), 0)

        elif arg1 != -1:
            # IV. Handle numeric input with second argument
            x0, x1 = int(arg0), int(arg1)
        else:
            raise ValueError('Must provide either a tuple/string or two numeric arguments')

        # Create and return the tuple
        assert x0 <= x1, f'Invalid span: {x0} > {x1}'
        return super().__new__(cls, (x0, x1))

    @property
    def delta(self) -> int:
        """Return the length of this span."""
        return self[1] - self[0]

    def __repr__(self) -> str:
        return f'Span({self[0]}, {self[1]})'

    def __lt__(self, other: object) -> bool:
        if isinstance(other, tuple) and len(other) == 2 and isinstance(other[0], int):
            return self[0] < other[0]
        return False

    def __eq__(self, other: object) -> bool:
        if isinstance(other, tuple) and len(other) == 2:
            return self[0] == other[0] and self[1] == other[1]
        return False

    def __str__(self) -> str:
        p0, p1 = self
        if p0 == p1:
            return ''
        elif p0 == p1 - 1:
            return f'{p0}'
        else:
            return f'{p0}-{p1 - 1}'

    def __bool__(self) -> bool:
        return self[0] != self[1]

    def __hash__(self) -> int:
        return hash(self[0]) ^ hash(self[1])

    def __contains__(self, value: object) -> bool:
        p0, p1 = self
        if p0 == p1:
            return False
        elif isinstance(value, int):
            return self[0] <= value < self[1]
        elif isinstance(value, tuple) and len(value) == 2:
            i0, i1 = value
            if isinstance(i0, int) and isinstance(i1, int):
                return p0 < i1 and i0 < p1
        return False

    def intersects(self, other: 'Span|tuple[int, int]') -> bool:
        """
        Check if this span overlaps with another span.

        Args:
            other: Span to test for intersection.
        Returns:
            True if the spans overlap.
        """
        return other in self

    def __add__(self, other: object) -> 'Span':
        if isinstance(other, int):
            return Span((self[0] + other, self[1] + other))
        if isinstance(other, (tuple, list)) and len(other) == 2:
            o0, o1 = other
            if isinstance(o0, int) and isinstance(o1, int):
                return Span((self[0] + o0, self[1] + o1))
        return self

    @staticmethod
    def serialize(*args: 'Span|tuple[int, int]') -> str:
        """
        Serialize multiple spans to a delimited string.

        Args:
            *args: Spans to serialize.
        Returns:
            String with spans separated by DELIM.
        """
        return DELIM.join(map(str, args))

    @classmethod
    def parse(cls, text: str) -> 'Span':
        """
        Parse a span from text with smart abbreviation handling.

        Handles formats like:
        - "10-20": Full range
        - "432-3": Abbreviated end (becomes 432-433)
        - "1475-33": Abbreviated end with rollover (becomes 1475-1533)
        - "42": Single position (becomes 42-43)

        Args:
            text: String to parse.
        Returns:
            Parsed Span, or empty Span (0, 0) if parsing fails.
        """
        segments = cls.DELIM_RGX.split(text)
        if len(segments) == 2 and all(map(str.isdigit, segments)):
            # Account for ommitted digits (e.g. 432-33, or even 432-3)
            x0, x1 = segments

            # Add a tens/hundreds place where necessary (e.g. 1475-33 -> 1475-1533)
            if (digit_delta := len(x0) - len(x1)) > 0:
                prefix, lhs = x0[:digit_delta], x0[digit_delta:]
                if x1 <= lhs:
                    prefix = str(int(prefix) + 1)

                x1 = f'{prefix}{x1}'

            return Span((int(x0), int(x1) + 1))
        elif text.isdigit():
            return Span((int(text), int(text) + 1))
        else:
            return Span((0, 0))

    def join(self, other: 'Span|tuple[int, int]') -> 'Span':
        """
        Create a span that encompasses both this span and another.

        Args:
            other: Span to join with.
        Returns:
            New span from the minimum start to maximum end.
        """
        return Span(min(self[0], other[0]), max(self[1], other[1]))

    @classmethod
    def merge(cls, *args: 'tuple[int, int]|Span') -> list['Span']:
        """
        Merge overlapping spans into a minimal set of non-overlapping spans.

        Args:
            *args: Spans to merge.
        Returns:
            Sorted list of non-overlapping spans covering the same positions.
        """
        spans = list(sorted(set(map(Span, args))))
        i = 0
        while i < len(spans) - 1:
            while i < len(spans) - 1 and spans[i + 1][0] <= spans[i][1]:
                spans[i] = spans[i].join(spans[i + 1])
                spans.pop(i + 1)
            i += 1

        return spans

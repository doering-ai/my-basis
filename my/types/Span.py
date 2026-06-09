############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import ClassVar, Self, overload
from collections.abc import Iterable, Iterator

### EXTERNAL
import regex as re
from pydantic_core import core_schema as pyds

### INTERNAL
from ..infra.types import Vec, String, Scalar, _Vec, _Iter, Iter, Atom
from ..infra.constants import DELIM
from ..typing import ty


############
### BODY ###
############
class Span[T: Scalar](tuple[T, T]):
    """An immutable half-open interval [start, end), typically representing a text range.

    Spans are a simple wrapper around `tuple[int, int]` built to support arithmetic (shifting by
    integers), containment testing (checking if positions or other spans intersect), and merging
    operations (combining overlapping spans into minimal non-overlapping sets).

    The class provides flexible construction from strings like `"10-20"` or abbreviated forms like
    `"432-3"` (interpreted as 432-433). The `parse()` classmethod handles smart abbreviation
    expansion, where trailing digits inherit leading digits from the start position.
    """

    DELIM_RGX: ClassVar[re.Pattern] = re.compile(r' ?[-,\/]+ ?')

    # -------------------
    # `.` Initial Methods
    # -------------------
    @overload  # empty
    def __new__(cls) -> Span[int]: ...
    @overload  # basic
    def __new__[S: Scalar](cls, arg0: S, arg1: S) -> Span[S]: ...
    @overload  # monoarg
    def __new__[S: Scalar](cls, arg0: Span[S] | tuple[S, S]) -> Span[S]: ...
    @overload
    def __new__[S: Scalar](
        cls,
        arg0: String | Scalar | Span,
        arg1: String | Scalar,
        tvar: type[S],
    ) -> Span[S]: ...
    def __new__[S: Scalar](
        cls,
        arg0: String | Scalar | Span[S] | tuple[S, S] = -1,
        arg1: String | Scalar = -1,
        tvar: type[S] | None = None,
    ) -> Span[S]:
        """Create a new Span instance, overriding default tuple behavior w/ flexible coercion."""
        if isinstance(arg0, Span):
            # Don't bother autoconverting span contents
            return arg0  # type: ignore
        if tvar is None:
            # Set default to integer spans
            tvar = int  # type: ignore

        a1 = ty.cast(arg1, int)
        if a1 is None:
            raise ValueError(f'Invalid second argument for Span: {arg1}')

        if isinstance(arg0, String):
            # II. Handle string input with delimiters
            a0 = ty.normalize(arg0).strip()
            assert a0, 'Cannot create Span from empty string'
            parts = cls.DELIM_RGX.split(a0)
            match len(parts), parts:
                case 1, (p0,):
                    x0 = int(p0)
                    return x0, (x0 if (a1 == -1) else a1)
                case 2, (p0, p1):
                    x0, x1 = int(p0), int(p1)
                case _:
                    raise ValueError(f'Invalid string format for Span: {arg0}')

        elif isinstance(arg0, Iter):
            # I. Handle tuple input
            if (tup := ty.cast(arg0, tuple[int, int])) is not None:
                x0, x1 = tup
            else:
                x0 = x1 = max(a1, 0)

        elif arg0 == arg1:
            # III. Handle empty rangers, missing parameters, and/or points
            x0 = x1 = max(a1, 0)

        elif arg1 != -1:
            # IV. Handle numeric input with second argument
            if (_x0 := ty.cast(arg0, int)) is not None:
                x0, x1 = _x0, a1
            raise ValueError(f'Invalid first argument for Span: {arg0}')
        else:
            raise ValueError('Must provide either a tuple/string or two numeric arguments')

        # Create and return the tuple
        assert x0 <= x1, f'Invalid span: {x0} > {x1}'
        return super().__new__(cls, (x0, x1))

    @classmethod
    def __get_pydantic_core_schema__(cls, source: type, handler) -> pyds.CoreSchema:
        return pyds.no_info_before_validator_function(cls, pyds.is_instance_schema(cls))

    # -------------------
    # `-` Private Methods
    # -------------------

    # -------------------
    # `+` Primary Methods
    # -------------------

    # ------------------
    # `*` Public Methods
    # ------------------
    # --------------
    # `*0` Overrides
    # --------------
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
        if not self:
            return False
        elif isinstance(value, int):
            return self[0] <= value < self[1]
        elif isinstance(value, Series):
            if len(value) == 2:
                p0, p1 = sorted(value)
                if isinstance(p0, int) and isinstance(p1, int):
                    return self[0] < p1 and self[1] > p0
            return any(v in self for v in value)
        return False

    def __add__(self, other: object) -> 'Span':
        if isinstance(other, int):
            return Span((self[0] + other, self[1] + other))
        if isinstance(other, (tuple, list)) and len(other) == 2:
            o0, o1 = other
            if isinstance(o0, int) and isinstance(o1, int):
                return Span((self[0] + o0, self[1] + o1))
        return self

    # ---------------
    # `*1` Properties
    # ---------------
    @property
    def delta(self) -> T:
        """Return the length of this span."""
        return self[1] - self[0]

    # ------------
    # `*2` Methods
    # ------------
    def intersects(self, other: tuple[T, T] | Self | list[Self]) -> bool:
        """Check if this span overlaps with another span.

        Args:
            other: Span to test for intersection.
        Returns:
            True if the spans overlap.
        """
        return other in self

    def join(self, other: Self | tuple[T, T]) -> Self:
        """Create a span that encompasses both this span and another.

        Args:
            other: Span to join with.
        Returns:
            New span from the minimum start to maximum end.
        """
        return type(self)(min(self[0], other[0]), max(self[1], other[1]))

    @classmethod
    def serialize(cls, *args: Self | tuple[T, T]) -> str:
        """Serialize multiple spans to a delimited string.

        Args:
            *args: Spans to serialize.
        Returns:
            String with spans separated by DELIM.
        """
        return DELIM.join(map(str, args))

    @classmethod
    def parse(cls, text: str) -> Self:
        """Parse a span from text with smart abbreviation handling.

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

            return cls((int(x0), int(x1) + 1))
        elif text.isdigit():
            return cls((int(text), int(text) + 1))
        else:
            return cls((0, 0))

    @classmethod
    def merge(cls, *args: tuple[int, int] | Self) -> list[Self]:
        """Merge overlapping spans into a minimal set of non-overlapping spans.

        Args:
            *args: Spans to merge.
        Returns:
            Sorted list of non-overlapping spans covering the same positions.
        """
        spans = list(sorted(set(map(cls, args))))
        i = 0
        while i < len(spans) - 1:
            while i < len(spans) - 1 and spans[i + 1][0] <= spans[i][1]:
                spans[i] = spans[i].join(spans[i + 1])
                spans.pop(i + 1)
            i += 1

        return spans

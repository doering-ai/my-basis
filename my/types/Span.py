############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import ClassVar, Self, cast, overload
from collections.abc import Iterable

### EXTERNAL
import regex as re
from pydantic_core import core_schema as pyds
import more_itertools as mi

### INTERNAL
from ..infra.types import String, Scalar, Vec, Real
from ..infra.constants import DELIM
from ..typing import ty, MyType

import inspect

Empty = type[inspect.Parameter.empty]
empty = inspect.Parameter.empty


############
### BODY ###
############
class Span[T: Real](tuple[T, T]):
    """An immutable half-open interval [start, end), typically representing a text range.

    Spans are a simple wrapper around `tuple[int, int]` built to support arithmetic (shifting by
    integers), containment testing (checking if positions or other spans intersect), and merging
    operations (combining overlapping spans into minimal non-overlapping sets).

    The class provides flexible construction from strings like `"10-20"` or abbreviated forms like
    `"432-3"` (interpreted as 432-433). The `parse()` classmethod handles smart abbreviation
    expansion, where trailing digits inherit leading digits from the start position. Note that
    `str()` renders the *inclusive* form -- `Span(3, 9)` becomes `'3-8'` -- which is what `parse()`
    expects back.

    Examples:
        Construct spans from points, pairs, or strings::

            >>> from my import Span
            >>> Span(3, 9)
            Span(3, 9)
            >>> Span('10-20')
            Span(10, 20)

        Shift a span by an integer and test containment::

            >>> Span(3, 9) + 1
            Span(4, 10)
            >>> 5 in Span(3, 9)
            True
            >>> (8, 12) in Span(3, 9)
            True

        Render the inclusive string form::

            >>> str(Span(3, 9))
            '3-8'
    """

    DELIM_RGX: ClassVar[re.Pattern] = re.compile(r' ?[-,\/]+ ?')

    # -------------------
    # `.` Initial Methods
    # -------------------
    @overload  # empty
    def __new__(cls) -> Span[int]: ...
    @overload  # basic
    def __new__[S: Real](cls, arg0: S, arg1: S) -> Span[S]: ...
    @overload  # monoarg
    def __new__[S: Real](cls, arg0: Span[S] | tuple[S, S]) -> Span[S]: ...
    @overload
    def __new__[S: Real](
        cls,
        arg0: String | Scalar | tuple[Scalar, Scalar] | Span,
        arg1: String | Scalar,
        tvar: type[S] | MyType[S],
    ) -> Span[S]: ...
    def __new__[S: Real](
        cls,
        arg0: String | Scalar | Span[S] | tuple[Scalar, Scalar] | Empty = empty,
        arg1: String | Scalar | Empty = empty,
        tvar: type[S] | MyType[S] = int,  # ty:ignore[invalid-parameter-default]
    ) -> Span[S]:
        """Create a new Span instance, overriding default tuple behavior w/ flexible coercion."""
        if isinstance(arg0, Span):
            # Don't bother autoconverting span contents
            return arg0  # type: ignore
        elif arg0 is empty:
            return cls(0, 0, tvar)
        elif arg1 is not empty:
            arg0 = (arg0, arg1)  # type: ignore

        # Set default to integer spans
        _type: MyType[S] = MyType(tvar or int)  # type: ignore
        main = _type.main
        if main is None:
            raise ValueError(f'Invalid second argument for Span: {arg1}')

        x0, x1 = cls._new_impl(arg0, main)  # type: ignore[bad-specialization]
        if isinstance(x0, (int, float)) and isinstance(x1, (int, float)):
            assert x0 <= x1, f'Invalid span: {x0} > {x1}'
        # Pyrefly cannot bind tuple's element TypeVar through a generic tuple subclass.
        return cast('Span[S]', super().__new__(cls, [x0, x1]))  # pyrefly: ignore[bad-argument-type]

    @classmethod
    def _fast(cls, a: int, b: int) -> Span[int]:
        """Trusted fast-path constructor for int pairs from regex matches.

        Bypasses all type coercion, MyType construction, and validation.
        Use only when inputs are guaranteed valid ints with ``a <= b``
        (e.g. ``match.span()`` results inside hot iterators).

        Args:
            a: Start position (inclusive).
            b: End position (exclusive).
        Returns:
            A Span without any validation overhead.
        """
        return cast(
            'Span[int]',
            super().__new__(cls, [a, b]),  # pyrefly: ignore[bad-argument-type]
        )

    @classmethod
    def _new_impl[S: Real](
        cls,
        data: String | Scalar | Span[S] | Iterable[Scalar] | Empty | None,
        tvar: type[S],
    ) -> tuple[S, S]:
        """Coerce the raw constructor argument into a validated (start, end) tuple."""
        zero = tvar()
        if data in {empty, None}:
            # I. Null-equivelant args result in a set of zeros, which are falsey
            return zero, zero

        if isinstance(data, String):
            # II. Handle string input with delimiters
            text = ty.normalize(data).strip()
            segments = [s for s in cls.DELIM_RGX.split(text) if s]
            nums = [v for s in segments if (v := ty.cast(s, tvar)) is not None]
            if len(nums) != len(segments):
                # A segment that didn't cast cleanly (e.g. 'a-b') can't be a valid Span.
                nums = []
            match len(nums), nums:
                case 1, (p0,):
                    return p0, p0
                case 2, (p0, p1):
                    return p0, p1
                case _:
                    raise ValueError(f'Invalid string format for Span: {data}')

        elif isinstance(data, Scalar):
            # III. Handle empty rangers, missing parameters, and/or points
            if (x0 := ty.cast(data, tvar)) is not None:
                return x0, x0

        elif isinstance(data, Iterable):
            # IV. Handle numeric input with second argument
            items = list(data)
            if len(items) <= 2:
                a0, a1 = mi.padded((ty.cast(d, tvar) for d in items), zero, 2)
                if a0 is not None and a1 is not None:
                    return a0, a1

        raise ValueError(f'Invalid first argument for Span: {data=}, t0={type(data)}, {tvar=})')

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
        elif isinstance(value, Vec):
            if len(value) == 2:
                p0, p1 = sorted(value)
                if isinstance(p0, int) and isinstance(p1, int):
                    return self[0] < p1 and self[1] > p0
            return any(v in self for v in value)
        return False

    def __add__(self, other: object) -> Span:
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
        return self[1] - self[0]  # type: ignore[bad-return]

    # ------------
    # `*2` Methods
    # ------------
    def intersects(self, other: tuple[T, T] | Self | list[Self]) -> bool:
        """Check if this span overlaps with another span.

        Args:
            other: Span to test for intersection.
        Returns:
            True if the spans overlap.
        Examples:
            Test a partial overlap::

                >>> from my import Span
                >>> Span(3, 9).intersects((8, 12))
                True
        """
        return other in self

    def join(self, other: Self | tuple[T, T]) -> Self:
        """Create a span that encompasses both this span and another.

        Args:
            other: Span to join with.
        Returns:
            New span from the minimum start to maximum end.
        Examples:
            Join two overlapping spans::

                >>> from my import Span
                >>> Span(3, 9).join((7, 15))
                Span(3, 15)
        """
        return type(self)(min(self[0], other[0]), max(self[1], other[1]))

    @classmethod
    def serialize(cls, *args: Self | tuple[T, T]) -> str:
        """Serialize multiple spans to a delimited string.

        Args:
            *args: Spans to serialize.
        Returns:
            String with spans separated by `DELIM`.
        Examples:
            Serialize two spans (inclusive display form)::

                >>> from my import Span
                >>> Span.serialize(Span(1, 3), Span(8, 12))
                '1-2 // 8-11'
        """
        return DELIM.join(map(str, args))

    @classmethod
    def parse(cls, text: str) -> Self:
        """Parse a span from text with smart abbreviation handling.

        Handles formats like:

        - `"10-20"`: Full range
        - `"432-3"`: Abbreviated end (becomes 432-433)
        - `"1475-33"`: Abbreviated end with rollover (becomes 1475-1533)
        - `"42"`: Single position (becomes 42-43)

        Args:
            text: String to parse.
        Returns:
            Parsed Span, or empty Span (0, 0) if parsing fails.
        Examples:
            Expand abbreviated inclusive ranges into half-open spans::

                >>> from my import Span
                >>> Span.parse('432-3')
                Span(432, 434)
                >>> Span.parse('1475-33')
                Span(1475, 1534)
                >>> Span.parse('42')
                Span(42, 43)
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
        Examples:
            Collapse overlapping spans::

                >>> from my import Span
                >>> Span.merge((0, 5), (3, 9), (12, 15))
                [Span(0, 9), Span(12, 15)]
        """
        spans = list(sorted(set(map(cls, args))))
        i = 0
        while i < len(spans) - 1:
            while i < len(spans) - 1 and spans[i + 1][0] <= spans[i][1]:
                spans[i] = spans[i].join(spans[i + 1])
                spans.pop(i + 1)
            i += 1

        return spans

############
### HEAD ###
############
### STANDARD
from typing import ClassVar, Self, Literal
import functools as ft

### EXTERNAL
from pydantic_core import core_schema as pyds
import regex as re

### INTERNAL
from .meta_rgxs import META_RGXS


############
### BODY ###
############
@ft.total_ordering
class Quantifier:
    """Subatomic syntax that specifies how many times the atom is allowed to occur.

    Examples:
        Inspect a quantifier's range and traits::

            >>> quant = Quantifier('{2,4}')
            >>> quant.range, quant.is_ranged, quant.is_optional
            ((2, 4), True, False)

        The lazy/possessive suffix is separated from the base::

            >>> Quantifier('*+').base, Quantifier('*+').extra
            ('*', '+')
    """

    RGX: ClassVar[re.Pattern] = META_RGXS['quant']
    data: str = ''

    # -------------------
    # `.` Initial Methods
    # -------------------
    def __init__(self, data: str | Self = '', extra: Literal['', '?', '+'] | None = None) -> None:
        """Initialize a Quantifier from a string or another Quantifier."""
        if isinstance(data, Quantifier):
            self.data = data.data if extra is None else data.base + extra
        elif data := data.lstrip(')'):
            assert self.RGX.fullmatch(data), f'Invalid quantifier: {data!r}'
            self.data = data if extra is None else data + extra
        elif extra:
            self.data = r'{1}' + extra

    @classmethod
    def from_range(cls, r0: int, r1: int, extra: Literal['', '?', '+'] | None = None) -> Self:
        """Create a Quantifier from a range of occurrences, choosing the shortest valid syntax.

        Args:
            r0: Minimum number of occurrences (must be non-negative).
            r1: Maximum number of occurrences, or a negative value for "unbounded".
            extra: Optional lazy (`?`) or possessive (`+`) suffix to append.
        Returns:
            The simplest quantifier expressing the range.
        Raises:
            ValueError: If the minimum is negative.
        Examples:
            Common ranges collapse to their shorthand forms::

                >>> str(Quantifier.from_range(0, 1)), str(Quantifier.from_range(1, -1))
                ('?', '+')
                >>> str(Quantifier.from_range(2, 5)), str(Quantifier.from_range(3, 3))
                ('{2,5}', '{3}')
        """
        if r0 < 0:
            raise ValueError('Tried to create an invalid range.')
        elif r0 == r1:
            if r0 == 1 and not extra:
                return cls('')
            else:
                return cls(rf'{{{r0}}}', extra)
        elif r1 < 0:
            if r0 == 0:
                return cls(r'*', extra)
            elif r0 == 1:
                return cls(r'+', extra)
            else:
                return cls(rf'{{{r0},}}', extra)
        elif r0 == 0:
            if r1 == 1:
                return cls(r'?', extra)
            return cls(rf'{{,{r1}}}', extra)
        else:
            return cls(rf'{{{r0},{r1}}}', extra)

    @classmethod
    def __get_pydantic_core_schema__(cls, source: type, handler) -> pyds.CoreSchema:
        return pyds.no_info_before_validator_function(cls, pyds.is_instance_schema(cls))

    # -------------------
    # `-` Private Methods
    # -------------------

    # -------------------
    # `+` Primary Methods
    # -------------------
    def join(self, other: str | Self) -> Self | None:
        """Combine this quantifier with another into a single equivalent quantifier, if possible.

        If the two quantifiers cannot be simply combined, return `None` to indicate that nested
        groups are needed. Also available via the `&` operator.

        Args:
            other: The quantifier to combine with this one.
        Returns:
            The combined quantifier, or None if nesting is required.
        Examples:
            Multiply out compatible quantifiers; incompatible pairs return None::

                >>> Quantifier('{2,3}').join('{2,3}')
                Quantifier('{4,9}')
                >>> Quantifier('+').join('*')
                Quantifier('*')
                >>> Quantifier('{3,5}').join('?') is None
                True
        """
        cls = self.__class__
        if isinstance(other, str):
            other = cls(other)
        lhs, rhs = self, other
        if lhs.range == (1, 1) and not lhs.extra:
            lhs = cls('')
        if rhs.range == (1, 1) and not rhs.extra:
            rhs = cls('')

        # I. Handle trivial cases
        if not (lhs and rhs):
            return lhs or rhs
        elif rhs == '?':
            return lhs.as_optional()
        elif lhs == '?':
            return rhs.as_optional()

        # II. Infer the proper extra
        if lhs.extra and rhs.extra and lhs.extra != rhs.extra:
            return None
        extra = lhs.extra or rhs.extra

        # III. Main Cases
        if lhs.is_ranged:
            l0, l1 = lhs.range
            if rhs.is_ranged:
                # III.i. Ranged + Ranged
                r0, r1 = rhs.range
                new_min = l0 * r0
                new_max = -1 if l1 < 0 or r1 < 0 else l1 * r1
                return cls.from_range(new_min, new_max, extra)
            else:
                # III.ii. Ranged + Basic
                if rhs.base == '+':
                    return cls.from_range(l0, -1, extra)
                elif rhs.base == '*':
                    if l0 <= 1:
                        return cls(r'*', extra)
        elif rhs.is_ranged:
            # III.iii. Basic + Ranged
            r0, r1 = rhs.range
            if r0 == 0:
                return cls(r'*', extra)
            else:
                return lhs
        elif lhs.is_basic and rhs.is_basic:
            # III.iv. Basic + Basic
            if lhs == rhs:
                return lhs
            else:
                # (*, +) or (+, *) -- empty and ? were handled earlier
                return cls(r'*', extra)

        # VI. Indicate that the quantifiers need to be combined with nested groups
        return None

    def as_optional(self) -> Self | None:
        """Create a copy of this quantifier made optional, if possible (e.g. `+` -> `*`).

        Unlike `as_required()`, this function may not always succeed, as there are valid quantifiers
        that cannot be made optional without wrapping them (i.e. `(?:...)?`) -- namely, this applies
        to range quantifiers that start beyond 1 (e.g. `{3,5}`).

        Returns:
            The optional copy, or None if this quantifier cannot be made optional in place.
        Examples:
            Loosen a quantifier to permit zero occurrences::

                >>> Quantifier('+').as_optional()
                Quantifier('*')
                >>> Quantifier('{3,5}').as_optional() is None
                True
        """
        if self.is_optional:
            return self

        cls = self.__class__
        if not self:
            return cls('?')
        elif self.is_basic:
            if self.base == '+':
                return cls(r'*', self.extra)
        elif self.is_ranged:
            if self.range == (1, 1):
                return cls(r'?', self.extra)
            elif self.range[0] == 1:
                return cls.from_range(0, self.range[1], self.extra)

        # IV. Indicate that this quantifier can not trivially be made optional
        return None

    def as_required(self) -> Self:
        """Create a copy of this quantifier made NON-optional (e.g. `*` -> `+`).

        Examples:
            Force at least one occurrence::

                >>> Quantifier('*').as_required()
                Quantifier('+')
                >>> Quantifier('{0,4}').as_required()
                Quantifier('{1,4}')
        """
        if not self.is_optional:
            return self

        cls = self.__class__
        if self.is_basic:
            if self.base == '?':
                return cls('' if not self.is_possessive else '{1}+')
            elif self.base == '*':
                return cls('+' + self.extra)
        elif self.is_ranged:
            if self.range == (0, 1):
                return cls('')
            elif self.range[0] == 0:
                return cls.from_range(1, self.range[1], self.extra)

        raise RuntimeError(f'Unhandled optional quantifier: {self.data!r}')

    # ------------------
    # `*` Public Methods
    # ------------------
    # --------------
    # `*0` Overrides
    # --------------
    def __bool__(self) -> bool:
        return len(self.data) > 0

    def __str__(self) -> str:
        return self.data

    def __repr__(self) -> str:
        return f'Quantifier({self.data!r})'

    def __hash__(self) -> int:
        return hash(self.data)

    def __contains__(self, item: str) -> bool:
        return item == self.data

    def __len__(self) -> int:
        return len(self.data)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.data == other
        elif isinstance(other, Quantifier):
            return self.data == other.data
        else:
            return False

    def __lt__(self, other: object) -> bool:
        if isinstance(other, (str, Quantifier)):
            return self.data < (other.data if isinstance(other, Quantifier) else other)
        else:
            raise TypeError(f'Unsupported type for Quantifier comparison: {type(other)}')

    def startswith(self, prefix: str) -> bool:
        """Check if the quantifier starts with the given prefix."""
        return self.data.startswith(prefix)

    def endswith(self, suffix: str) -> bool:
        """Check if the quantifier ends with the given suffix."""
        return self.data.endswith(suffix)

    def __getitem__(self, key: slice | int) -> str:
        return self.data[key]

    def __and__(self, other: str | Self) -> Self | None:
        return self.join(other)

    def __iand__(self, other: str | Self) -> Self:
        joined = self.join(other)
        if joined is None:
            raise ValueError(
                f'Cannot combine quantifiers {self.data!r} and {other!r} without nested groups.'
            )
        return joined

    __rand__ = __and__

    # ---------------
    # `*1` Properties
    # ---------------
    @ft.cached_property
    def base(self) -> str:
        """The quantifier's text without its lazy/possessive `extra` suffix (e.g. `*+` -> `*`)."""
        if not self:
            return ''
        elif not (self.is_lazy or self.is_possessive):
            return self.data
        elif self.is_ranged:
            return self.data.split('}', 1)[0] + '}'
        else:
            return self.data[0]

    @ft.cached_property
    def extra(self) -> Literal['', '?', '+']:
        """The "extra" part of the quantifier (i.e. the lazy `?` or possessive `+`)."""
        if self.is_lazy:
            return '?'
        elif self.is_possessive:
            return '+'
        return ''

    @ft.cached_property
    def is_simple(self) -> bool:
        """Whether the quantifier is "simple" (i.e. empty or `?`)."""
        return self.data in ('', '?')

    @ft.cached_property
    def is_basic(self) -> bool:
        """Whether the quantifier is "basic" (i.e. empty, `?`, `*`, or `+`)."""
        return not self.data or self.data[0] in '?*+'

    @ft.cached_property
    def is_ranged(self) -> bool:
        """Whether the quantifier is a range (i.e. starts with `{`)."""
        return self.data.startswith('{')

    @ft.cached_property
    def is_optional(self) -> bool:
        """Whether the quantifier allows zero occurrences."""
        return bool(self.data) and (self.base in '*?' or self.range[0] == 0)

    @ft.cached_property
    def is_lazy(self) -> bool:
        """Whether the quantifier is lazy (i.e. ends with extra `?`)."""
        return len(self.data) > 1 and self.data.endswith('?')

    @ft.cached_property
    def is_possessive(self) -> bool:
        """Whether the quantifier is possessive (i.e. ends with extra `+`)."""
        return len(self.data) > 1 and self.data.endswith('+')

    @ft.cached_property
    def range(self) -> tuple[int, int]:
        """The (min, max) occurrences of a ranged quantifier, with -1 marking "not applicable".

        Non-ranged quantifiers yield `(-1, -1)`; an open-ended range like `{2,}` yields `(2, -1)`.
        """
        if not self.is_ranged:
            return (-1, -1)
        content = self.base[1:-1]
        if ',' in content:
            min_str, max_str = content.split(',', 1)
            min_val = int(min_str) if min_str else 0
            max_val = int(max_str) if max_str else -1
        else:
            min_val = max_val = int(content)
        return (min_val, max_val)

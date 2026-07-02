############
### HEAD ###
############
# --------
# Standard
# --------
from __future__ import annotations
from typing import ClassVar, overload
from typing import Self
import functools as ft
import itertools as it
from collections import deque
from collections.abc import Iterable

# --------
# External
# --------
import pydantic as pyd
import regex as re
import more_itertools as mi

# --------
# Internal
# --------
from myBasis import ut
from .enums import IdxStyle
from .IdxSpec import IdxSpec


############
### BODY ###
############
@ft.total_ordering
class Idx(pyd.BaseModel):
    """A parsed, round-trippable hierarchical index string.

    An `Idx` holds both the original `root` string (e.g. `"1.A.ii."`) and
    its decomposed `parts` list (e.g. `[(NUMBER, 1), (ALPHAU, 1), (ROMANL, 1)]`),
    kept in sync by Pydantic validators.  The `spec` field records inferred
    formatting options (`dotted`, `marked`) discovered during parsing.

    Parsing (`read`) and serialisation (`write`) are inverses of each other:
    `Idx(root=text).write() == text` for any valid index string.

    **Arithmetic operators**:

    - `idx + other` — concatenate two index strings (append `other`'s root to `self.root`).
    - `idx - n` — remove the last *n* depth levels (truncate).
    """

    _DEBUG: ClassVar[bool] = False
    RGXS: ClassVar[dict[str, re.Pattern[str]]] = ut.rgx_dict(  # type: ignore
        untagged_flex=IdxSpec(tagged=False).rgx,
        tagged_flex=IdxSpec(tagged=True).rgx,
    )

    root: str = ""
    parts: list[tuple[IdxStyle, int]] = []
    spec: IdxSpec = IdxSpec()

    # -------------------
    # `.` Initial Methods
    # -------------------
    def __init__(self, root: str = "", **kwargs) -> None:
        """Initializes the Idx object with the given root string and optional parts and spec."""
        super().__init__(root=root, **kwargs)

    @pyd.model_validator(mode="after")
    def read(self) -> Self:
        """Reads the root string and populates the parts, dotted, and marked attributes."""
        self.root = self.root.strip()
        if not self.root:
            if self.parts:
                self.root = self.write()
            return self

        _rem = self.root
        if _rem[-1] in ".):":
            self.spec.marked = _rem[-1]  # type: ignore
            _rem = _rem[:-1]

        if "." in _rem:
            self.spec.dotted = True
            _parts = _rem.split(".")
            if _max := self.spec.max_depth:
                assert len(_parts) <= _max, f"{self.root} has > {_max} parts."
            assert all(_parts), f"Invalid index with empty part: {self.root}"

            try:
                self.parts = list(map(self._read_dotted_part, _parts))
            except (AssertionError, ValueError):
                self.parts = []
                if self._DEBUG:
                    raise
        else:
            self.spec.dotted = False
            try:
                _max = self.spec.max_depth
                while _rem and (not _max or len(self.parts) <= _max):
                    style, place, _rem = self._read_part(_rem)
                    self.parts.append((style, place))
                if _max and len(self.parts) > _max:
                    raise ValueError(f"{self.root} has > {_max} parts.")
            except (AssertionError, ValueError):
                self.parts = []
                if self._DEBUG:
                    raise
        return self

    @pyd.model_serializer
    def write(self) -> str:
        """Writes the root string based on the parts, dotted, and marked attributes."""
        if not self.parts:
            return ""

        sep = "." if self.spec.dotted is True else ""
        ret = sep.join(it.starmap(self._write_part, self.parts)) + self.spec.mark
        return ret

    @classmethod
    def attempt_to_read(cls, root: str) -> Self | None:
        """Attempts to read the given root string as an index, returning None if it is invalid."""
        try:
            inst = cls(root=root)
        except (AssertionError, ValueError):
            return None
        return inst if inst.parts else None

    @classmethod
    def from_parts(cls, spec: IdxSpec, *parts: int) -> Self:
        """Creates an Idx object from the given parts and spec."""
        return cls(parts=list(zip(spec.style_iter(end=len(parts)), parts)), spec=spec)

    # -------------------
    # `-` Private Methods
    # -------------------
    @staticmethod
    def alpha_to_int(text: str) -> int:
        """Converts a single alphabetical character to an integer."""
        return ord(text[0].upper()) - ord("A") + 1

    @staticmethod
    def int_to_alpha(num: int, upper: bool = False) -> str:
        """Converts an integer to a single alphabetical character."""
        assert num < 26, "int_to_alpha only supports values up to 26."
        return chr(ord("A" if upper else "a") + num)

    # -------------------
    # `+` Primary Methods
    # -------------------
    @classmethod
    def _read_dotted_part(cls, text: str) -> tuple[IdxStyle, int]:
        """Parse a single part of a dot-separated index string.

        Tries each style in order — numeric, symbol, roman, alpha — and returns
        the first match.  Roman is tested before alpha because many roman-numeral
        strings (`i`, `v`, `x`, `c`, `m`) are also valid alpha characters.

        Args:
            text: A single fragment between dots, e.g. `"A"`, `"iii"`, `"42"`.

        Returns:
            A `(style, place)` pair where *place* is the 0-based integer position.

        Raises:
            ValueError: If *text* cannot be classified as any known style.
        """
        assert text, "Cannot read empty idx part."
        if text.isdigit():
            return IdxStyle.NUMBER, int(text)

        elif (val := IdxSpec.SYMBOLS.find(text)) > -1:
            return IdxStyle.SYMBOL, val

        elif IdxSpec.RGXS["roman"].fullmatch(text):
            # Roman Numerals can only be used with dot separators or when total depth is 0
            style = IdxStyle.ROMANU if text.isupper() else IdxStyle.ROMANL
            return style, ut.roman_to_decimal(text)

        elif text.isalpha():
            # NOTE: alpha must be matched after roman numerals, for obvious reasons
            style = IdxStyle.ALPHAU if text.isupper() else IdxStyle.ALPHAL
            val = 0
            for place, char in enumerate(reversed(text)):
                val += cls.alpha_to_int(char) * (26**place)
            return style, val

        raise ValueError(f"Cannot classify idx: {text}")

    @classmethod
    def _read_part(cls, text: str) -> tuple[IdxStyle, int, str]:
        """Reads a single part of an index string.

        Returns:
            3-tuple with `(style, position, remaining text)`.
        """
        assert text, "Cannot read empty idx part."
        if text[0].isdigit():
            return IdxStyle.NUMBER, int(text[0]), text[1:]

        elif text[0] in IdxSpec.SYMBOLS:
            assert len(text) == 1, "Symbol idx must be a single character."
            return IdxStyle.SYMBOL, IdxSpec.SYMBOLS.index(text[0]), text[1:]

        elif IdxSpec.RGXS["roman"].fullmatch(text):
            # Roman Numerals can only be used with dot separators or when total depth is 0
            style = IdxStyle.ROMANU if text.isupper() else IdxStyle.ROMANL
            return style, ut.roman_to_decimal(text), ""

        elif text[0].isalpha():
            # NOTE: alpha must be matched after roman numerals, for obvious reasons
            style = IdxStyle.ALPHAU if text[0].isupper() else IdxStyle.ALPHAL
            return (style, cls.alpha_to_int(text[0]), text[1:])

        raise ValueError(f"Cannot classify idx: {text}")

    @classmethod
    def _write_part(cls, style: IdxStyle, place: int) -> str:
        """Convert a `(style, place)` pair back to its string representation.

        Args:
            style: The notation style to render with.
            place: 0-based integer position within the style's sequence.

        Returns:
            The rendered string fragment, e.g. `"3"`, `"C"`, `"iv"`, `"+"`.

        Raises:
            AssertionError: If *place* is negative or out of range for the style.
            ValueError: If *style* is unrecognised.
        """
        assert place >= 0, f"Cannot write negative idx place: {place}"
        if style == IdxStyle.NUMBER:
            return str(place)

        elif style == IdxStyle.SYMBOL:
            assert place < len(IdxSpec.SYMBOLS), f"Symbol idx {place} is out of bounds."
            return IdxSpec.SYMBOLS[place]

        elif style & IdxStyle.ROMAN:
            fn = str.lower if style == IdxStyle.ROMANL else str.upper
            return fn(ut.decimal_to_roman(place))

        elif style & IdxStyle.ALPHA:
            is_upper = style == IdxStyle.ALPHAU
            if place < 26:
                return cls.int_to_alpha(place, upper=is_upper)
            else:
                # For places >= 26, we use this as a base-26 (25?) form
                chars = deque()
                while place > 0:
                    chars.appendleft(cls.int_to_alpha(place % 26, upper=is_upper))
                    place //= 26
                return "".join(chars)

        else:
            raise ValueError(f"Cannot write idx for unrecognized style: {style}")

    # ------------------
    # `*` Public Methods
    # ------------------
    def __eq__(self, other: object):
        if other is None:
            return False
        elif isinstance(other, str):
            return self.root == other
        elif isinstance(other, Idx):
            return self.root == other.root
        else:
            raise TypeError(f"Cannot compare Idx to {type(other)}")

    def __lt__(self, other: Idx | str):
        """Orders two indices.

        This is *similar* to a straight lexigraphical ordering, but with one caveat: abstract files
        are marked with an "a" or "b" at the end of the index, and they precede (are lower than)
        their concrete siblings.

        E.g. a < b < 0 < 0a < 0b < 00 < 1 < 1a < ...
        """
        if isinstance(other, str):
            _ret = Idx.attempt_to_read(other)
            assert _ret is not None, f"Cannot compare to invalid index string: {other}"
            other = _ret

        if self == other:
            return False

        return self.root < other.root

    def __repr__(self):
        return f"`{self.root}`"

    def __str__(self):
        return self.root

    def __hash__(self):
        return hash(self.root)

    def __len__(self):
        return len(self.parts)

    def __bool__(self):
        return len(self.parts) > 0

    def __add__(self, other: Idx | str) -> Self:
        """Concatenate two index strings, appending *other*'s root to this one.

        Args:
            other: An `Idx` instance or a raw index string.

        Returns:
            A new `Idx` whose `root` is `self.root + other.root`.

        Raises:
            TypeError: If *other* is neither an `Idx` nor a `str`.
        """
        # if isinstance(other, str):
        #     _ret = Idx.attempt_to_read(other)
        #     assert _ret is not None, f'Cannot add invalid index string: {other}'
        if isinstance(other, str):
            return self.__class__(root=self.root + other)
        elif isinstance(other, Idx):
            return self.__class__(root=self.root + other.root)
        else:
            raise TypeError(f"Cannot add Idx to {type(other)}")

    def __sub__(self, num: int) -> Self:
        """Remove the last *num* depth levels from this index.

        `idx - 0` returns `self`; `idx - len(idx)` (or more) returns an empty `Idx`.

        Args:
            num: Number of trailing depth levels to drop.

        Returns:
            A new `Idx` with *num* fewer parts.
        """
        if num == 0:
            return self
        elif num >= len(self):
            return self.__class__()
        else:
            assert 0 < num < len(self), (
                f"Invalid subtraction length for {self.root}: {num}"
            )
            return self.__class__(root=self.root[:-num])

    def matches(self, other: Idx | str | None) -> bool:
        """Lenient equality that considers two indices equal if their place sequences match.

        Unlike `==` (which compares raw `root` strings), this method compares the
        underlying `(style, place)` pairs, so `Idx("1.A")` and `Idx("1.a")` are
        considered matching even though their roots differ.

        Args:
            other: An `Idx`, a raw index string, or `None`.

        Returns:
            `True` if *other* parses successfully and has the same place sequence.
        """
        if not other:
            return False
        elif isinstance(other, str):
            other = Idx(root=other)
        return self == other or self.places == other.places

    def is_ancestor_of(self, other: Idx | str | None) -> bool:
        """Return `True` if *other* is a strict descendant of this index.

        `self` is an ancestor of `other` when `self.parts` is a proper prefix
        of `other.parts` — i.e. `other` is deeper and starts with the same
        sequence of (style, place) pairs.

        Args:
            other: An `Idx`, a raw index string, or `None`.
        """
        other = Idx.attempt_to_read(other) if isinstance(other, str) else other
        if not other:
            return False
        return len(self) < len(other) and other.parts[: len(self)] == self.parts

    # ----------
    # Properties
    # ----------
    @property
    def places(self) -> list[int]:
        """The series of places (i.e. siblings indices) that uniquely identify this idx."""
        return [place for _, place in self.parts]

    # ---------------
    # Tree Properties
    # ---------------
    @ft.cached_property
    def depth(self) -> int:
        """The depth of this index."""
        return len(self.parts)

    @property
    def values(self) -> list[int]:
        """The values of each part of this index."""
        return [val for _, val in self.parts]

    # -------
    # METHODS
    # -------
    @classmethod
    def build(cls, spec: IdxSpec, *values: int | Iterable[int]) -> Self:
        """Build an index string with the given values (depth is inferred from number of values)."""
        acc = list(mi.collapse(values))
        styles = spec.style_iter(end=len(acc))
        return cls(parts=list(zip(styles, acc)), spec=spec)

    @overload
    def build_relative(self, *, abs_depth: int, abs_place: int | list[int]) -> Self: ...

    @overload
    def build_relative(self, *, abs_depth: int, rel_place: int | list[int]) -> Self: ...

    @overload
    def build_relative(self, *, rel_depth: int, abs_place: int | list[int]) -> Self: ...

    @overload
    def build_relative(self, *, rel_depth: int, rel_place: int | list[int]) -> Self: ...

    @overload
    def build_relative(self, *, abs_place: int) -> Self: ...

    @overload
    def build_relative(self, *, rel_place: int) -> Self: ...

    def build_relative(
        self,
        *,
        abs_depth: int = -1,
        rel_depth: int = 0,
        abs_place: int | list[int] = -1,
        rel_place: int | list[int] = 0,
    ) -> Self:
        """Calculate a new idx string by placing or shifting the given idx string.

        Caller should specify one of place or shift (AKA absolute or relative), but never both.

        Args:
            abs_depth: The absolute depth to place the new idx at.
            rel_depth: The relative change in depth to shift the new idx by.
            abs_place: The absolute value(s) to place at each part of the new idx.
            rel_place: The relative change in value(s) to shift each part of the new idx by.
        Returns:
            The new idx object
        """
        depth0 = len(self.parts)
        parts = self.parts.copy()

        # I. Set the number of depths
        if abs_depth >= 0:
            # I.i. Set depth
            if abs_depth < depth0:
                parts = parts[:abs_depth]
            elif abs_depth > depth0:
                parts.extend((_s, 0) for _s in self.spec.style_iter(depth0, abs_depth))
        elif rel_depth != 0:
            # I.ii. Shift depth
            if rel_depth > 0:
                parts.extend(
                    (_s, 0) for _s in self.spec.style_iter(depth0, depth0 + rel_depth)
                )
            else:
                parts = parts[:-rel_depth]

        depth = len(parts)
        if depth == 0:
            raise IndexError(f"Vertical change out of bounds: {depth0} + {rel_depth}")

        # II. Set place(s) within depth(s)
        if isinstance(abs_place, list):
            # II.i. Set all places
            abs_place = list(abs_place)
            assert len(abs_place) == depth, (
                f"Given {len(abs_place)} new places for {depth} parts."
            )
            parts = [(style, pos) for (style, _), pos in zip(parts, abs_place)]
        elif abs_place >= 0:
            # II.ii. Set last place
            parts[-1] = parts[-1][0], abs_place
        elif isinstance(rel_place, list):
            # II.iii. Shift all places
            rel_place = list(rel_place)
            assert len(rel_place) == depth, (
                f"Given {len(rel_place)} place shifts for {depth} parts."
            )
            parts = [
                (style, cur + shift) for (style, cur), shift in zip(parts, rel_place)
            ]
        elif rel_place != 0:
            # II.iv. Shift last place
            style, last = parts[-1]
            parts[-1] = style, last + rel_place

        if any(pos < 0 for _, pos in parts):
            raise IndexError(f"Horizontal change(s) out of bounds: {parts=}")

        return self.model_copy(update=dict(parts=parts))

############
### HEAD ###
############
# STANDARD
from __future__ import annotations
from typing import Union
from typing_extensions import Self
import functools as ft

# EXTERNAL
import sublime as sb
import pydantic as pyd
import more_itertools as mi

# INTERNAL
from .utils import ut

Region = sb.Region


############
### DATA ###
############
@ft.total_ordering
class Comment(pyd.BaseModel):
    """Represents source code comment consisting of one or more lines of text."""

    # ---- Dependent ----
    #: The raw positions of each line included in this comment (when it was created, at least).
    #: Callers are responsible for shifting these values whenever the file changes.
    lines: list[ut.RegionField] = []

    #: The 0-indexed row of the first line of the comment.
    row: int = 0
    #: The 0-indexed column where the *content* of the comment starts (after punctuation).
    col: int = 1

    # ---- Independent ----
    #: The content of each line of content without initial whitespace & punctuation
    texts: list[str] = []

    #: The character(s) recognized by the containing syntax as line comment markers
    punct: str = '#'

    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyd.model_validator(mode='after')
    def validate_comment(self) -> Self:
        """Ensures that the comment data is consistent and valid."""
        if (h := self.height) != len(self.texts):
            raise ValueError(
                f'Number of lines ({h}) must match number of texts ({len(self.texts)}).'
            )
        return self

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
    def __str__(self) -> str:
        indent = f'{self.punct:>{self.col}}'  # col is 0-based, thank god
        return '\n'.join(indent + text for text in self.texts)

    def __bool__(self) -> bool:
        return len(self.lines) > 0

    def __hash__(self) -> int:
        return hash(tuple(line.to_tuple() for line in self.lines))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Comment):
            return self.lines == other.lines
        else:
            raise NotImplementedError(f'Cannot compare Comment with {type(other)}.')

    def __lt__(self, other: object) -> bool:
        if isinstance(other, Comment):
            return (self.row, self.col) < (other.row, other.col)
        elif isinstance(other, int):
            return self.row < other
        else:
            raise NotImplementedError(f'Cannot compare Comment with {type(other)}.')

    def __contains__(self, other: object) -> bool:
        if isinstance(other, Comment):
            other = other.region
        elif isinstance(other, tuple):
            assert len(other) == 2, (
                f'Expected a 2-tuple of (start, end) positions, got {len(other)}-tuple.'
            )
            assert isinstance(other[0], int) and isinstance(other[1], int)
            other = sb.Region(other[0], other[1])
        elif not isinstance(other, int):
            raise NotImplementedError(f'Cannot check if Comment contains {type(other)}.')
        return other in self.region

    def __add__(self, other: object) -> Comment:
        if not isinstance(other, Comment):
            raise NotImplementedError(f'Cannot add Comment with {type(other)}.')
        elif self.follows(other):
            return other + self
        elif not other.follows(self):
            raise ValueError('Can only add Comments that follow each other.')
        else:
            return Comment(
                lines=self.lines + other.lines,
                texts=self.texts + other.texts,
                row=self.row,
                col=self.col,
            )

    def __getitem__(self, key: Union[int, slice]) -> Comment:
        cls = type(self)
        if isinstance(key, int):
            return cls(
                lines=self.lines[key : key + 1],
                texts=self.texts[key : key + 1],
                row=self.row + key,
                col=self.col,
                punct=self.punct,
            )
        else:
            return cls(
                lines=self.lines[key],
                texts=self.texts[key],
                row=self.row + (key.start or 0),
                col=self.col,
                punct=self.punct,
            )

    # ---------------
    # `*1` Properties
    # ---------------
    @property
    def line(self) -> Region:
        """The position of the first line of the comment."""
        return mi.first(self.lines, Region(0, 0))

    @property
    def start(self) -> int:
        """The start position (in characters) of the comment."""
        return self.line.begin()

    @property
    def end(self) -> int:
        """The end position (in characters) of the comment."""
        return mi.last(self.lines, Region(0, 0)).end()

    @property
    def region(self) -> Region:
        """The Region object representing the entire comment."""
        return Region(self.start, self.end)

    @property
    def height(self) -> int:
        """The number of lines in the comment."""
        return len(self.lines)

    @property
    def size(self) -> int:
        """The size of the comment in characters, including newlines and indentation."""
        return self.end - self.start

    @property
    def bare_content(self) -> str:
        """The text content of the comment's lines, sans-punctuation."""
        return '\n'.join(self.texts)

    @property
    def bare_size(self) -> int:
        """The size of the comment in characters, including only post-punctuation content."""
        return sum(map(len, self.texts)) + (self.height - 1)

    @property
    def rowspan(self) -> tuple[int, int]:
        """The Region object representing the entire comment."""
        return self.row, self.row + self.height

    @property
    def indent(self) -> int:
        """The number of whitespace characters before this comment's punctuation."""
        return max(0, self.col - len(self.punct))

    def contains_row(self, row: int) -> bool:
        """Whether the given row number is within the vertical span of this comment."""
        start, end = self.rowspan
        return start <= row < end

    # ------------
    # `*2` Methods
    # ------------
    def follows(self, other: Comment) -> bool:
        """Returns True if this comment immediately follows the other comment."""
        return self.row == other.row + other.height and self.col == other.col

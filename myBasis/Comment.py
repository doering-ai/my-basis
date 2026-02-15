############
### HEAD ###
############
# STANDARD
from __future__ import annotations
from typing import Union, TYPE_CHECKING
from typing_extensions import Self
import functools as ft

# EXTERNAL
import sublime as sb
import pydantic as pyd

# INTERNAL
if TYPE_CHECKING:
    from .utils import Utils


############
### DATA ###
############
@ft.total_ordering
class Comment(pyd.BaseModel):
    """Represents source code comment consisting of one or more lines of text."""

    # ---- Dependent ----
    #: The raw positions of each line included in this comment (when it was created, at least).
    #: Callers are responsible for shifting these values whenever the file changes.
    lines: list[Utils.RegionField] = []

    #: The row and column where the first line of the comment starts.
    #: Callers are responsible for shifting these values whenever the file changes.
    row: int = 1

    #: The column where the first line of the comment starts.
    #: Callers are responsible for shifting this value whenever the file changes.
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
    def __bool__(self) -> bool:
        return len(self.lines) > 0

    def __lt__(self, other: object) -> bool:
        if isinstance(other, Comment):
            return (self.row, self.col) < (other.row, other.col)
        elif isinstance(other, int):
            return self.row < other
        else:
            raise NotImplementedError(f'Cannot compare Comment with {type(other)}.')

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Comment):
            return self.lines == other.lines
        else:
            raise NotImplementedError(f'Cannot compare Comment with {type(other)}.')

    def __str__(self) -> str:
        indent = ' ' * (self.col - 1)
        return '\n'.join(
            indent + (text if text.startswith(self.punct) else f'{self.punct} {text}')
            for text in self.texts
        )

    def __contains__(self, other: object) -> bool:
        r0: int
        r1: int
        if isinstance(other, Comment):
            r0, r1 = other.row, other.row + other.height
        elif isinstance(other, int):
            r0, r1 = other, other + 1
        elif isinstance(other, tuple) and len(other) == 2:
            assert isinstance(other[0], int) and isinstance(other[1], int)
            r0, r1 = other[0], other[1]
        else:
            raise NotImplementedError(f'Cannot check containment of Comment with {type(other)}.')

        assert r0 < r1, f'Invalid region to check containment ({r0}, {r1}).'
        return self.row <= r0 and self.row + self.height >= r1

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
    def start(self) -> int:
        """The start position (in characters) of the comment."""
        return self.lines[0].begin() if self else 0

    @property
    def end(self) -> int:
        """The end position (in characters) of the comment."""
        return self.lines[-1].end() if self else 0

    @property
    def region(self) -> sb.Region:
        """The Region object representing the entire comment."""
        return sb.Region(self.start, self.end) if self else sb.Region(0, 0)

    @property
    def height(self) -> int:
        """The number of lines in the comment."""
        return len(self.lines)

    @property
    def size(self) -> int:
        """The size of the comment in characters, including newlines and indentation."""
        return self.end - self.start

    # ------------
    # `*2` Methods
    # ------------
    def follows(self, other: Comment) -> bool:
        """Returns True if this comment immediately follows the other comment."""
        return self.row == other.row + other.height and self.col == other.col

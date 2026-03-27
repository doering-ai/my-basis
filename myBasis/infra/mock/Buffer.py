"""In-memory text buffer backing the mock sublime.View.

Pure Python, no ST dependency. Implements the subset of the ST buffer API
that is exercised by ViewTestCase and direct view.insert/replace/substr calls.
"""

############
### HEAD ###
############
### STANDARD
from __future__ import annotations

### EXTERNAL

### INTERNAL


############
### BODY ###
############
class Buffer:
    """A simple mutable string buffer with row/col and region arithmetic."""

    # -------------------
    # `.` Initial Methods
    # -------------------
    def __init__(self, text: str = '') -> None:
        """Initialize the buffer."""
        self._text = text

    # -------------------
    # `-` Private Methods
    # -------------------
    def _clamp(self, point: int) -> int:
        return max(0, min(point, len(self._text)))

    # -------------------
    # `+` Primary Methods
    # -------------------
    def text_point(self, row: int, col: int) -> int:
        """Convert a (row, col) pair to a character offset.

        Both coordinates are 0-based. Col is clamped to the line length.
        """
        if row < 0:
            return 0
        lines = self._text.split('\n')
        if row >= len(lines):
            return len(self._text)
        offset = sum(len(line) + 1 for line in lines[:row])
        return offset + min(col, len(lines[row]))

    def rowcol(self, point: int) -> tuple:
        """Convert a character offset to a (row, col) pair (both 0-based)."""
        point = max(0, min(point, len(self._text)))
        before = self._text[:point]
        row = before.count('\n')
        last_nl = before.rfind('\n')
        col = point - last_nl - 1
        return row, col

    def line_extent(self, point: int) -> tuple:
        """Return (start, end) of the line that contains *point*.

        *start* is inclusive, *end* is exclusive (points at the newline or EOF).
        """
        point = self._clamp(point)
        start = self._text.rfind('\n', 0, point) + 1  # 0 when no prior newline
        end_idx = self._text.find('\n', point)
        end = end_idx if end_idx != -1 else len(self._text)
        return start, end

    # ------------------
    # `*` Public Methods
    # ------------------
    @property
    def text(self) -> str:
        """Get the entire buffer text."""
        return self._text

    def __str__(self) -> str:
        return self._text

    def size(self) -> int:
        """Return the number of characters in the buffer."""
        return len(self._text)

    def insert(self, point: int, text: str) -> int:
        """Insert *text* at *point*, return number of characters inserted."""
        point = self._clamp(point)
        self._text = self._text[:point] + text + self._text[point:]
        return len(text)

    def replace(self, a: int, b: int, text: str) -> None:
        """Replace the half-open range [a, b) with *text*."""
        n = len(self._text)
        a = max(0, min(a, n))
        b = max(a, min(b, n))
        self._text = self._text[:a] + text + self._text[b:]

    def substr(self, a: int, b: int) -> str:
        """Return the substring in the half-open range [a, b)."""
        return self._text[a:b]

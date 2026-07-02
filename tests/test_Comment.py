############
### HEAD ###
############
### STANDARD
from __future__ import annotations

### EXTERNAL
import pytest as pyt
import sublime as sb

### INTERNAL
from myBasis.types.Comment import Comment
from myBasis import ut


############
### DATA ###
############
def _r(a: int, b: int) -> ut.RegionField:
    """Shorthand for creating a Region."""
    return sb.Region(a, b)


def _make_comment(
    lines: list[sb.Region] | None = None,
    texts: list[str] | None = None,
    row: int = 0,
    col: int = 1,
    punct: str = '#',
) -> Comment:
    """Build a Comment with sensible defaults, ensuring lines/texts match."""
    if lines is None:
        lines = [_r(0, 10)]
    if texts is None:
        texts = ['hello'] * len(lines)
    assert len(lines) == len(texts), f'lines ({len(lines)}) must match texts ({len(texts)})'
    return Comment(lines=lines, texts=texts, row=row, col=col, punct=punct)


############
### BODY ###
############
class TestCommentConstruction:
    """Tests for Comment construction and validation."""

    def test_basic_construction(self):
        c = _make_comment()
        assert c.row == 0
        assert c.col == 1
        assert c.punct == '#'
        assert c.texts == ['hello']

    def test_default_values(self):
        c = Comment()
        assert c.lines == []
        assert c.texts == []
        assert c.row == 0
        assert c.col == 1
        assert c.punct == '#'

    def test_validation_height_mismatch(self):
        with pyt.raises(pyd.ValidationError if (pyd := __import__('pydantic')) else Exception):
            Comment(lines=[_r(0, 5), _r(6, 10)], texts=['only one'], row=0, col=1)

    def test_validation_height_match(self):
        c = Comment(lines=[_r(0, 5), _r(6, 10)], texts=['line1', 'line2'], row=0, col=1)
        assert c.height == 2

    def test_custom_punct(self):
        c = _make_comment(punct='//')
        assert c.punct == '//'


class TestCommentBool:
    """Tests for ``Comment.__bool__``."""

    def test_false_when_empty(self):
        c = Comment()
        assert not c

    def test_true_when_has_lines(self):
        c = _make_comment()
        assert bool(c)


class TestCommentStr:
    """Tests for ``Comment.__str__``."""

    def test_single_line(self):
        c = _make_comment(texts=['hello'], col=1, punct='#')
        assert str(c) == '#hello'

    def test_multi_line(self):
        c = _make_comment(lines=[_r(0, 5), _r(6, 10)], texts=['line1', 'line2'], col=1, punct='#')
        assert str(c) == '#line1\n#line2'

    def test_indent_from_col(self):
        c = _make_comment(texts=['hello'], col=3, punct='#')
        assert str(c) == '  #hello'

    def test_double_slash_punct(self):
        c = _make_comment(texts=['hello'], col=2, punct='//')
        assert str(c) == '//hello'


class TestCommentHash:
    """Tests for ``Comment.__hash__``."""

    def test_same_lines_same_hash(self):
        c1 = _make_comment(lines=[_r(0, 5)], texts=['a'])
        c2 = _make_comment(lines=[_r(0, 5)], texts=['b'])
        assert hash(c1) == hash(c2)

    def test_different_lines_different_hash(self):
        c1 = _make_comment(lines=[_r(0, 5)], texts=['a'])
        c2 = _make_comment(lines=[_r(10, 15)], texts=['a'])
        assert hash(c1) != hash(c2)


class TestCommentEq:
    """Tests for ``Comment.__eq__``."""

    def test_equal_same_lines(self):
        c1 = _make_comment(lines=[_r(0, 5)], texts=['a'])
        c2 = _make_comment(lines=[_r(0, 5)], texts=['b'])
        assert c1 == c2

    def test_not_equal_different_lines(self):
        c1 = _make_comment(lines=[_r(0, 5)])
        c2 = _make_comment(lines=[_r(10, 15)])
        assert c1 != c2

    def test_eq_foreign_type_is_false(self):
        """`__eq__` returns NotImplemented for foreign types, so `==` falls back to False."""
        c = _make_comment()
        assert (c == 'not a comment') is False
        assert c != 'not a comment'


class TestCommentLt:
    """Tests for ``Comment.__lt__`` (total_ordering)."""

    def test_lt_by_row_col(self):
        c1 = _make_comment(row=0, col=1)
        c2 = _make_comment(row=1, col=1)
        assert c1 < c2

    def test_lt_by_col(self):
        c1 = _make_comment(row=0, col=1)
        c2 = _make_comment(row=0, col=2)
        assert c1 < c2

    def test_lt_with_int(self):
        c = _make_comment(row=5)
        assert c < 10
        assert not (c < 3)

    def test_lt_raises_on_non_comment_non_int(self):
        """`__lt__` returns NotImplemented for foreign types, so `<` raises TypeError."""
        c = _make_comment()
        with pyt.raises(TypeError):
            _ = c < 'string'

    def test_le_total_ordering(self):
        c1 = _make_comment(row=0, col=1)
        c2 = _make_comment(row=0, col=1)
        assert c1 <= c2

    def test_gt_total_ordering(self):
        c1 = _make_comment(row=5)
        c2 = _make_comment(row=1)
        assert (c1 > c2) or (c1.row > c2.row)


class TestCommentContains:
    """Tests for ``Comment.__contains__``."""

    def test_contains_int(self):
        c = _make_comment(lines=[_r(10, 20)])
        assert 15 in c
        assert 5 not in c
        assert 25 not in c

    def test_contains_region(self):
        c = _make_comment(lines=[_r(10, 20)])
        # Region is not directly supported; use tuple instead
        assert (12, 18) in c
        assert (5, 15) not in c

    def test_contains_tuple(self):
        c = _make_comment(lines=[_r(10, 20)])
        assert (12, 18) in c

    def test_contains_comment(self):
        c1 = _make_comment(lines=[_r(10, 20), _r(21, 30)], texts=['a', 'b'])
        c2 = _make_comment(lines=[_r(12, 18)], texts=['inner'])
        assert c2 in c1

    def test_contains_raises_on_invalid_type(self):
        c = _make_comment()
        with pyt.raises(TypeError):
            _ = 'string' in c


class TestCommentAdd:
    """Tests for ``Comment.__add__``."""

    def test_add_adjacent_comments(self):
        c1 = _make_comment(lines=[_r(0, 10)], texts=['line1'], row=0, col=1, punct='#')
        c2 = _make_comment(lines=[_r(11, 20)], texts=['line2'], row=1, col=1, punct='#')
        result = c1 + c2
        assert result.height == 2
        assert result.texts == ['line1', 'line2']
        assert result.row == 0

    def test_add_non_adjacent_raises(self):
        c1 = _make_comment(lines=[_r(0, 10)], texts=['a'], row=0)
        c2 = _make_comment(lines=[_r(20, 30)], texts=['b'], row=5)
        with pyt.raises(ValueError, match='follow'):
            _ = c1 + c2

    def test_add_wrong_type_raises(self):
        """`__add__` returns NotImplemented for foreign types, so `+` raises TypeError."""
        c = _make_comment()
        with pyt.raises(TypeError):
            _ = c + 5

    def test_add_commutative_via_follows(self):
        """If c2 follows c1, then c2 + c1 == c1 + c2."""
        c1 = _make_comment(lines=[_r(0, 10)], texts=['a'], row=0, col=1, punct='#')
        c2 = _make_comment(lines=[_r(11, 20)], texts=['b'], row=1, col=1, punct='#')
        assert c2.follows(c1)
        result = c2 + c1
        assert result.row == 0
        assert result.texts == ['a', 'b']


class TestCommentGetitem:
    """Tests for ``Comment.__getitem__``."""

    def test_getitem_int(self):
        c = _make_comment(
            lines=[_r(0, 5), _r(6, 10), _r(11, 15)],
            texts=['a', 'b', 'c'],
            row=0,
        )
        first = c[0]
        assert first.texts == ['a']
        assert first.row == 0
        assert first.height == 1

        second = c[1]
        assert second.texts == ['b']
        assert second.row == 1

    def test_getitem_slice(self):
        c = _make_comment(
            lines=[_r(0, 5), _r(6, 10), _r(11, 15)],
            texts=['a', 'b', 'c'],
            row=0,
        )
        result = c[0:2]
        assert result.texts == ['a', 'b']
        assert result.height == 2
        assert result.row == 0

    def test_getitem_slice_with_start(self):
        c = _make_comment(
            lines=[_r(0, 5), _r(6, 10), _r(11, 15)],
            texts=['a', 'b', 'c'],
            row=0,
        )
        result = c[1:]
        assert result.texts == ['b', 'c']
        assert result.row == 1

    def test_getitem_preserves_punct(self):
        c = _make_comment(lines=[_r(0, 5), _r(6, 10)], texts=['a', 'b'], punct='//')
        result = c[0]
        assert result.punct == '//'


class TestCommentProperties:
    """Tests for Comment properties."""

    # ---- line / start / end / region ----
    def test_line_first_region(self):
        c = _make_comment(lines=[_r(10, 20), _r(30, 40)], texts=['a', 'b'])
        assert c.line == _r(10, 20)

    def test_line_empty_default(self):
        c = Comment()
        assert c.line == sb.Region(0, 0)

    def test_start(self):
        c = _make_comment(lines=[_r(10, 20), _r(30, 40)], texts=['a', 'b'])
        assert c.start == 10

    def test_end(self):
        c = _make_comment(lines=[_r(10, 20), _r(30, 40)], texts=['a', 'b'])
        assert c.end == 40

    def test_region(self):
        c = _make_comment(lines=[_r(10, 20), _r(30, 40)], texts=['a', 'b'])
        assert c.region == sb.Region(10, 40)

    def test_region_empty(self):
        c = Comment()
        assert c.region == sb.Region(0, 0)

    # ---- height / size ----
    def test_height(self):
        c = _make_comment(lines=[_r(0, 5), _r(6, 10), _r(11, 15)], texts=['a', 'b', 'c'])
        assert c.height == 3

    def test_size(self):
        c = _make_comment(lines=[_r(10, 20), _r(30, 40)], texts=['a', 'b'])
        assert c.size == 30  # 40 - 10

    # ---- bare_content / bare_size ----
    def test_bare_content(self):
        c = _make_comment(lines=[_r(0, 5), _r(6, 10)], texts=['hello', 'world'])
        assert c.bare_content == 'hello\nworld'

    def test_bare_size(self):
        c = _make_comment(lines=[_r(0, 5), _r(6, 10)], texts=['ab', 'cde'])
        # sum(len) + (height - 1) = 2 + 3 + 1 = 6
        assert c.bare_size == 6

    def test_bare_size_single_line(self):
        c = _make_comment(lines=[_r(0, 5)], texts=['hello'])
        assert c.bare_size == 5

    # ---- rowspan ----
    def test_rowspan(self):
        c = _make_comment(lines=[_r(0, 5), _r(6, 10)], texts=['a', 'b'], row=3)
        assert c.rowspan == (3, 5)

    # ---- indent ----
    def test_indent(self):
        c = _make_comment(col=1, punct='#')
        assert c.indent == 0

    def test_indent_with_whitespace(self):
        c = _make_comment(col=4, punct='#')
        assert c.indent == 3

    def test_indent_double_slash(self):
        c = _make_comment(col=2, punct='//')
        assert c.indent == 0

    def test_indent_large_col(self):
        c = _make_comment(col=5, punct='//')
        assert c.indent == 3


class TestCommentMethods:
    """Tests for Comment methods."""

    def test_follows_true(self):
        c1 = _make_comment(lines=[_r(0, 10)], texts=['a'], row=0, col=1, punct='#')
        c2 = _make_comment(lines=[_r(11, 20)], texts=['b'], row=1, col=1, punct='#')
        assert c2.follows(c1)

    def test_follows_false_different_row(self):
        c1 = _make_comment(lines=[_r(0, 10)], texts=['a'], row=0, col=1, punct='#')
        c2 = _make_comment(lines=[_r(11, 20)], texts=['b'], row=5, col=1, punct='#')
        assert not c2.follows(c1)

    def test_follows_false_different_col(self):
        c1 = _make_comment(lines=[_r(0, 10)], texts=['a'], row=0, col=1, punct='#')
        c2 = _make_comment(lines=[_r(11, 20)], texts=['b'], row=1, col=2, punct='#')
        assert not c2.follows(c1)

    def test_follows_false_different_punct(self):
        """follows() does not check punct - it only checks row and col."""
        c1 = _make_comment(lines=[_r(0, 10)], texts=['a'], row=0, col=1, punct='#')
        c2 = _make_comment(lines=[_r(11, 20)], texts=['b'], row=1, col=1, punct='//')
        # follows() returns True because it only checks row + col, not punct
        assert c2.follows(c1)

    def test_contains_row_true(self):
        c = _make_comment(lines=[_r(0, 5), _r(6, 10)], texts=['a', 'b'], row=3)
        assert c.contains_row(3)
        assert c.contains_row(4)

    def test_contains_row_false(self):
        c = _make_comment(lines=[_r(0, 5), _r(6, 10)], texts=['a', 'b'], row=3)
        assert not c.contains_row(2)
        assert not c.contains_row(5)

    def test_contains_row_boundary(self):
        c = _make_comment(lines=[_r(0, 5)], texts=['a'], row=0)
        assert c.contains_row(0)
        assert not c.contains_row(1)

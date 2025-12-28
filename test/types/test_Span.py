############
### HEAD ###
############
### STANDARD
from typing import Any

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.types import Span
from ..conftest import boolmap


############
### BODY ###
############
class TestSpan:
    # -------------------
    # `0` Initial Methods
    # -------------------
    @pyt.mark.parametrize(
        'arg0, arg1, expected',
        [
            # Tuple inputs
            ((1, 3), -1, (1, 3)),
            ((0, 10), -1, (0, 10)),
            ((5, 5), -1, (5, 5)),
            # Two numeric arguments
            (1, 3, (1, 3)),
            (0, 10, (0, 10)),
            (5, 5, (5, 5)),
            # String inputs with delimiters
            ('1-3', -1, (1, 3)),
            ('0/10', -1, (0, 10)),
            ('5,5', -1, (5, 5)),
            ('1 - 3', -1, (1, 3)),
            ('0 / 10', -1, (0, 10)),
            ('5 , 5', -1, (5, 5)),
            # String with second argument
            ('5', 10, (5, 10)),
            ('0', 1, (0, 1)),
        ],
    )
    def test_constructor_valid(
        self, arg0: str | int | tuple[int, int], arg1: int, expected: tuple[int, int]
    ):
        span = Span(arg0) if arg1 == -1 else Span(arg0, arg1)
        assert span == expected

    def test_constructor_span_input(self):
        """Test that passing a Span object returns itself"""
        original = Span(1, 5)
        copy = Span(original)
        assert copy is original

    @pyt.mark.parametrize(
        'arg0, arg1',
        [
            # Invalid tuple length
            ((1, 2, 3), -1),
            ((1,), -1),
            # Invalid span order
            ((5, 3), -1),
            (5, 3),
            # String that can't be parsed
            ('invalid', -1),
            ('1-2-3', -1),
            ('a-b', -1),
        ],
    )
    def test_constructor_invalid(self, arg0: tuple | int | str, arg1: int):
        with pyt.raises((AssertionError, ValueError)):  # noqa: PT012
            if arg1 == -1:
                Span(arg0)
            else:
                Span(arg0, arg1)

    # -------------------
    # `-` Private Methods
    # -------------------

    # -------------------
    # `+` Primary Methods
    # -------------------

    # ------------------
    # `x` Public Methods
    # ------------------
    # --------------
    # `x0` Overrides
    # --------------
    @pyt.mark.parametrize(
        'span, expected',
        [
            (Span(1, 5), '1-4'),
            (Span(0, 10), '0-9'),
            (Span(5, 6), '5'),
            (Span(10, 11), '10'),
            (Span(5, 5), ''),
        ],
    )
    def test_str(self, span: Span, expected: bool):
        assert str(span) == expected

    @pyt.mark.parametrize(
        'span, expected',
        boolmap(
            true=[Span(1, 5), Span(0, 10)],
            false=[Span(0, 0), Span(5, 5)],
            base_type=Span,
        ),
    )
    def test_bool(self, span: Span, expected: bool):
        assert bool(span) == expected

    @pyt.mark.parametrize(
        'lhs, rhs, expected',
        boolmap(
            true=[
                (Span(1, 5), Span(2, 6)),
                (Span(1, 5), (2, 6)),
            ],
            false=[
                (Span(2, 6), Span(1, 5)),
                (Span(1, 5), Span(1, 5)),
                (Span(5, 10), Span(3, 8)),
                (Span(1, 5), (1, 5)),
                (Span(1, 5), (0, 4)),
            ],
        ),
    )
    def test_lt(self, lhs: Span, rhs: Span | tuple, expected: bool):
        assert (lhs < rhs) == expected

    @pyt.mark.parametrize(
        'lhs, rhs, expected',
        boolmap(
            true=[
                (Span(1, 5), Span(1, 5)),
                (Span(0, 0), Span(0, 0)),
                (Span(1, 5), (1, 5)),
            ],
            false=[
                (Span(1, 5), Span(1, 6)),
                (Span(1, 5), Span(2, 5)),
                (Span(1, 5), (2, 5)),
            ],
        ),
    )
    def test_eq(self, lhs: Span, rhs: Span | tuple, expected: bool):
        assert (lhs == rhs) == expected

    @pyt.mark.parametrize(
        'primary, other, expected',
        boolmap(
            true=[
                (Span(1, 5), Span(3, 7)),  # Overlap
                (Span(1, 5), Span(0, 2)),  # Overlap at start
                (Span(1, 5), Span(2, 4)),  # One contained in other
                (Span(2, 4), Span(1, 5)),  # Other way around
                (Span(1, 5), Span(1, 5)),  # Identical
                (Span(1, 5), Span(4, 8)),
                (Span(1, 5), (3, 7)),
                (Span(1, 5), (1, 2, 3)),
                (Span(1, 5), [1, 2, 3]),
            ],
            false=[
                (Span(1, 5), Span(5, 8)),  # Adjacent, no overlap
                (Span(1, 5), Span(6, 8)),  # No overlap
                (Span(1, 5), (5, 8)),
                # Invalid types
                (Span(1, 5), 'string'),
            ],
            base_type=Span,
        ),
    )
    def test_contains(self, primary: Span, other: object, expected: bool):
        assert (other in primary) == expected

    @pyt.mark.parametrize(
        'p0, other, expected',
        [
            # Adding integer
            ((1, 5), 2, (3, 7)),
            ((0, 10), -2, (-2, 8)),
            ((5, 5), 1, (6, 6)),
            # Adding tuple/list
            ((1, 5), (2, 3), (3, 8)),
            ((1, 5), [2, 3], (3, 8)),
            ((0, 10), (-1, 1), (-1, 11)),
            # Adding invalid type (should return self)
            ((1, 5), 'string', (1, 5)),
            ((1, 5), dict(a=1), (1, 5)),
        ],
    )
    def test_add(self, p0: Span, other: Any, expected: Span):
        span = Span(*p0)
        result = span + other
        assert result == expected

    # ---------------
    # `x1` Properties
    # ---------------
    @pyt.mark.parametrize(
        'span, expected',
        [
            (Span(1, 5), 4),
            (Span(0, 10), 10),
            (Span(5, 5), 0),
            (Span(100, 200), 100),
        ],
    )
    def test_delta(self, span: Span, expected: int):
        assert span.delta == expected

    # ------------
    # `x2` Methods
    # ------------
    @pyt.mark.parametrize(
        'p0, p1, expected',
        [
            ((1, 5), (3, 7), (1, 7)),
            ((1, 5), (0, 2), (0, 5)),
            ((1, 5), (6, 8), (1, 8)),
            ((3, 7), (1, 5), (1, 7)),
            ((1, 5), (1, 5), (1, 5)),
        ],
    )
    def test_join(self, p0: tuple[int, int], p1: tuple[int, int], expected: tuple[int, int]):
        span1 = Span(*p0)
        span2 = Span(*p1)
        result = span1.join(span2)
        assert result == expected

    def test_join_with_tuple(self):
        span = Span(1, 5)
        result = span.join((3, 7))
        assert result == (1, 7)

    @pyt.mark.parametrize(
        'text, expected',
        [
            ('1 - 2', (1, 3)),
            ('1-2', (1, 3)),
            ('432-33', (432, 434)),
            ('432-3', (432, 434)),
            ('2265-77', (2265, 2278)),
            ('1475-33', (1475, 1534)),
            ('5', (5, 6)),
            ('12345', (12345, 12346)),
            ('invalid', (0, 0)),
            ('1-2-3', (0, 0)),
        ],
    )
    def test_parse(self, text: str, expected: tuple[int, int]):
        assert Span.parse(text) == expected

    @pyt.mark.parametrize(
        'spans, expected',
        [
            # Simple merge
            ([(1, 3), (2, 5)], [(1, 5)]),
            # Multiple overlapping spans
            ([(1, 3), (2, 5), (4, 8)], [(1, 8)]),
            # Non-overlapping spans
            ([(1, 3), (5, 7), (9, 11)], [(1, 3), (5, 7), (9, 11)]),
            # Adjacent spans (touching but not overlapping)
            ([(1, 3), (3, 5)], [(1, 5)]),
            # Single span
            ([(1, 5)], [(1, 5)]),
            # Empty list
            ([], []),
            # Duplicate spans
            ([(1, 5), (1, 5), (2, 6)], [(1, 6)]),
            # Mixed Span objects and tuples
            ([Span(1, 3), (2, 5), Span(4, 8)], [(1, 8)]),
        ],
    )
    def test_merge(self, spans, expected):
        result = Span.merge(*spans)
        assert result == [Span(*span) for span in expected]

    def test_merge_preserves_order(self):
        """Test that merge returns spans in sorted order"""
        spans = [(5, 7), (1, 3), (9, 11), (2, 4)]
        result = Span.merge(*spans)
        for i in range(len(result) - 1):
            assert result[i] < result[i + 1]

    def test_empty_span_behavior(self):
        """Test behavior of empty spans"""
        empty_span = Span(5, 5)

        # Empty spans should be falsy
        assert not empty_span

        # Empty spans should not contain anything
        assert 5 not in empty_span
        assert (4, 6) not in empty_span

        # Empty spans can still be added to
        assert empty_span + 1 == (6, 6)

        # Empty spans can be joined
        assert empty_span.join((1, 3)) == (1, 5)

    def test_regex_pattern(self):
        """Test that the DELIM_RGX pattern works as expected"""
        pattern = Span.DELIM_RGX

        # Test various delimiters
        assert pattern.split('1-2') == ['1', '2']
        assert pattern.split('1 - 2') == ['1', '2']
        assert pattern.split('1/2') == ['1', '2']
        assert pattern.split('1,2') == ['1', '2']
        assert pattern.split('1 / 2') == ['1', '2']
        assert pattern.split('1 , 2') == ['1', '2']

############
### HEAD ###
############
### STANDARD

### EXTERNAL
import pytest as pyt

### INTERNAL
from my import GoogleSheet


############
### BODY ###
############
class TestGoogleSheet:
    @pyt.mark.parametrize(
        'shape, start, expected', [
            ((1, 1), 'A1', 'A1:A1'),
            ((3, 2), 'B2', 'B2:D3'),
            ((4, 15), 'Z50', 'Z50:AC64'),
            ((10, 10), 'A1', 'A1:J10'),
            ((2, 3), 'ZZZ9', 'ZZZ9:AAAA11'),
        ]
    )
    def test_shape_to_range(self, shape: tuple[int, int], start: str, expected: str):
        result = GoogleSheet.shape_to_range(shape, start)
        assert result == expected

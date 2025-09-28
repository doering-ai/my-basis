############
### HEAD ###
############
### STANDARD

### EXTERNAL
import pytest as pyt
import pandas as pd

### INTERNAL
from my import GoogleSheet


############
### BODY ###
############
class TestGoogleSheet:
    @pyt.mark.parametrize(
        'shape, start, expected',
        [
            ((1, 1), 'A1', 'A1:A1'),
            ((3, 2), 'B2', 'B2:D3'),
            ((4, 15), 'Z50', 'Z50:AC64'),
            ((10, 10), 'A1', 'A1:J10'),
            ((2, 3), 'ZZZ9', 'ZZZ9:AAAA11'),
        ],
    )
    def test_shape_to_range(self, shape: tuple[int, int], start: str, expected: str):
        result = GoogleSheet.shape_to_range(shape, start)
        assert result == expected

    @pyt.mark.parametrize(
        'data, header, index, expected',
        [
            (
                pd.DataFrame(dict(A=[1, 2], B=[3, 4])),
                True,
                False,
                [['A', 'B'], ['1', '3'], ['2', '4']],
            ),
            (pd.DataFrame(dict(A=[1, 2], B=[3, 4])), False, False, [['1', '3'], ['2', '4']]),
            (
                pd.DataFrame(dict(A=[1, 2], B=[3, 4])),
                True,
                True,
                [['index', 'A', 'B'], ['0', '1', '3'], ['1', '2', '4']],
            ),
            (
                pd.DataFrame(dict(A=['1', None], B=['3', '4'])),
                True,
                False,
                [['A', 'B'], ['1', '3'], ['', '4']],
            ),
            (pd.DataFrame(), True, False, [[]]),
            (
                pd.DataFrame(dict(col1=['a', 'b', 'c'])),
                False,
                True,
                [['0', 'a'], ['1', 'b'], ['2', 'c']],
            ),
        ],
    )
    def test_serialize_data(
        self, data: pd.DataFrame, header: bool, index: bool, expected: list[list[str]]
    ):
        result = GoogleSheet.serialize_data(data, header=header, index=index)
        assert result == expected

    @pyt.mark.parametrize(
        'values, header, index, expected',
        [
            ([], True, '', pd.DataFrame()),
            ([[]], True, '', pd.DataFrame()),
            (
                [['A', 'B'], ['1', '3'], ['2', '4']],
                True,
                '',
                pd.DataFrame(dict(A=['1', '2'], B=['3', '4'])),
            ),
            (
                [['1', '3'], ['2', '4']],
                False,
                '',
                pd.DataFrame([[1, 3], [2, 4]], columns=[0, 1]),
            ),
            (
                [['Name', 'Age'], ['Alice', '25'], ['Bob', '30']],
                True,
                'Name',
                pd.DataFrame(dict(Age=['25', '30']), index=pd.Index(['Alice', 'Bob'], name='Name')),
            ),
            (
                [['A'], ['1'], ['2'], ['3']],
                True,
                '',
                pd.DataFrame(dict(A=['1', '2', '3'])),
            ),
            (
                [['A', 'B'], ['1'], ['2', '4']],
                True,
                '',
                pd.DataFrame(dict(A=['1', '2'], B=['', '4'])).ffill(),
            ),
            (
                [['A'], ['1', '3'], ['2', '4', '5']],
                True,
                '',
                pd.DataFrame(
                    {'A': ['1', '2'], 'Column 2': ['3', '4'], 'Column 3': ['', '5']}
                ).ffill(),
            ),
        ],
    )
    def test_deserialize_data(
        self, values: list[list], header: bool, index: str, expected: pd.DataFrame
    ):
        result = GoogleSheet.deserialize_data(values, header=header, index=index)
        pd.testing.assert_frame_equal(result, expected.astype(str), check_dtype=False)

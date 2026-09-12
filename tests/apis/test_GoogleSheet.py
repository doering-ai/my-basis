############
### HEAD ###
############
### STANDARD
import inspect

### EXTERNAL
import pytest as pyt
import pandas as pd

### INTERNAL
from my.apis import GoogleSheet

cls = GoogleSheet


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
        result = cls.shape_to_range(shape, start)
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
        result = cls.serialize_data(data, header=header, index=index)
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
        result = cls.deserialize_data(values, header=header, index=index)
        pd.testing.assert_frame_equal(result, expected.astype(str), check_dtype=False)

    def test_import_guard_message_names_google_extra(self, monkeypatch: pyt.MonkeyPatch):
        """Regression (basis-D7): the missing-dependency message must name the `[google]`
        extra (with an actionable install command), not the copy-pasted `[metrics]`/`utils.`
        wording borrowed from `MetricUtils`'s sibling guard."""
        module = inspect.getmodule(cls)
        assert module is not None
        monkeypatch.setattr(module, 'INSTALLED', False)

        with pyt.raises(ImportError) as exc_info:
            cls.shape_to_range((1, 1))

        message = str(exc_info.value)
        assert 'pip install my-basis[google]' in message
        assert '[metrics]' not in message
        assert 'utils.' not in message


class TestGoogleSheetStyling:
    def test_hex_color(self):
        assert cls.hex_color('#5A6169') == {
            'red': 90 / 255,
            'green': 97 / 255,
            'blue': 105 / 255,
        }
        assert cls.hex_color('B6ECF7') == {
            'red': 182 / 255,
            'green': 236 / 255,
            'blue': 247 / 255,
        }

    def test_hex_color_rejects_non_hex(self):
        with pyt.raises(AssertionError):
            cls.hex_color('#5A616')

    def test_repeat_cell(self):
        result = cls.repeat_cell(7, 0, 3, 1, 10, {'userEnteredFormat': {'bold': True}})
        assert result == {
            'repeatCell': {
                'range': {
                    'sheetId': 7,
                    'startColumnIndex': 0,
                    'endColumnIndex': 3,
                    'startRowIndex': 1,
                    'endRowIndex': 10,
                },
                'cell': {'userEnteredFormat': {'bold': True}},
                'fields': 'userEnteredFormat',
            }
        }

    def test_set_widths(self):
        result = cls.set_widths(7, [80, 150], start=3)
        assert result == [
            {
                'updateDimensionProperties': {
                    'range': {
                        'sheetId': 7,
                        'dimension': 'COLUMNS',
                        'startIndex': 3,
                        'endIndex': 4,
                    },
                    'properties': {'pixelSize': 80},
                    'fields': 'pixelSize',
                }
            },
            {
                'updateDimensionProperties': {
                    'range': {
                        'sheetId': 7,
                        'dimension': 'COLUMNS',
                        'startIndex': 4,
                        'endIndex': 5,
                    },
                    'properties': {'pixelSize': 150},
                    'fields': 'pixelSize',
                }
            },
        ]

    def test_add_banding(self):
        result = cls.add_banding(7, 18, 187, header='#5A6169', first='#2E3135', second='#212225')
        banding = result['addBanding']['bandedRange']
        assert banding['range'] == {
            'sheetId': 7,
            'startRowIndex': 0,
            'endRowIndex': 187,
            'startColumnIndex': 0,
            'endColumnIndex': 18,
        }
        assert banding['rowProperties']['headerColor'] == cls.hex_color('#5A6169')

    def test_gradient_rule(self):
        result = cls.gradient_rule(7, 5, 50, 0, 5, 10, '#B54548', '#5A6169', '#4CA96B')
        rule = result['addConditionalFormatRule']['rule']
        gradient = rule['gradientRule']
        assert gradient['minpoint'] == {
            'color': cls.hex_color('#B54548'),
            'type': 'NUMBER',
            'value': '0',
        }
        assert gradient['maxpoint']['value'] == '10'
        assert rule['ranges'] == [
            {
                'sheetId': 7,
                'startColumnIndex': 5,
                'endColumnIndex': 6,
                'startRowIndex': 1,
                'endRowIndex': 50,
            }
        ]

    def test_text_rule(self):
        result = cls.text_rule(7, 4, 50, 'open', fg='#3DD68C', bg='#0F2E22', bold=True)
        boolean = result['addConditionalFormatRule']['rule']['booleanRule']
        assert boolean['condition'] == {'type': 'TEXT_EQ', 'values': [{'userEnteredValue': 'open'}]}
        assert boolean['format']['textFormat']['bold'] is True
        assert boolean['format']['backgroundColor'] == cls.hex_color('#0F2E22')

    def test_formula_condition_and_rule(self):
        packed = cls.formula_condition('NUMBER_BETWEEN', '=TODAY()', '=TODAY()+14')
        assert packed == 'NUMBER_BETWEEN =TODAY() =TODAY()+14'
        result = cls.formula_rule(7, 4, 50, packed, fg='#FFCA16')
        boolean = result['addConditionalFormatRule']['rule']['booleanRule']
        assert boolean['condition'] == {
            'type': 'NUMBER_BETWEEN',
            'values': [{'userEnteredValue': '=TODAY()'}, {'userEnteredValue': '=TODAY()+14'}],
        }
        assert boolean['format'] == {'textFormat': {'foregroundColor': cls.hex_color('#FFCA16')}}

    def test_data_validation_warn_mode(self):
        result = cls.data_validation(7, 4, 100, '=meta!$A$2:$A$10')
        rule = result['setDataValidation']['rule']
        assert rule['condition']['values'] == [{'userEnteredValue': '=meta!$A$2:$A$10'}]
        assert rule['strict'] is False
        assert rule['showCustomUi'] is True

    def test_insert_columns(self):
        result = cls.insert_columns(7, 12)
        assert result == {
            'insertDimension': {
                'range': {
                    'sheetId': 7,
                    'dimension': 'COLUMNS',
                    'startIndex': 12,
                    'endIndex': 13,
                },
                'inheritFromBefore': False,
            }
        }

    def test_sheet_properties(self):
        result = cls.sheet_properties(
            7, frozen_rows=1, frozen_cols=4, hide_gridlines=True, tab_color='#714F19'
        )
        request = result['updateSheetProperties']
        assert request['properties']['gridProperties'] == {
            'frozenRowCount': 1,
            'frozenColumnCount': 4,
            'hideGridlines': True,
        }
        assert request['properties']['tabColor'] == cls.hex_color('#714F19')
        assert request['fields'] == (
            'gridProperties.frozenRowCount,gridProperties.frozenColumnCount,'
            'gridProperties.hideGridlines,tabColor'
        )

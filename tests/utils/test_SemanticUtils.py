############
### HEAD ###
############
### STANDARD
from typing import Literal
from pathlib import Path

### EXTERNAL
import pytest as pyt

### INTERNAL
from my import typist
from my.utils import SemanticUtils

cls = SemanticUtils


############
### BODY ###
############
class TestSemanticUtils:
    @staticmethod
    def plural_test_data() -> list[tuple[str, str, str]]:
        """Loads pluralization test data from a YAML file and returns it as a list of tuples.

        Returns:
            A list of `(category, plural, singular)` tuples.
        """
        file = Path(__file__).parent / 'plural_tests.yaml'
        assert file.exists(), f'Test data file not found: {file}'
        data: dict[str, list[list[str]]] = typist.from_file(file)
        return [(category, item[0], item[1]) for category, items in data.items() for item in items]

    # ------------------
    # `0` ROMAN NUMERALS
    # ------------------
    @pyt.mark.parametrize(
        'roman, decimal',
        [
            ('I', 1),
            ('II', 2),
            ('III', 3),
            ('IV', 4),
            ('V', 5),
            ('VI', 6),
            ('VII', 7),
            ('VIII', 8),
            ('IX', 9),
            ('X', 10),
            ('XL', 40),
            ('LX', 60),
            ('XC', 90),
            ('CXI', 111),
            ('MCXI', 1111),
            ('CMXCIX', 999),
            ('', 0),
            ('X: not a roman numeral', 0),
            ('X I', 0),
        ],
    )
    def test_roman_to_decimal(self, roman: str, decimal: int):
        assert cls.roman_to_decimal(roman) == decimal

    @pyt.mark.parametrize(
        'decimal, roman',
        [
            (1, 'I'),
            (2, 'II'),
            (3, 'III'),
            (4, 'IV'),
            (5, 'V'),
            (6, 'VI'),
            (7, 'VII'),
            (8, 'VIII'),
            (9, 'IX'),
            (10, 'X'),
            (40, 'XL'),
            (60, 'LX'),
            (90, 'XC'),
            (111, 'CXI'),
            (1111, 'MCXI'),
            (999, 'CMXCIX'),
        ],
    )
    def test_decimal_to_roman(self, decimal: int, roman: str):
        assert cls.decimal_to_roman(decimal) == roman

    # -----------
    # `1` AMOUNTS
    # -----------
    @pyt.mark.parametrize(
        'amount, unit, width, expected',
        [
            # Numeric format (K/M/B)
            (0, 'num', 0, '0'),
            (500, 'num', 0, '500'),
            (1000, 'num', 0, '1K'),
            (1500, 'num', 0, '2K'),  # Rounds to 2K
            (1000000, 'num', 0, '1M'),
            (1500000, 'num', 0, '2M'),
            (1000000000, 'num', 0, '1B'),
            (2500000000, 'num', 0, '2B'),
            # Memory format (KB/MB/GB)
            (1024, 'mem', 0, '1KB'),
            (1500, 'mem', 0, '2KB'),
            (1000000, 'mem', 0, '1MB'),
            (1000000000, 'mem', 0, '1GB'),
            # With width formatting
            (1000, 'num', 5, '1.00K'),
            (1000000, 'mem', 6, '1.000MB'),
        ],
    )
    def test_format_amount(
        self, amount: int, unit: Literal['num', 'mem'], width: int, expected: str
    ):
        assert unit in {'num', 'mem'}
        assert cls.format_amount(amount, unit, width) == expected

    # -----------------
    # `2` PLURALIZATION
    # -----------------
    @pyt.mark.parametrize('category, plural, expected', plural_test_data())
    def test_to_singular(self, category: str, plural: str, expected: str):
        assert cls.to_singular(plural) == expected

    def test_to_singular_invalid(self):
        with pyt.raises(ValueError, match='Failed to convert'):
            cls.to_singular('notaword')

    @pyt.mark.parametrize(
        'num, expected',
        [
            (1, '1st'),
            (2, '2nd'),
            (3, '3rd'),
            (4, '4th'),
            (10, '10th'),
            (11, '11th'),
            (12, '12th'),
            (13, '13th'),
            (21, '21st'),
            (22, '22nd'),
            (23, '23rd'),
            (101, '101st'),
            (111, '111th'),
            (0, ''),  # Leading zeros stripped
            ('001', '1st'),
            ('000', ''),
        ],
    )
    def test_to_ordinal(self, num: int | str, expected: str):
        assert cls.to_ordinal(num) == expected

    # ---------------
    # `3` IDENTIFIERS
    # ---------------
    @pyt.mark.parametrize(
        'symbols, should_pass',
        [
            (['valid_name', 'another_valid'], True),
            (['myVar'], True),
            (['_private'], True),
            (['for'], False),  # Python keyword
            (['class'], False),  # Both Python and TypeScript keyword
            (['await'], False),  # TypeScript keyword
            (['123invalid'], False),  # Invalid identifier
            (['my-var'], False),  # Invalid identifier (hyphen)
        ],
    )
    def test_validate_identifier(self, symbols: list[str], should_pass: bool):
        if should_pass:
            cls.validate_identifier(*symbols)
        else:
            with pyt.raises(AssertionError):
                cls.validate_identifier(*symbols)

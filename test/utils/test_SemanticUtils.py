############
### HEAD ###
############
### STANDARD

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.utils import SemanticUtils

cls = SemanticUtils


############
### BODY ###
############
class TestSemanticUtils:
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
    @pyt.mark.parametrize('data, expected', [])
    def test_format_amount(self, data: str, expected: str):
        pass

    # -----------------
    # `2` PLURALIZATION
    # -----------------
    @pyt.mark.parametrize('data, expected', [])
    def test_to_singular(self, data: str, expected: str):
        pass

    @pyt.mark.parametrize('data, expected', [])
    def test_to_ordinal(self, data: str, expected: str):
        pass

    # ---------------
    # `3` IDENTIFIERS
    # ---------------
    @pyt.mark.parametrize('data, expected', [])
    def test_validate_identifier(self, data: str, expected: str):
        pass

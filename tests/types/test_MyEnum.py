############
### HEAD ###
############
### STANDARD
from enum import Flag, auto
import functools as ft
import regex as re

### EXTERNAL
import pytest as pyt

### INTERNAL
from my import ut, MyEnum


############
### DATA ###
############
class Color(MyEnum):
    PINK = 1
    CLAY = 2
    BLUE = 3


class Priority(MyEnum):
    LOW = 'low'
    MED = 'medium'
    LRG = 'large'


class Status(MyEnum):
    PEND = 10
    ACTV = 20
    COMP = 30


class Perm(MyEnum, Flag):
    READ = auto()
    WRITE = auto()
    EXECUTE = auto()


class Tag(MyEnum):
    NONE = ''
    SOME = 'some'


class NumericText(MyEnum):
    TEN = '10'


class CaseCollision(MyEnum):
    LOWER = 'value'
    UPPER = 'VALUE'


class CustomAliasEnum(MyEnum):
    ALPHA = 'alpha'
    BETA = 'b'
    GAMMA = 'g'

    @ft.lru_cache(maxsize=1)
    @staticmethod
    def _aliases() -> dict[str, re.Pattern]:
        return ut.regex_dict(
            dict(
                alpha=r'first|primary|alpha',
                beta=r'second|secondary|beta',
                gamma=r'third|gamma',
            ),
            compile_function=lambda s: re.compile(s, re.I),
        )


############
### BODY ###
############
class TestMyEnum:
    # ---------
    # 1. READ()
    # ---------
    @pyt.mark.parametrize(
        'cls, value, expected',
        [
            # Integer enums
            (Color, 1, Color.PINK),
            (Color, 2, Color.CLAY),
            (Color, 3, Color.BLUE),
            # String enums
            (Priority, 'low', Priority.LOW),
            (Priority, 'medium', Priority.MED),
            (Priority, 'large', Priority.LRG),
            # Case-insensitive member-name lookup
            (Priority, 'LOW', Priority.LOW),
            (Priority, 'MeD', Priority.MED),
            (Priority, ' LRG ', Priority.LRG),
            # Trimmed and case-insensitive member-value lookup
            (Priority, ' medium ', Priority.MED),
            (Priority, ' MeDiUm ', Priority.MED),
            (Priority, ' LARGE ', Priority.LRG),
            # String representation of integers
            (Status, '10', Status.PEND),
            (Status, '20', Status.ACTV),
            (Status, '30', Status.COMP),
            (Status, ' 10 ', Status.PEND),
            # Name-based lookup
            (Color, 'PINK', Color.PINK),
            (Color, 'CLAY', Color.CLAY),
            (Color, 'Blue', Color.BLUE),
            # Falsy, numeric-looking, and case-colliding string values round-trip.
            (Tag, '', Tag.NONE),
            (Tag, 'some', Tag.SOME),
            (NumericText, '10', NumericText.TEN),
            (NumericText, ' 10 ', NumericText.TEN),
            (CaseCollision, 'value', CaseCollision.LOWER),
            (CaseCollision, ' VALUE ', CaseCollision.UPPER),
        ],
    )
    def test_read(self, cls, value, expected):
        assert cls.read(value) == expected

    @pyt.mark.parametrize(
        'cls, value, expected',
        [
            # Flag enum single values
            (Perm, 1, Perm.READ),
            (Perm, 2, Perm.WRITE),
            (Perm, 4, Perm.EXECUTE),
            # Flag enum combinations
            (Perm, 3, Perm.READ | Perm.WRITE),
            (Perm, 5, Perm.READ | Perm.EXECUTE),
            (Perm, 7, Perm.READ | Perm.WRITE | Perm.EXECUTE),
            # String representations
            (Perm, 'READ', Perm.READ),
            (Perm, '1', Perm.READ),
            # List-based flag combinations
            (Perm, ['READ', 'WRITE'], Perm.READ | Perm.WRITE),
            (Perm, ['read', 'execute'], Perm.READ | Perm.EXECUTE),
            (Perm, ['1', '4'], Perm.READ | Perm.EXECUTE),
            # Pipe-separated strings
            (Perm, 'READ|WRITE', Perm.READ | Perm.WRITE),
            (Perm, 'read|write|execute', Perm.READ | Perm.WRITE | Perm.EXECUTE),
        ],
    )
    def test_read__flag(self, cls, value, expected):
        assert cls.read(value) == expected

    @pyt.mark.parametrize(
        'value, expected',
        [
            ('first', CustomAliasEnum.ALPHA),
            ('PRIMARY', CustomAliasEnum.ALPHA),
            ('alpha', CustomAliasEnum.ALPHA),
            ('Second', CustomAliasEnum.BETA),
            ('secondary', CustomAliasEnum.BETA),
            ('BETA', CustomAliasEnum.BETA),
            ('third', CustomAliasEnum.GAMMA),
            ('Gamma', CustomAliasEnum.GAMMA),
        ],
    )
    def test_read__aliases(self, value, expected):
        assert CustomAliasEnum.read(value) == expected

    @pyt.mark.parametrize(
        'cls, value, message',
        [
            (Color, 'invalid', 'Invalid Color value'),
            (Color, 99, 'Invalid Color value'),
            (Priority, 'unknown', 'Invalid Priority value'),
            (Status, 'not_a_status', 'Invalid Status value'),
            (Perm, 'invalid_permission', 'Invalid Perm value'),
            (CustomAliasEnum, 'not_an_alias', 'Invalid CustomAliasEnum value'),
            (CaseCollision, 'VaLuE', 'Ambiguous CaseCollision value'),
        ],
    )
    def test_read__invalid(self, cls, value, message: str):
        with pyt.raises(ValueError, match=message):
            cls.read(value)

    # ----------------
    # 2. SERIALIZATION
    # ----------------
    @pyt.mark.parametrize(
        'enum_value, expected',
        [
            # String-valued enums return their string value
            (Priority.LOW, 'low'),
            (Priority.MED, 'medium'),
            (Priority.LRG, 'large'),
            # Non-string enums return lowercase name
            (Color.PINK, 'pink'),
            (Color.CLAY, 'clay'),
            (Color.BLUE, 'blue'),
            (Status.PEND, 'pend'),
            (Status.ACTV, 'actv'),
            (Status.COMP, 'comp'),
            # Falsy and truthy string values use their values, not member names.
            (Tag.NONE, ''),
            (Tag.SOME, 'some'),
        ],
    )
    def test__write(self, enum_value, expected):
        assert enum_value.write() == expected
        assert str(enum_value) == expected

    @pyt.mark.parametrize(
        'enum_value, expected',
        [
            (Perm.READ, 'read'),
            (Perm.WRITE, 'write'),
            (Perm.EXECUTE, 'execute'),
            (Perm.READ | Perm.WRITE, 'read|write'),
            (Perm.READ | Perm.EXECUTE, 'read|execute'),
            (Perm.WRITE | Perm.EXECUTE, 'write|execute'),
            (Perm.READ | Perm.WRITE | Perm.EXECUTE, 'read|write|execute'),
        ],
    )
    def test_write__flag(self, enum_value, expected):
        result = enum_value.write()
        assert result == expected
        assert str(enum_value) == expected

    # -------------
    # 3. OPERATIONS
    # -------------
    @pyt.mark.parametrize(
        'left, right, expected',
        [
            # Basic integer arithmetic
            (Color.PINK, Color.CLAY, Color.BLUE),  # 1 + 2 = 3
            (Status.PEND, Status.ACTV, Status.COMP),  # 10 + 20 = 30
            (Color.PINK, 2, Color.BLUE),
        ],
    )
    def test_add(self, left, right, expected):
        assert left + right == expected

        # Test in-place addition
        temp = left
        temp += right
        assert temp == expected

    @pyt.mark.parametrize(
        'left, right, expected',
        [
            (Color.BLUE, Color.CLAY, Color.PINK),  # 3 - 2 = 1
            (Status.COMP, Status.ACTV, Status.PEND),  # 30 - 20 = 10
            (Color.BLUE, 2, Color.PINK),
        ],
    )
    def test_sub(self, left, right, expected):
        assert left - right == expected

        # Test in-place subtraction
        temp = left
        temp -= right
        assert temp == expected

    @pyt.mark.parametrize(
        'left, right, expected',
        [
            # Flag addition (bitwise OR)
            (Perm.READ, Perm.WRITE, Perm.READ | Perm.WRITE),
            (Perm.READ | Perm.WRITE, Perm.EXECUTE, Perm.READ | Perm.WRITE | Perm.EXECUTE),
            (Perm.READ, 'WRITE', Perm.READ | Perm.WRITE),
        ],
    )
    def test_add__flag(self, left, right, expected):
        assert left + right == expected

        temp = left
        temp += right
        assert temp == expected

    @pyt.mark.parametrize(
        'left, right, expected',
        [
            # Flag subtraction (bitwise AND NOT)
            (Perm.READ | Perm.WRITE, Perm.WRITE, Perm.READ),
            (Perm.READ | Perm.WRITE | Perm.EXECUTE, Perm.WRITE, Perm.READ | Perm.EXECUTE),
        ],
    )
    def test_sub__flag(self, left, right, expected):
        assert left - right == expected

        temp = left
        temp -= right
        assert temp == expected

    @pyt.mark.parametrize(
        'left, right, expected',
        [
            # Integer-valued enums
            (Color.PINK, Color.CLAY, True),  # 1 < 2
            (Color.CLAY, Color.PINK, False),  # 2 < 1
            (Color.PINK, Color.PINK, False),  # 1 < 1
            # Based on definition order for same values
            (Status.PEND, Status.ACTV, True),  # 10 < 20
            (Status.ACTV, Status.COMP, True),  # 20 < 30
            (Status.COMP, Status.PEND, False),  # 30 < 10
        ],
    )
    def test_eq(self, left, right, expected):
        assert (left < right) == expected
        assert (left <= right) == (expected or left == right)
        assert (left > right) == (not expected and left != right)
        assert (left >= right) == (not expected or left == right)

    @pyt.mark.parametrize(
        'enum_list, expected_order',
        [
            ([Color.BLUE, Color.PINK, Color.CLAY], [Color.PINK, Color.CLAY, Color.BLUE]),
            (
                [Status.COMP, Status.PEND, Status.ACTV],
                [Status.PEND, Status.ACTV, Status.COMP],
            ),
        ],
    )
    def test_lt(self, enum_list, expected_order):
        assert sorted(enum_list) == expected_order

    # ----------------------
    # 5. Properties
    # ----------------------
    @pyt.mark.parametrize(
        'enum_value, expected',
        [
            # Non-flag enums return themselves
            (Color.PINK, [Color.PINK]),
            (Priority.LOW, [Priority.LOW]),
            (Status.PEND, [Status.PEND]),
            # Single flag values
            (Perm.READ, [Perm.READ]),
            (Perm.WRITE, [Perm.WRITE]),
            (Perm.EXECUTE, [Perm.EXECUTE]),
            # Combined flag values
            (Perm.READ | Perm.WRITE, [Perm.READ, Perm.WRITE]),
            (Perm.READ | Perm.EXECUTE, [Perm.READ, Perm.EXECUTE]),
            (Perm.READ | Perm.WRITE | Perm.EXECUTE, [Perm.READ, Perm.WRITE, Perm.EXECUTE]),
        ],
    )
    def test_parts_property(self, enum_value, expected):
        parts = enum_value.parts
        assert parts == expected

    @pyt.mark.parametrize(
        'enum_value, expected_base',
        [
            # Non-flag enums return themselves
            (Color.PINK, Color.PINK),
            (Priority.LOW, Priority.LOW),
            (Status.PEND, Status.PEND),
            # Flag enums return first part
            (Perm.READ, Perm.READ),
            (Perm.READ | Perm.WRITE, Perm.READ),
            (Perm.WRITE | Perm.EXECUTE, Perm.WRITE),
            (Perm.READ | Perm.WRITE | Perm.EXECUTE, Perm.READ),
        ],
    )
    def test_base_property(self, enum_value, expected_base):
        assert enum_value.base == expected_base

    # ----------------------
    # 6. Edge cases and special scenarios
    # ----------------------
    def test_empty_flag_value(self):
        empty_permission = Perm(0)
        assert empty_permission.parts == []
        assert empty_permission.base == empty_permission
        assert str(empty_permission) == ''

    def test_aliases_cache(self):
        # Test that _aliases() is cached
        aliases1 = CustomAliasEnum._aliases()
        aliases2 = CustomAliasEnum._aliases()
        assert aliases1 is aliases2  # Should be the same object due to lru_cache

    @pyt.mark.parametrize('enum_cls', [Color, Priority, Status, Perm, CustomAliasEnum])
    def test_total_ordering(self, enum_cls):
        # Test that all comparison operations work
        vals = [Perm.READ, Perm.WRITE, Perm.EXECUTE] if enum_cls == Perm else list(enum_cls)

        if len(vals) >= 2:
            a, b = vals[0], vals[1]
            # Test that comparison methods exist and work
            assert hasattr(a, '__lt__')
            assert hasattr(a, '__le__')
            assert hasattr(a, '__gt__')
            assert hasattr(a, '__ge__')
            assert hasattr(a, '__eq__')

            # Test transitivity
            result_lt = a < b
            result_gt = a > b
            assert result_lt != result_gt or a == b

    def test_read_with_existing_enum_instance(self):
        # Test passing existing enum instance
        inst = Color.PINK
        assert Color.read(inst) == Color.PINK

    @pyt.mark.parametrize(
        'empty_list',
        [
            [],
        ],
    )
    def test_read_empty_list_flag(self, empty_list):
        # Empty list should create a zero-value flag
        result = Perm.read(empty_list)
        assert result == Perm(0)
        assert result.value == 0

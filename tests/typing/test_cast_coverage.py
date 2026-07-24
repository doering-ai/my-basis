############
### HEAD ###
############
### STANDARD
from datetime import date, datetime, time, timedelta, UTC
from enum import Enum
from typing import Any

### EXTERNAL
import pydantic as pyd
import pytest as pyt

### INTERNAL
from my.typing import TypeCast, Typist

# Reuse the enum fixtures from test_cast.py to avoid class-identity conflicts
# (two `Color` classes with the same members are still distinct types).
from .test_cast import Color, Status, Permission

cls = TypeCast
#: A fully-flexible Typist instance for driving cast-based tests.
typist = Typist(firsts=True, atomics=True, splits=True, wraps=True)


class Point(pyd.BaseModel):
    """A simple pydantic model for model-conversion tests."""

    x: int = 0
    y: int = 0


class Coord(pyd.BaseModel):
    """A second model with shared field names for model-to-model tests."""

    x: int = 0
    y: int = 0
    label: str = ''


############
### BODY ###
############
class TestCastTimeConversions:
    """Tests for Time-to-Time sub-conversions (datetime/date/time/timedelta interop)."""

    @pyt.mark.parametrize(
        'data, target, expected',
        [
            (datetime(2026, 1, 15, 10, 30, 45, tzinfo=UTC), time, time(10, 30, 45, tzinfo=UTC)),
        ],
    )
    def test_cast__datetime_to_time_subtypes(self, data: Any, target: type, expected: Any):
        """Cast a datetime to a time subtype."""
        assert cls.cast(data, target) == expected

    def test_cast__datetime_to_timedelta(self):
        """Cast a datetime to a timedelta via its timestamp."""
        result = cls.cast(datetime(2026, 1, 15, 0, 0, 0, tzinfo=UTC), timedelta)
        assert isinstance(result, timedelta)

    @pyt.mark.parametrize(
        'data, target, expected',
        [
            (date(2026, 1, 15), datetime, datetime(2026, 1, 15, 0, 0, tzinfo=UTC)),
            (date(2026, 1, 15), time, time()),
        ],
    )
    def test_cast__date_to_time_subtypes(self, data: Any, target: type, expected: Any):
        """Cast a date to a datetime or time subtype."""
        assert cls.cast(data, target) == expected

    def test_cast__date_to_timedelta(self):
        """Cast a date to a timedelta via its ordinal."""
        result = cls.cast(date(2026, 1, 15), timedelta)
        assert isinstance(result, timedelta)

    def test_cast__timedelta_to_int(self):
        """Cast a timedelta to an int via the integer-seconds route."""
        assert cls.cast(timedelta(seconds=42), int) == 42

    def test_cast__timedelta_to_float(self):
        """Cast a timedelta to a float via the integer-seconds route."""
        assert cls.cast(timedelta(seconds=42, microseconds=500000), float) == 42.5


class TestCastEnumConversions:
    """Tests for enum-to-X and X-to-enum cast transforms."""

    # ---- Enum -> String ----
    @pyt.mark.parametrize(
        'data, expected',
        [
            (Status.ACTIVE, 'active'),
            (Status.INACTIVE, 'inactive'),
            (Color.RED, 'red'),
            (Color.BLUE, 'blue'),
        ],
    )
    def test_cast__enum_to_string(self, data: Enum, expected: str):
        """Cast an enum member to a string (value for str-enums, name for int-enums)."""
        assert cls.cast(data, str) == expected

    # ---- Enum -> Scalar ----
    @pyt.mark.parametrize(
        'data, target, expected',
        [
            (Color.RED, int, 1),
            (Color.BLUE, int, 3),
        ],
    )
    def test_cast__enum_to_scalar(self, data: Enum, target: type, expected: Any):
        """Cast an enum member's value to a scalar type."""
        assert cls.cast(data, target) == expected

    # ---- Enum -> Enum ----
    def test_cast__enum_to_enum_by_name(self):
        """Cast an enum member to another enum with a matching member name."""

        class Source(Enum):
            RED = 10
            GREEN = 20
            BLUE = 30

        result = cls.cast(Source.RED, Color)
        assert result is Color.RED

    # ---- Object -> Enum ----
    @pyt.mark.parametrize(
        'data, target, expected',
        [
            (1, Color, Color.RED),
            (3, Color, Color.BLUE),
            ('active', Status, Status.ACTIVE),
            ('RED', Color, Color.RED),
            ('red', Color, Color.RED),  # case-insensitive
            ('1', Color, Color.RED),  # coerced value
        ],
    )
    def test_cast__object_to_enum(self, data: Any, target: type[Enum], expected: Enum):
        """Cast an arbitrary object to an enum member by value, name, or coerced value."""
        assert cls.cast(data, target) == expected

    def test_cast__enum_member_to_itself(self):
        """An enum member cast to its own enum returns itself."""
        assert cls.cast(Color.RED, Color) is Color.RED

    # ---- Enum -> Vec/Map/Iter/Model (decline) ----
    @pyt.mark.parametrize(
        'target',
        [list, dict],
    )
    def test_cast__enum_to_struct_declines(self, target: type):
        """Enums decline when cast to vec/map (no struct representation)."""
        assert cls.cast(Color.RED, target) is None


class TestCastFlagConversions:
    """Tests for Flag enum cast transforms."""

    def test_cast__flag_to_vec(self):
        """Cast a combined Flag to a list of active member values."""
        perm = Permission.READ | Permission.WRITE
        result = cls.cast(perm, list)
        assert result is not None
        assert {r.value for r in result} == {1, 2}

    def test_cast__flag_to_map(self):
        """Cast a combined Flag to a dict of active member names to values."""
        perm = Permission.READ | Permission.WRITE
        result = cls.cast(perm, dict)
        assert result == {'READ': 1, 'WRITE': 2}

    def test_cast__vec_to_flag(self):
        """Cast a list of values to a combined Flag value."""
        result = cls.cast([1, 2], Permission)
        assert result == Permission.READ | Permission.WRITE

    def test_cast__string_to_flag(self):
        """Cast a pipe-separated string of member names to a combined Flag."""
        result = cls.cast('READ|WRITE', Permission)
        assert result == Permission.READ | Permission.WRITE


class TestCastModelConversions:
    """Tests for model-to-model and model-to-map cast transforms."""

    def test_cast__model_to_map(self):
        """Cast a pydantic model to a plain dict."""
        p = Point(x=3, y=4)
        result = cls.cast(p, dict)
        assert result == {'x': 3, 'y': 4}

    def test_cast__model_to_model(self):
        """Cast one model to another with shared field names."""
        p = Point(x=3, y=4)
        result = cls.cast(p, Coord)
        assert isinstance(result, Coord)
        assert result.x == 3
        assert result.y == 4

    def test_cast__model_to_model_extra_fields_ignored(self):
        """Model-to-model cast only copies shared fields."""
        c = Coord(x=1, y=2, label='hello')
        result = cls.cast(c, Point)
        assert isinstance(result, Point)
        assert result.x == 1
        assert result.y == 2


class TestCastScalarEnumConversions:
    """Tests for scalar-to-enum and string-to-enum transforms."""

    def test_cast__scalar_to_enum(self):
        """Cast a scalar value to an enum member via the enum constructor."""
        assert cls.cast(2, Color) is Color.GREEN

    def test_cast__string_to_enum_by_name(self):
        """Cast a string to an enum member by uppercase name lookup."""
        assert cls.cast('GREEN', Color) is Color.GREEN

    def test_cast__string_to_enum_by_value(self):
        """Cast a string to a string-valued enum by matching value."""
        assert cls.cast('pending', Status) is Status.PENDING

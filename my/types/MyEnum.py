############
### HEAD ###
############
### STANDARD
from typing import Self, Type
from enum import Enum, Flag
import more_itertools as mi
import functools as ft

### EXTERNAL
import regex as re

### INTERNAL
from ..utils import ut


############
### DATA ###
############
@ft.total_ordering
class MyEnum(Enum):
    """
    Enhanced Enum base class with flexible parsing, arithmetic, and comparison.

    Supports reading values from strings (including aliases), integers, and lists.
    Provides arithmetic operations for numeric enums and bitwise operations for Flags.
    Implements total ordering and string conversion with configurable aliases.
    """
    @classmethod
    def read(cls, value: str | int | list | Self) -> Self:
        """
        Parse a value into an enum member.

        Supports multiple input formats:
        - Enum member: Returns as-is
        - String: Matches by name, alias, or numeric string
        - Integer: For Flag enums, creates by value
        - List: For Flag enums, combines multiple values

        Args:
            value: Value to parse into enum member.

        Returns:
            Corresponding enum member.

        Raises:
            ValueError: If value cannot be parsed.
        """
        if isinstance(value, cls):
            return value
        members = cls.__members__

        # I. Check against key names
        if isinstance(value, str):
            uval = value.upper().strip()
            if value.isdigit():
                # I.i. Cast numbers for int flags
                value = int(value)
            elif uval in members:
                # I.ii. Find by name
                return members[uval]
            elif key := ut.find_key(cls._aliases(), lambda rgx: bool(rgx.fullmatch(uval))):
                # I.iii. Find by alias
                return members[key.upper()]
            elif issubclass(cls, Flag) and '|' in uval:
                # I.iv. Break down flags into a list
                value = uval.split('|')

        # II. Handle int flags
        if isinstance(value, int) and issubclass(cls, Flag):
            return cls(value)

        # III. Immediate check against values (instead of keys)
        if type(value) is cls.vtype() and (key := ut.find_key(members, lambda v: v.value == value)):
            return members[key]

        # IV. Handle lists of values
        if isinstance(value, list):
            assert issubclass(cls, Flag)
            return cls(sum(val.value for val in map(cls.read, value)))

        raise ValueError(f'Invalid {cls.__name__} value: {value}')

    def write(self) -> str:
        """
        Convert enum member to string representation.

        Returns:
            String value, lowercase name, or pipe-separated flags for Flag enums.
        """
        if self.value and isinstance(self.value, str):
            return self.value
        elif self.name:
            return self.name.lower()
        elif isinstance(self, Flag):
            return '|'.join(
                [flag.name for flag in type(self) if flag.name and self.value & flag.value]
            )
        else:
            return str(self)

    def __str__(self) -> str:
        return self.write()

    def __sub__(self, other: Self | str | int | list) -> Self:
        cls = self.__class__
        if issubclass(cls, Flag) and isinstance(other, cls):
            return self & ~other  # type: ignore

        if not isinstance(other, cls):
            other = cls.read(other)
        return cls(self.value - other.value)  # type: ignore

    def __isub__(self, other: Self | str | int | list) -> Self:
        return self - other  # type: ignore

    def __add__(self, other: Self | str | int | list) -> Self:
        cls = self.__class__
        if issubclass(cls, Flag) and isinstance(other, cls):
            return self | other  # type:ignore
        return cls(self.value + other.value)  # type: ignore

    def __iadd__(self, other: Self | str | int | list) -> Self:
        return self + other  # type: ignore

    @property
    def parts(self) -> list[Self]:
        if not isinstance(self, Flag):
            return [self]
        else:
            return list(self) or []

    @property
    def base(self) -> Self:
        """
        Return the first/primary part of a Flag enum, or self for regular enums.

        Returns:
            First flag component or self.
        """
        return parts[0] if (parts := self.parts) else self

    def __lt__(self, other: Self | str | int | list) -> bool:
        cls = self.__class__
        if not isinstance(other, cls):
            other = cls.read(other)

        lhs = self.base
        if isinstance(lhs.value, int | float):
            return lhs.value < other.base.value
        else:
            # Else find each of the members index in the overall ordering
            members = list(self.__class__)
            return members.index(self) < members.index(other)

    @ft.lru_cache(maxsize=1)
    @staticmethod
    def _aliases() -> dict[str, re.Pattern]:
        """
        Define regex patterns for parsing aliases.

        Override in subclasses to provide custom alias matching.

        Returns:
            Dict mapping member names to alias regex patterns.
        """
        return {}

    @classmethod
    def vtype(cls) -> Type:
        """
        Get the type of enum values.

        Returns:
            Type of the first enum member's value.
        """
        return type(mi.first(enum.value for enum in cls.__members__.values()))

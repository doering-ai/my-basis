############
### HEAD ###
############
### STANDARD
from typing import Any, Self, cast
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
    """Enhanced Enum base class with flexible & ergonomic parsing, arithmetic, and comparison.

    This class is built to be a useful *base* more than anything, but as-is, its main strength is in
    its (de)serialization methods. A single `read()` call can parse strings (matching by name or
    regex alias), integers (for Flag enums), and lists thereof all at once,  while `write
    ()` method serializes enums back to strings, with pipe-separated names for combined flags.

    This class does not inherit from `enum.Flag` by default, but it is built with support for such
    usecases out-of-the-box; to use those those features, simply subclass both `MyEnum` and `Flag`.

    ```{note}
    Total ordering is implemented based on enum value for numeric enums, and declaration order
    otherwise -- if you want ordering based on string values, you'll have to override `__lt__()`.
    ```
    """

    @classmethod
    def read(cls, value: str | int | list | Self) -> Self:
        """Parse a value into an enum member.

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
            if uval.isdigit():
                # I.i. Cast numeric strings after trimming surrounding whitespace.
                value = int(uval)
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
            return cast('Self', cls(value))

        # III. Immediate check against values (instead of keys)
        if type(value) is cls.vtype() and (key := ut.find_key(members, lambda v: v.value == value)):
            return members[key]

        # IV. Handle lists of values
        if isinstance(value, list):
            if not issubclass(cls, Flag):
                raise ValueError(f'{cls.__name__} does not support combined values.')
            # Pyrefly narrows `cls` to `Flag` here and loses the `MyEnum` side of the
            # multiple-inheritance contract, even though every runtime subclass has `read`.
            read = cls.read  # pyrefly: ignore[missing-attribute]
            return cast('Self', cls(sum(val.value for val in map(read, value))))

        raise ValueError(f'Invalid {cls.__name__} value: {value}')

    def write(self) -> str:
        """Convert enum member to string representation.

        Returns:
            String value, lowercase name, or pipe-separated flags for Flag enums.
        """
        if isinstance(self.value, str):
            return self.value
        elif self.name:
            return self.name.lower()
        elif isinstance(self, Flag):
            return '|'.join(flag.name for flag in self if flag.name)
        else:
            return str(self)

    def __str__(self) -> str:
        return self.write()

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}.{self.name}' if self.name else super().__repr__()

    def __sub__(self, other: Self | str | int | list) -> Self:
        cls = self.__class__
        if not isinstance(other, cls):
            other = cls.read(other)
        if isinstance(self, Flag):
            return cast('Self', self & ~cast('Any', other))
        return cast('Self', cls(self.value - other.value))

    def __isub__(self, other: Self | str | int | list) -> Self:
        return self - other

    def __add__(self, other: Self | str | int | list) -> Self:
        cls = self.__class__
        if not isinstance(other, cls):
            other = cls.read(other)
        if isinstance(self, Flag):
            return cast('Self', self | cast('Any', other))
        return cast('Self', cls(self.value + other.value))

    def __iadd__(self, other: Self | str | int | list) -> Self:
        return self + other

    @property
    def parts(self) -> list[Self]:
        """The component members of Flag unions, else just `[self]`."""
        if not isinstance(self, Flag):
            return [self]
        else:
            return [cast('Self', flag) for flag in self]

    @property
    def base(self) -> Self:
        """Return the first/primary part of a Flag enum, or self for regular enums.

        Returns:
            First flag component or self.
        """
        return parts[0] if (parts := self.parts) else self

    def __lt__(self, other: Self | str | int | list) -> bool:
        cls = self.__class__
        if not isinstance(other, cls):
            other = cls.read(other)

        lhs = self.base
        rhs = other.base  # type: ignore
        if isinstance(lhs.value, int | float):
            return lhs.value < rhs.value
        else:
            # Else find each of the members index in the overall ordering
            members = list(self.__class__)
            return members.index(self) < members.index(other)

    @ft.lru_cache(maxsize=1)
    @staticmethod
    def _aliases() -> dict[str, re.Pattern]:
        """Define regex patterns for parsing aliases.

        Override in subclasses to provide custom alias matching.

        Returns:
            Dict mapping member names to alias regex patterns.
        """
        return {}

    @classmethod
    def vtype(cls) -> type:
        """Get the type of enum values.

        Returns:
            Type of the first enum member's value.
        """
        return type(mi.first(enum.value for enum in cls.__members__.values()))

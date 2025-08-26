############
### HEAD ###
############
### STANDARD
from typing import TypeVar
from enum import Enum, Flag
import more_itertools as mi
import functools as ft

### EXTERNAL

### INTERNAL
from ..base import utils as ut

SubType = TypeVar('SubType', bound='MyEnum')


############
### DATA ###
############
@ft.total_ordering
class MyEnum(Enum):
    @classmethod
    def read(cls: type[SubType], value: str | int | list) -> SubType:
        members = cls.__members__

        if type(value) is type(mi.first(members.values())):
            if key := ut.find_key(members, lambda v: v.value == value):
                # IV. Find by value
                return members[key]

        if isinstance(value, str):
            uval = value.upper()
            if value.isdigit():
                # 0. Cast numbers for int flags
                value = int(value)
            elif uval in members:
                # I. Find by name
                return members[uval]
            elif issubclass(cls, Flag) and '|' in value:
                # II. Break down flags into a list
                value = value.split('|')

        if isinstance(value, list):
            # 0. Handle lists of values
            assert issubclass(cls, Flag)
            values = [members.get(_v.strip().upper(), cls(0)) for _v in value]
            return cls(sum(val.value for val in values))

        if isinstance(value, int) and issubclass(cls, Flag):
            # III. Handle int flags
            return cls(value)

        raise ValueError(f'Invalid {cls.__name__} value: {value}')

    def write(self) -> str:
        if self.value and isinstance(self.value, str):
            return self.value
        elif self.name:
            return self.name.lower()
        elif isinstance(self, Flag):
            return '|'.join([
                flag.name for flag in type(self) if flag.name and self.value & flag.value
            ])
        else:
            return str(self)

    def __sub__(self: SubType, other: SubType) -> SubType:
        cls = self.__class__
        if issubclass(cls, Flag) and isinstance(other, cls):
            return self & ~other  # type: ignore
        return self.__class__(self.value - other.value)

    def __isub__(self: SubType, other: SubType) -> SubType:
        return self - other

    def __add__(self: SubType, other: SubType) -> SubType:
        cls = self.__class__
        if issubclass(cls, Flag) and isinstance(other, cls):
            return self | other  # type:ignore
        return self.__class__(self.value + other.value)

    def __iadd__(self: SubType, other: SubType) -> SubType:
        return self + other

    @property
    def parts(self: SubType) -> list[SubType]:
        if not isinstance(self, Flag):
            return [self]
        else:
            return list(self) or []

    @property
    def base(self: SubType) -> SubType:
        """ Returns the base part of the enumeration, if applicable. """
        return parts[0] if (parts := self.parts) else self

    def __lt__(self: SubType, other: SubType) -> bool:
        lhs = self.base
        if isinstance(lhs.value, int | float):
            return lhs.value < other.base.value
        else:
            # Else find each of the members index in the overall ordering
            members = list(self.__class__)
            return members.index(self) < members.index(other)

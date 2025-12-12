############
### HEAD ###
############
### STANDARD
from typing import ClassVar, Self
import functools as ft

### EXTERNAL
import regex as re

### INTERNAL
from .meta_patterns import META_RGXS


############
### BODY ###
############
@ft.total_ordering
class Quantifier:
    RGX: ClassVar[re.Pattern] = META_RGXS['quant']

    data: str

    # -------------------
    # `0` Initial Methods
    # -------------------
    def __init__(self, data: str = '') -> None:
        assert self.RGX.fullmatch(data), f'Invalid quantifier: {data!r}'
        self.data = data

    def copy(self) -> Self:
        return self.__class__(self.data)

    # -------------------
    # `-` Private Methods
    # -------------------

    # -------------------
    # `+` Primary Methods
    # -------------------
    def join(self, other: str | Self) -> Self | None:
        """
        Create a copy of this atom with the given quantifier applied. Any existing quantifier is
        dropped.
        """
        cls = self.__class__
        if isinstance(other, str):
            other = cls(other)
        lhs, rhs = self.data, other.data

        # I. Handle trivial cases
        if not lhs:
            return cls(rhs)
        elif not rhs:
            return cls(lhs)

        # II. Skip redundant quantifiers
        if lhs == rhs and rhs in ('?', '*', '+'):
            return cls(lhs)

        # III. Make optional
        if (rhs == '?' and (opt := self.as_optional()) is not None) or (
            lhs == '?' and (opt := other.as_optional()) is not None
        ):
            return opt

        # IV. Indicate that the quantifiers need to be combined with nested groups
        return None

    def as_optional(self) -> Self | None:
        cls = self.__class__
        if self.is_optional:
            return self.copy()
        elif self.data == '':
            return cls('?')
        elif self.data.startswith('{1'):
            return cls('{0' + self.data[3:])
        elif self.data[0] == '+':
            return cls('*' + self.data[1:])
        else:
            # IV. Indicate that this quantifier can not trivially be made optional
            return None

    def as_required(self) -> Self:
        cls = self.__class__
        if not self.is_optional:
            return self.copy()
        elif self.data == '?':
            return cls('')
        elif self.data.startswith('{0'):
            return cls('{1' + self.data[3:])
        elif self.data[0] == '*':
            return cls('+' + self.data[1:])
        else:
            raise RuntimeError(f'Unhandled optional quantifier: {self.data!r}')

    # ------------------
    # `x` Public Methods
    # ------------------
    def __bool__(self) -> bool:
        return bool(self.data)

    def __str__(self) -> str:
        return self.data

    def __contains__(self, item: str) -> bool:
        return item == self.data

    def __len__(self) -> int:
        return len(self.data)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, (str, Quantifier)):
            return self.data == (other.data if isinstance(other, Quantifier) else other)
        else:
            return False

    def __lt__(self, other: object) -> bool:
        if isinstance(other, (str, Quantifier)):
            return self.data < (other.data if isinstance(other, Quantifier) else other)
        else:
            raise TypeError(f'Unsupported type for Quantifier comparison: {type(other)}')

    def startswith(self, prefix: str) -> bool:
        return self.data.startswith(prefix)

    def endswith(self, suffix: str) -> bool:
        return self.data.endswith(suffix)

    def __getitem__(self, key: slice | int) -> str:
        return self.data[key]

    @ft.cached_property
    def is_simple(self) -> bool:
        return self.data in ('', '?')

    @ft.cached_property
    def is_optional(self) -> bool:
        return bool(self.data) and (
            self.data == '?' or self.data.startswith('{0,') or self.data.startswith('*')
        )

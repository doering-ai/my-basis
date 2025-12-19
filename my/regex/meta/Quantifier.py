############
### HEAD ###
############
### STANDARD
from typing import ClassVar, Self, Literal
import functools as ft

### EXTERNAL
from pydantic_core import core_schema as pyds
import regex as re

### INTERNAL
from .meta_patterns import META_RGXS


############
### BODY ###
############
@ft.total_ordering
class Quantifier:
    RGX: ClassVar[re.Pattern] = META_RGXS['quant']
    Modes: ClassVar = Literal['try', 'overwrite', 'join']

    data: str = ''

    # -------------------
    # `0` Initial Methods
    # -------------------
    def __init__(self, data: str | Self = '') -> None:
        if isinstance(data, Quantifier):
            self.data = data.data
        elif data := data.lstrip(')'):
            assert self.RGX.fullmatch(data), f'Invalid quantifier: {data!r}'
            self.data = data

    @classmethod
    def __get_pydantic_core_schema__(cls, source: type, handler) -> pyds.CoreSchema:
        return pyds.no_info_before_validator_function(cls, pyds.is_instance_schema(cls))

    # -------------------
    # `-` Private Methods
    # -------------------

    # -------------------
    # `+` Primary Methods
    # -------------------
    def join(self, other: str | Self) -> Self | None:
        """
        Create a copy of this quantifier with the given quantifier applied. If the two quantifiers
        cannot be simply combined, return `None` to indicate that nested groups are needed.
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
            return cls(self)
        elif self == '':
            return cls('?')
        elif self.startswith('{1'):
            return cls('{0' + self[2:])
        elif self.startswith('+'):
            return cls('*' + self[1:])
        else:
            # IV. Indicate that this quantifier can not trivially be made optional
            return None

    def as_required(self) -> Self:
        cls = self.__class__
        if not self.is_optional:
            return cls(self)
        elif self == '?':
            return cls('')
        elif self.startswith('{0'):
            return cls('{1' + self[2:])
        elif self.startswith('*'):
            return cls('+' + self[1:])
        else:
            raise RuntimeError(f'Unhandled optional quantifier: {self.data!r}')

    # ------------------
    # `x` Public Methods
    # ------------------
    # --------------
    # `x0` Overrides
    # --------------
    def __bool__(self) -> bool:
        return len(self.data) > 0

    def __str__(self) -> str:
        return self.data

    def __repr__(self) -> str:
        return f'Quantifier({self.data!r})'

    def __hash__(self) -> int:
        return hash(self.data)

    def __contains__(self, item: str) -> bool:
        return item == self.data

    def __len__(self) -> int:
        return len(self.data)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.data == other
        elif isinstance(other, Quantifier):
            return self.data == other.data
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

    def __or__(self, other: str | Self) -> Self | None:
        return self.join(other)

    # ---------------
    # `x1` Properties
    # ---------------
    @ft.cached_property
    def is_simple(self) -> bool:
        return self.data in ('', '?')

    @ft.cached_property
    def is_optional(self) -> bool:
        return bool(self.data) and (
            self.data == '?' or self.data.startswith('{0,') or self.data.startswith('*')
        )

    @ft.cached_property
    def is_greedy(self) -> bool:
        return len(self) <= 1 or not self.data.endswith('?')

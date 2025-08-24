############
### HEAD ###
############
# Standard imports
from typing import ClassVar, Iterator
import functools as ft
import more_itertools as mi

# External imports
import regex as re
import pydantic as pyd

# Internal imports

############
### DATA ###
############
HASH_TRANS = str.maketrans('ab', '89')


############
### BODY ###
############
class Idx(pyd.RootModel):
    root: str

    RGX: ClassVar[re.Pattern] = re.compile(r'^([0123]{0,3}[ab]?|[0123]{4})$')

    @pyd.field_validator('root', mode='before')
    @classmethod
    def validate_idx(cls, val: str) -> str:
        assert cls.is_valid(val)
        return val

    @classmethod
    def new(cls, val: 'str|int|Idx' = '') -> "Idx":
        if isinstance(val, str):
            return cls(val.strip())
        elif isinstance(val, int):
            return cls(str(val))
        elif isinstance(val, Idx):
            return val
        else:
            raise ValueError(f"Invalid index type: {type(val).__name__}")

    @classmethod
    def is_valid(cls, val: str) -> bool:
        return cls.RGX.match(val) is not None

    @ft.cached_property
    def complexity(self) -> int:
        return len(self.root) if self.is_concrete else len(self.root) - 1

    @ft.cached_property
    def is_concrete(self) -> bool:
        return self.root.isdigit() or not self.root

    @ft.cached_property
    def is_actual(self) -> bool:
        return self.complexity == 4

    @ft.cached_property
    def base(self) -> 'Idx':
        """Returns the base index, which is the index without any abstract suffixes."""
        return self if self.is_concrete else self - 1

    def __contains__(self, other: 'Idx|str') -> bool:
        """ Determines whether other is a descendant of self. """
        rhs = Idx.new(other)
        if len(self) == 0 or self == rhs:
            return True
        elif self.complexity > rhs.complexity:
            return False
        else:
            return self in rhs.ancestors

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.root == other
        elif isinstance(other, Idx):
            return self.root == other.root
        else:
            raise TypeError(f"Cannot compare Idx to {type(other)}")

    def __ne__(self, other: object) -> bool:
        return not (self == other)

    def __lt__(self, other: "Idx|str") -> bool:
        """
        This is *similar* to a straight lexigraphical ordering, but with one caveat: abstract files
        are marked with an "a" or "b" at the end of the index, and they precede (are lower than) 
        their concrete siblings.

        E.g. a < b < 0 < 0a < 0b < 00 < 1 < 1a < ...
        """
        if isinstance(other, str):
            other = Idx(other)
        if self == other:
            return False

        if self.is_concrete == other.is_concrete:
            return self.root < other.root
        elif self.is_concrete:
            return self.base.root <= other.base.root
        else:
            return self.base.root < other.base.root

    def __gt__(self, other: "Idx|str") -> bool:
        return not (self == other or self < other)

    def __le__(self, other: "Idx|str") -> bool:
        return self == other or self < other

    def __ge__(self, other: "Idx|str") -> bool:
        return self == other or self > other

    def __repr__(self) -> str:
        return f"`{self.root}`"

    def __str__(self) -> str:
        return self.root

    toString = __str__

    def __hash__(self) -> int:
        return hash(self.root.translate(HASH_TRANS))

    def __len__(self) -> int:
        return len(self.root)

    def __bool__(self) -> bool:
        return len(self) != 0

    def __getitem__(self, key: int | slice) -> str:
        return self.root[key]

    def __add__(self, other: "Idx|str") -> "Idx":
        if isinstance(other, str):
            return Idx(self.root + other)
        elif isinstance(other, Idx):
            return Idx(self.root + other.root)
        else:
            raise TypeError(f"Cannot add Idx to {type(other)}")

    def __sub__(self, num: int) -> "Idx":
        if num == 0:
            return self
        elif num >= len(self):
            return Idx.new()
        else:
            assert 0 < num < len(self), f"Invalid subtraction length for {self.root}: {num}"
            return Idx.new(self.root[:-num])

    # ---------------
    # Tree Properties
    # ---------------
    @ft.cached_property
    def parent(self) -> 'Idx':
        if not self:
            return self

        base = self - 1
        last = self[-1]
        if last in '01':
            return base + 'a'
        elif last in '23':
            return base + 'b'
        else:
            return base

    @ft.cached_property
    def concrete_parent(self) -> 'Idx':
        return self - 1

    @ft.cached_property
    def children(self) -> list['Idx']:
        if self.is_actual:
            return []
        elif self.is_concrete:
            digits = 'ab'
        elif self[-1] == 'a':
            digits = '01'
        else:
            digits = '23'

        return [self.base + d for d in digits]

    @ft.cached_property
    def concrete_children(self) -> list['Idx']:
        if self.is_concrete and not self.is_actual:
            return [self + d for d in '0123']
        else:
            return self.children

    @property
    def ancestors(self) -> Iterator['Idx']:
        if parent := self.parent:
            yield from parent.ancestors
            yield parent

    @property
    def concrete_ancestors(self) -> Iterator['Idx']:
        if parent := self.concrete_parent:
            yield from parent.concrete_ancestors
            yield parent

    @property
    def descendants(self) -> Iterator['Idx']:
        """
        Calculate all the nodes "below" this one in the architectonic that extend it, listing the
        results in depth-first order.
        """
        for child in self.children:
            yield child
            yield from child.descendants

    @property
    def concrete_descendants(self) -> Iterator['Idx']:
        for child in self.concrete_children:
            yield child
            yield from child.concrete_descendants

    @property
    def parts(self) -> tuple[str, str, str, str]:
        """Returns the four parts of the index as a tuple of integers."""
        ret = list(mi.padded(self.root, '', 4))
        assert len(ret) == 4
        return ret[0], ret[1], ret[2], ret[3]

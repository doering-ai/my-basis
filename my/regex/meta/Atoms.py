############
### HEAD ###
############
### STANDARD
from typing import Iterator, Self, Sequence, ClassVar
import functools as ft
import more_itertools as mi

### EXTERNAL

### INTERNAL
from .meta_patterns import META_RGXS
from .Quantifier import Quantifier
from .Atom import Atom


############
### DATA ###
############
@ft.total_ordering
class Atoms:
    SPLITTER: ClassVar[Atom] = Atom(r'|')

    data: list[Atom] = []

    # -------------------
    # `0` Initial Methods
    # -------------------
    def __init__(self, *args: str | Atom | Sequence[Atom] | Iterator[Atom] | Self) -> None:
        self.data = []
        for arg in args:
            if isinstance(arg, Atom):
                self.data.append(arg)
            elif isinstance(arg, Atoms):
                self.data.extend(arg.data)
            elif isinstance(arg, str):
                self.data.extend(Atom.atomize(arg))
            elif isinstance(arg, (Sequence | Iterator)):
                self.data.extend(map(Atom, arg))
            else:
                raise TypeError(f'Unsupported type for Atoms initialization: {type(arg)}')

    @classmethod
    def atomize(cls, expr: str | Self, escape: bool = False) -> Self:
        """
        Break a regex expression into its atomic components.

        Args:
            expr: The raw regular expression string to atomize.
            escape: If set, escape characters matching RGXS['special_characters'].
        Returns:
            Tuple of atomic regex components (characters, groups, character sets, etc.).
        """
        if isinstance(expr, cls):
            return expr
        if escape:
            expr = META_RGXS['special_characters'].sub(r'\\\1', expr)
        return cls(Atom.atomize(expr))

    @classmethod
    def empty(cls) -> Self:
        return cls(Atom())

    def copy(self) -> Self:
        return self.__class__(self.data.copy())

    # -------------------
    # `-` Private Methods
    # -------------------

    # -------------------
    # `+` Primary Methods
    # -------------------

    # ------------------
    # `x` Public Methods
    # ------------------
    # --------------
    # `x0` Overrides
    # --------------
    def __len__(self) -> int:
        return len(self.data)

    def __str__(self) -> str:
        return ''.join(map(str, self.data))

    def __repr__(self) -> str:
        return f'{self.data!r}'

    def __hash__(self) -> int:
        return hash(tuple(self.data))

    def __bool__(self) -> bool:
        return len(self.data) > 0 and any(map(bool, self.data))

    @ft.singledispatchmethod
    def __getitem__(self, key):
        raise TypeError(f'Unsupported type for Atoms indexing: {type(key)}')

    @__getitem__.register
    def _get_pos(self, key: int) -> Atom:
        return self.data[key]

    @__getitem__.register
    def _get_slice(self, key: slice) -> Self:
        return self.__class__(self.data[key])

    @ft.singledispatchmethod
    def __setitem__(self, key, value):
        raise TypeError(f'Unsupported types for Atoms assignment: {type(key)}, {type(value)}')

    @__setitem__.register
    def _set_pos(self, key: int, value: str | Atom) -> None:
        if isinstance(value, str):
            value = mi.one(Atom.atomize(value))
        self.data[key] = value

    @__setitem__.register
    def _set_slice(self, key: slice, value: str | Sequence[Atom] | Self) -> None:
        if isinstance(value, str):
            value = self.atomize(value)

        if isinstance(value, Atoms):
            self.data[key] = value.data
        elif isinstance(value, Sequence):
            self.data[key] = list(map(Atom, value))
        else:
            raise TypeError(f'Unsupported type for Atoms assignment: {type(value)}')

    def __add__(self, other: object) -> Self:
        cls = self.__class__
        if isinstance(other, (str, Atom, Sequence, Atoms)):
            return cls(self.data + cls(other).data)
        else:
            raise TypeError(f'Unsupported type for Atoms addition: {type(other)}')

    def __lt__(self, other: object) -> bool:
        if isinstance(other, (str, Atom, Sequence, Atoms)):
            return self.data < self.__class__(other).data
        else:
            raise TypeError(f'Unsupported type for Atoms comparison: {type(other)}')

    def __iter__(self) -> Iterator[Atom]:
        return iter(self.data)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, (str, Atom, Sequence, Atoms)):
            return self.data == self.__class__(other).data
        else:
            return False

    def __contains__(self, item: object) -> bool:
        if isinstance(item, Atom):
            return item in self.data
        elif isinstance(item, str):
            return Atom(item) in self.data
        else:
            return False

    # ---------------
    # `x1` Properties
    # ---------------
    @property
    def first(self) -> Atom:
        return self.data[0] if self else Atom()

    @property
    def one(self) -> Atom:
        assert len(self) == 1, 'Atoms.one called on Atoms with length != 1'
        return self.data[0]

    # ------------
    # `x2` Methods
    # ------------
    @classmethod
    def quantify(
        cls,
        expr: str | Self,
        quantifier: str | Quantifier,
        overwrite: bool = False,
    ) -> Self:
        """
        Create a version of the given pattern that has the request quantifier applied.
        Handles patterns that need to be wrapped before a quantifier is applied.

        Args:
            expr: The regex pattern body to quantify.
            quantifier: The quantifier string to apply (e.g., '?', '+', '*', '{2,5}').
        Returns:
            The quantified regex pattern string.
        """
        atoms = Atoms.atomize(expr) if isinstance(expr, str) else expr
        assert isinstance(atoms, cls), f'Unsupported type for quantify: {type(atoms)}'

        # Edge & null cases
        if not atoms:
            return cls()
        elif not quantifier:
            return atoms
        elif len(atoms) == 1:
            return cls(atoms.first.quantify(quantifier, overwrite=overwrite))

        # Base case: Must wrap multi-atom expression in a new group
        return cls(Atom(f'(?:{atoms}){quantifier}'))

    @classmethod
    def is_split(cls, expr: str | Self) -> bool:
        return Atom('|') in (cls._atomize_iter(expr) if isinstance(expr, str) else expr)

    @classmethod
    def is_atomic(cls, expr: str | Atom | Self) -> bool:
        if isinstance(expr, Atom):
            return True
        elif isinstance(expr, Atoms):
            return len(expr) == 1
        elif isinstance(expr, str):
            return Atom.is_atomic(expr)
        else:
            raise TypeError(f'Unsupported type for is_atomic check: {type(expr)}')

    def split(self) -> Iterator[Self]:
        """
        Split the Atoms instance into branches at top-level '|' atoms.

        Yields:
            Atoms instances representing alternate branches.
        """
        yield from map(Atoms, mi.split_at(self.data, lambda atom: atom == self.SPLITTER))

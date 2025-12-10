############
### HEAD ###
############
### STANDARD
from typing import Iterator, Self, Sequence, overload
import functools as ft
import more_itertools as mi

### EXTERNAL
import pydantic as pyd

### INTERNAL
from .Atom import Atom
from .meta_patterns import META_RGXS


############
### DATA ###
############
class Atoms(pyd.RootModel[list[Atom]]):
    # -------------------
    # `0` Initial Methods
    # -------------------
    def __init__(self, *args: str | Atom | Sequence[Atom] | Iterator[Atom] | Self) -> None:
        self.data = []
        for arg in args:
            if isinstance(arg, Atom):
                self.data.append(arg)
            elif isinstance(arg, Atoms):
                self.data.extend(arg.model_copy(deep=True))
            elif isinstance(arg, str):
                self.data.extend(Atom.parse(arg))
            elif isinstance(arg, Sequence):
                self.data.extend(map(Atom, arg))
            else:
                raise TypeError(f'Unsupported type for Atoms initialization: {type(arg)}')

    @classmethod
    @ft.lru_cache(maxsize=64)
    def atomize(cls, expr: str, escape: bool = False) -> Self:
        """
        Break a regex expression into its atomic components.

        Args:
            expr: The raw regular expression string to atomize.
            escape: If set, escape characters matching RGXS['special_characters'].
        Returns:
            Tuple of atomic regex components (characters, groups, character sets, etc.).
        """
        if escape:
            expr = META_RGXS['special_characters'].sub(r'\\\1', expr)
        return cls(Atom.parse(expr))

    # -------------------
    # `-` Private Methods
    # -------------------
    @classmethod
    def _is_split(cls, expr: str | Self) -> bool:
        if isinstance(expr, str):
            return any(atom == '|' for atom in cls._atomize_iter(expr))
        else:
            return '|' in expr

    @classmethod
    def _is_atomic(cls, expr: str | Atom | Self) -> bool:
        if isinstance(expr, Atom):
            return True
        elif isinstance(expr, Atoms):
            return len(expr) == 1
        elif isinstance(expr, str):
            return Atom.is_atomic(expr)
        else:
            raise TypeError(f'Unsupported type for is_atomic check: {type(expr)}')

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

    def __getitem__(self, key: slice | int) -> Self:
        return self.__class__(self.data[key])

    @ft.singledispatchmethod
    def __setitem__(self, key, value) -> None:
        raise TypeError(f'Unsupported types for Atoms assignment: {type(key)}, {type(value)}')

    @__setitem__.register
    def _set_pos(self, key: int, value: str | Atom) -> None:
        if isinstance(value, str):
            value = mi.one(Atom.parse(value))
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

    # ---------------
    # `x1` Properties
    # ---------------
    @property
    def is_split(self) -> bool:
        return self._is_split(self)

    @property
    def first(self) -> Atom:
        return self.data[0] if self else Atom()

    # ------------
    # `x2` Methods
    # ------------
    @classmethod
    def quantify(cls, expr: str | Self, quantifier: str) -> Self:
        """
        Create a version of the given pattern that has the request quantifier applied.
        Handles patterns that need to be wrapped before a quantifier is applied.

        Args:
            expr: The regex pattern body to quantify.
            quantifier: The quantifier string to apply (e.g., '?', '+', '*', '{2,5}').
        Returns:
            The quantified regex pattern string.
        """
        if isinstance(expr, str):
            expr = Atoms.atomize(expr)
        assert isinstance(expr, cls), f'Unsupported type for quantify: {type(expr)}'

        # Edge & null cases
        if not expr:
            return cls()
        elif not quantifier or (quantifier == '?' and all(atom.is_optional for atom in expr)):
            return expr

        # Base case: Must wrap multi-atom expression in a new group
        return cls(Atom(f'(?:{expr}){quantifier}'))

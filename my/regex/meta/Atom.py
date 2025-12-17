############
### HEAD ###
############
### STANDARD
from typing import Self, Generator, Any
import functools as ft

### EXTERNAL
import pydantic as pyd

### INTERNAL
from .meta_patterns import META_RGXS
from .Quantifier import Quantifier


############
### BODY ###
############
@ft.total_ordering
class Atom(pyd.BaseModel):
    data: str = r''

    # -------------------
    # `0` Initial Methods
    # -------------------
    def __init__(self, data: str | Self = '', *args: Any, **kwargs: Any) -> None:
        if isinstance(data, Atom):
            kwargs = data.model_dump() | kwargs
        else:
            kwargs['data'] = str(data)
        super().__init__(*args, **kwargs)

    @classmethod
    def plain_atomize(cls, expr: str) -> Generator[Self, None, None]:
        """
        Transform the given expression text into a series of atom objects.
        This function is "plain" because it does NOT handle groups or sets -- the caller must
        guarantee that neither type of atom appears in the snippet before calling this function.

        For general-purpose atomization, see Regex.atomize().
        """
        yield from map(cls, META_RGXS['atom'].findall(expr))

    # -------------------
    # `-` Private Methods
    # -------------------
    @staticmethod
    def _normalize_other_atom(param: object) -> str:
        return param.data if isinstance(param, Atom) else str(param)

    @staticmethod
    def _has_set_operator(data) -> bool:
        return bool(META_RGXS['set_operator'].search(data))

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
        return self.data

    def __repr__(self) -> str:
        return f'{self.data!r}'

    def __hash__(self) -> int:
        return hash(self.data)

    def __eq__(self, other: object) -> bool:
        return self.data == self._normalize_other_atom(other)

    def __lt__(self, other: object) -> bool:
        return self.data < self._normalize_other_atom(other)

    def __contains__(self, item: object) -> bool:
        return self._normalize_other_atom(item) in self.data

    def __add__(self, other: object) -> Self:
        cls = self.__class__
        return cls(self.data + self._normalize_other_atom(other))

    def __radd__(self, other: object) -> Self:
        cls = self.__class__
        return cls(self._normalize_other_atom(other) + self.data)

    def __bool__(self) -> bool:
        return bool(self.data)

    def __getitem__(self, key: slice | int) -> Self:
        cls = self.__class__
        return cls(self.data[key])

    # ---------------
    # `x1` Properties
    # ---------------
    @ft.cached_property
    def quantifier(self) -> Quantifier:
        """Extracts the quantifier (if any) applied to this atom."""
        if len(self) >= 2:
            if self.is_group:
                # I. Look for quantifier after the closing ')'
                return Quantifier(self.data.rsplit(')', 1)[-1])
            elif match := META_RGXS['quant'].search(self.data):
                # II. Otherwise, just search with a regex that only matches at the end of the string
                return Quantifier(match[0])
        return Quantifier()

    @ft.cached_property
    def is_optional(self) -> bool:
        """Determines if this atom has an optional quantifier (e.g. '?', '*', '{0,3}')."""
        return self.quantifier.is_optional

    @ft.cached_property
    def is_group(self) -> bool:
        """Determines if this atom is a group (e.g. '(?:abc)')."""
        return len(self) > 0 and self.data[0] == '('

    @ft.cached_property
    def is_set(self) -> bool:
        """Determines if this atom is a character set (e.g. '[A-Za-z]')."""
        return len(self) >= 3 and self.data[0] == '['

    @ft.cached_property
    def is_simple(self) -> bool:
        """
        Determine if this atom is 'simple', i.e. a single symbol with no grouping, set, or complex
        quantifier. Useful for isomorphic transformations.
        """
        return (
            bool(self)
            and self.quantifier.is_simple
            and not self.is_group
            and not (self.is_set and self._has_set_operator(self.data))
        )

    # ------------
    # `x2` Methods
    # ------------
    def quantify(self, quantifier: str | Quantifier, overwrite: bool = True) -> Self:
        """
        Create a copy of this atom with the given quantifier applied.

        Args:
            quantifier: The quantifier string to apply (e.g., '?', '+', '*', '{2,5}').
            overwrite: Whether to overwrite any existing quantifier (default True).
        Returns:
            The quantified atom (the original object is NOT modified).
        """
        val = self.data
        if n_quant := len(self.quantifier):
            if self.quantifier == quantifier and quantifier in ('?', '*', '+'):
                # I.i. Skip redundant quantifiers
                return self
            elif overwrite:
                # I.ii. Remove the existing quantifier
                val = val[:-n_quant]
            elif quantifier:
                # I.iii. Add the new quantifier to the whole existing atom with a wrapping group
                val = f'(?:{val})'
        return self.__class__(val + str(quantifier))

    def as_optional(self) -> Self:
        """Generate a copy of this atom with its quantifier made optional (default '?')."""
        if opt := self.quantifier.as_optional():
            return self.quantify(opt)
        else:
            return self.quantify('?', overwrite=False)

    def as_required(self) -> Self:
        """Generate a copy of this atom with its quantifier made non-optional (default '')."""
        return self.quantify(self.quantifier.as_required())

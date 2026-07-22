############
### HEAD ###
############
### STANDARD
from typing import Self, Any, ClassVar
from collections.abc import Generator
import functools as ft

### EXTERNAL
import pydantic as pyd

### INTERNAL
from .meta_rgxs import META_RGXS
from .Quantifier import Quantifier


############
### BODY ###
############
@ft.total_ordering
class Atom(pyd.BaseModel):
    r"""An immutable, atomic element of a regex expression (e.g. characters, sets, & groups).

    Collections (sets and groups) can be broken down further in a way by identifying their
    alternating matches, but all atoms nonetheless share the quality of being indivisible in the
    context of the original expression that contains them.

    Examples:
        Inspect an atom's parts and shape::

            >>> atom = Atom(r'\d{2,4}')
            >>> atom.base, str(atom.quantifier)
            ('\\d', '{2,4}')
            >>> Atom(r'(?:ab)+').is_group, Atom(r'[ab]').is_set
            (True, True)
    """

    GroupAtom: ClassVar[type['Atom']]
    SetAtom: ClassVar[type['Atom']]

    data: str = r''

    # -------------------
    # `.` Initial Methods
    # -------------------
    def __init__(self, data: str | Self = '', *args: Any, **kwargs: Any) -> None:
        """Create a new Atom instance from a raw substring."""
        if isinstance(data, Atom):
            kwargs = data.model_dump() | kwargs
        else:
            kwargs['data'] = data
        super().__init__(*args, **kwargs)

    @classmethod
    def __init_subclass__(cls) -> None:
        name = cls.__name__
        if name == 'GroupAtom':
            Atom.GroupAtom = cls
        elif name == 'SetAtom':
            Atom.SetAtom = cls

    @classmethod
    def plain_atomize(cls, expr: str) -> Generator[Self]:
        r"""Iteratively generate *plain* atoms from the given expression.

        .. important::
            This function is "plain" because it does NOT handle groups or sets -- the caller must
            guarantee that neither type of atom appears in the snippet before calling this function.

        For general-purpose atomization, see `Regex.atomize()`.

        Args:
            expr: The regex expression snippet to atomize.
        Yields:
            Atom objects representing each atomic element in the expression.
        Examples:
            Break a group-free snippet into its atoms::

                >>> list(Atom.plain_atomize(r'ab\d+c?'))
                ['a', 'b', '\\d+', 'c?']
        """
        yield from map(cls, META_RGXS['atom'].findall(expr))

    # -------------------
    # `-` Private Methods
    # -------------------
    @staticmethod
    def _has_set_operator(data: str) -> bool:
        return bool(META_RGXS['set_operator'].search(data))

    # -------------------
    # `+` Primary Methods
    # -------------------
    # ------------------
    # `*` Public Methods
    # ------------------
    # --------------
    # `*0` Overrides
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
        return self.data == str(other)

    def __lt__(self, other: object) -> bool:
        if isinstance(other, Atom):
            _o = other.base
        elif other is None:
            _o = ''
        else:
            _o = str(other)

        if self.base == _o:
            if self != other:
                if isinstance(other, Atom):
                    return self.quantifier < other.quantifier
                else:
                    return True
            return False
        return self.base < _o

    def __contains__(self, item: object) -> bool:
        return str(item) in self.data

    def __add__(self, other: object) -> Self:
        cls = self.__class__
        return cls(self.data + str(other))

    def __radd__(self, other: object) -> Self:
        cls = self.__class__
        return cls(str(other) + self.data)

    def __bool__(self) -> bool:
        return bool(self.data)

    def __getitem__(self, key: slice | int) -> Self:
        cls = self.__class__
        return cls(self.data[key])

    # ---------------
    # `*1` Properties
    # ---------------
    @ft.cached_property
    def quantifier(self) -> Quantifier:
        """The quantifier applied to this atom, empty if it has none."""
        ret = ''
        if len(self) <= 1:
            pass
        elif self.is_group:
            ret = self.data.rsplit(')', 1)[-1]
        elif self.is_set:
            ret = self.data.rsplit(']', 1)[-1]
        elif match := META_RGXS['quant'].search(self.data):
            ret = match[0]

        return Quantifier(ret)

    @ft.cached_property
    def base(self) -> str:
        """The unqualified 'base' text of this atom, i.e. its data without any quantifier."""
        return self.data[: -len(self.quantifier)] if self.quantifier else self.data

    @ft.cached_property
    def is_optional(self) -> bool:
        """Whether this atom has an optional quantifier (e.g. `?`, `*`, `{0,3}`)."""
        return self.quantifier.is_optional

    @ft.cached_property
    def is_group(self) -> bool:
        """Whether this atom is a group (e.g. ``(?:abc)``)."""
        return len(self) > 0 and self.data[0] == '('

    @ft.cached_property
    def is_set(self) -> bool:
        """Whether this atom is a character set (e.g. `[A-Za-z]`)."""
        return len(self) >= 3 and self.data[0] == '['

    @ft.cached_property
    def is_simple(self) -> bool:
        """Whether this atom is 'simple': a single literal w/ no repeating quantifier."""
        return bool(self) and self.quantifier.is_simple

    # ------------
    # `*2` Methods
    # ------------
    def quantify(self, quantifier: str | Quantifier, overwrite: bool = True) -> 'Atom':
        """Create a copy of this atom with the given quantifier applied.

        Args:
            quantifier: The quantifier string to apply (e.g. `?`, `*+`, `{2,5}`).
            overwrite: Whether to overwrite any existing quantifier; if False, the two
                quantifiers are combined instead (wrapping in a new group when necessary).
        Returns:
            A new, quantified atom (the original object is NOT modified).
        Examples:
            Apply a quantifier directly, or combine it with an existing one::

                >>> Atom('a').quantify('{2,5}')
                'a{2,5}'
                >>> Atom('a+').quantify('?', overwrite=False)
                'a*'
        """
        cls = self.__class__
        new = Quantifier(quantifier)
        if overwrite:
            return cls(f'{self.base}{new}')
        elif self.quantifier == new and (not new or new[0] in '?*+'):
            return self
        elif (joined := self.quantifier.join(new)) is not None:
            return cls(f'{self.base}{joined}')
        else:
            return Atom.GroupAtom(rf'(?:{self.data}){new}')

    def as_optional(self) -> 'Atom':
        """Generate a copy of this atom with its quantifier made optional (e.g. `a` -> `a?`)."""
        return self.quantify(r'?', overwrite=False)

    def as_required(self) -> Self:
        """Generate a copy of this atom with its quantifier made required (e.g. `a*` -> `a+`)."""
        ret = self.quantify(self.quantifier.as_required(), overwrite=True)
        assert ret is not None and isinstance(ret, self.__class__)
        return ret

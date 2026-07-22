############
### HEAD ###
############
### STANDARD
from typing import Self, ClassVar, overload
from collections.abc import Iterator, Sequence, Generator, Iterable
import functools as ft
import itertools as it
import more_itertools as mi

### EXTERNAL
from pydantic_core import core_schema as pyds

### INTERNAL
from ...types.Buffer import Buffer, PairMode
from .meta_rgxs import META_RGXS, RegexBuffer
from .GroupKind import GroupKind, NO_KIND
from .Quantifier import Quantifier
from .Atom import Atom
from .GroupAtom import GroupAtom
from .SetAtom import SetAtom


############
### BODY ###
############
@ft.total_ordering
class Regex:
    r"""A mutable representation of a regex expression, valid or otherwise.

    A Regex is essentially a list of `Atom` objects: it can be indexed, sliced, iterated,
    compared, and concatenated, and it serializes back to the raw pattern text via `str()`.

    Examples:
        Parse an expression into atoms and read its parts::

            >>> expr = Regex(r'ab(?:cd)+[ef]\d?')
            >>> list(expr)
            ['a', 'b', '(?:cd)+', '[ef]', '\\d?']
            >>> str(expr)
            'ab(?:cd)+[ef]\\d?'
    """

    SPLITTER: ClassVar[Atom] = Atom(r'|')

    data: list[Atom]

    # -------------------
    # `.` Initial Methods
    # -------------------
    def __init__(self, *args: str | Atom | Iterable[Atom] | Self) -> None:
        """Construct a new instance from a very flexible set of positional arguments."""
        self.data = list(filter(bool, mi.flatten(map(self._parse_arg, args))))

    @classmethod
    def atomize(cls, expr: str | Buffer | Self) -> Generator[Atom]:
        r"""Break a regex expression into its atomic components.

        Args:
            expr: The raw regular expression string to atomize.
        Yields:
            Atomic regex components (characters, groups, character sets, etc.), each carrying
            its quantifier.
        Examples:
            Groups and sets are atoms too, no matter how long they are::

                >>> from my import Regex
                >>> list(Regex.atomize(r'ab?(?:cd|ef)[xyz]+'))
                ['a', 'b?', '(?:cd|ef)', '[xyz]+']
        """
        if isinstance(expr, Regex):
            yield from expr.data
            return

        g_prev = 0
        for group_atom in cls.group_iterator(expr, mode='roots'):
            g0, g1 = group_atom.span
            if g0 > g_prev:
                yield from cls._set_atomize(expr[g_prev:g0])
            g_prev = g1
            yield group_atom

        if g_prev < len(expr):
            yield from cls._set_atomize(expr[g_prev:])

    @classmethod
    def _set_atomize(cls, expr: str) -> Generator[Atom]:
        s_prev = 0
        for set_atom in cls.set_iterator(expr):
            s0, s1 = set_atom.span
            if s0 > s_prev:
                yield from Atom.plain_atomize(expr[s_prev:s0])
            s_prev = s1
            yield set_atom

        if s_prev < len(expr):
            yield from Atom.plain_atomize(expr[s_prev:])

    @classmethod
    def empty(cls) -> Self:
        """Create a new 'empty' instance, holding just one empty `Atom`."""
        return cls(Atom())

    def copy(self) -> Self:
        """Create a deep copy of this Regex instance (as Atoms are immutable)."""
        return self.__class__(self.data.copy())

    @classmethod
    def __get_pydantic_core_schema__(cls, source: type, handler) -> pyds.CoreSchema:
        """Provide Pydantic with schema generation instructions for Regex.

        This allows Regex instances to be used as fields in Pydantic models.
        Accepts str or list inputs and serializes back to str.
        """

        # Validator function that converts input to Regex
        def validate_expression(value):
            return value if isinstance(value, cls) else cls(value)

        # Create validation schema that accepts str or list inputs
        python_schema = pyds.union_schema(
            [
                pyds.is_instance_schema(cls),
                pyds.no_info_after_validator_function(
                    validate_expression,
                    pyds.union_schema(
                        [
                            pyds.str_schema(),
                            pyds.list_schema(items_schema=pyds.any_schema()),
                        ]
                    ),
                ),
            ]
        )

        return pyds.json_or_python_schema(
            json_schema=pyds.no_info_after_validator_function(
                validate_expression, pyds.str_schema()
            ),
            python_schema=python_schema,
            serialization=pyds.plain_serializer_function_ser_schema(
                lambda instance: str(instance),
                return_schema=pyds.str_schema(),
            ),
        )

    # -------------------
    # `-` Private Methods
    # -------------------
    @classmethod
    def _parse_arg(cls, arg: str | Atom | Iterable[Atom] | Self) -> Iterator[Atom]:
        if isinstance(arg, Atom):
            yield arg
        elif isinstance(arg, Regex):
            yield from arg.data
        elif isinstance(arg, str):
            yield from cls.atomize(arg)
        else:
            yield from mi.flatten(map(cls._parse_arg, arg))

    # -------------------
    # `+` Primary Methods
    # -------------------
    @classmethod
    def group_iterator(
        cls,
        text: Buffer | str | list[str],
        mask: GroupKind = NO_KIND,
        mode: PairMode = 'all',
    ) -> Iterator[GroupAtom]:
        r"""Iterate over all groups in the given pattern (e.g. `(?:abc)`).

        Args:
            text: Text to search for groups (will be converted to Buffer).
            mask: Optional GroupKind filter to yield only matching group types.
            mode: 'all' by default, 'roots' to exclude nested groups, or 'leaves' for the opposite.
        Yields:
            A GroupAtom for each group found, populated with its span, kind, name, and body.
        Examples:
            Filter for one kind of group with a mask::

                >>> from my import Regex, GroupKind
                >>> groups = Regex.group_iterator(r'(?P<a>x)(?P<b>y)', mask=GroupKind.NAMED)
                >>> [group.name for group in groups]
                ['a', 'b']
        """
        # I. Cast the input text to a charset-ignoring buffer
        if isinstance(text, list):
            text = RegexBuffer(''.join(text))
        elif isinstance(text, str):
            text = RegexBuffer(text)
        assert isinstance(text, Buffer), f'Invalid text buffer: {type(text)}'
        assert 'arrays' in text.fence_rgxs, f'Invalid buffer fences: {text.fence_rgxs}'

        # II. Use the Buffer's "pair" functionality to find matching parens
        for span, start, body, _ in text.pair_iterator(META_RGXS['group'], mode):
            kind = GroupKind.read(start)
            if not mask or kind in mask:
                yield GroupAtom(
                    data=text[span[0] : span[1]], span=span, kind=kind, start=start, body=body
                )

    @classmethod
    def set_iterator(cls, text: Buffer | str | list[str]) -> Iterator[SetAtom]:
        """Find and yield all the character sets (e.g. `[A-Za-z]`) in the given text.

        Args:
            text: Text to search for character sets.
        Yields:
            A SetAtom for each root-level character set found, populated with its span and body.
        Examples:
            Iterate the sets of a pattern::

                >>> [s.body for s in Regex.set_iterator(r'[a-z]+[0-9]')]
                ['a-z', '0-9']
        """
        if isinstance(text, list):
            text = ''.join(text)
        if isinstance(text, str):
            # RegexBuffer's *exclude* sets on purpose, so don't use that constructor here
            text = Buffer.new(text, no_fence=True)
        assert isinstance(text, Buffer)

        for span, _, body, _ in text.pair_iterator(META_RGXS['set'], mode='roots'):
            yield SetAtom(data=text[span[0] : span[1]], span=span, body=body)

    # ------------------
    # `*` Public Methods
    # ------------------
    # --------------
    # `*0` Overrides
    # --------------
    def __len__(self) -> int:
        return len(self.data)

    def __str__(self) -> str:
        return ''.join(map(str, self.data))

    def __repr__(self) -> str:
        return f"r'{self}'"

    def __hash__(self) -> int:
        return hash(tuple(self.data))

    def __bool__(self) -> bool:
        return any(map(bool, self.data))

    @overload
    def __getitem__(self, key: int) -> Atom: ...

    @overload
    def __getitem__(self, key: slice) -> Self: ...

    def __getitem__(self, key: int | slice) -> Atom | Self:
        if isinstance(key, int):
            return self.data[key]
        return self.__class__(self.data[key])

    @overload
    def __setitem__(self, key: int, value: str | Atom) -> None: ...

    @overload
    def __setitem__(self, key: slice, value: str | Sequence[Atom] | Self) -> None: ...

    def __setitem__(self, key: int | slice, value: str | Atom | Sequence[Atom] | Self) -> None:
        if isinstance(key, int):
            if isinstance(value, str):
                value = mi.one(self.atomize(value))
            self.data[key] = value  # type: ignore
        else:
            if isinstance(value, str):
                self.data[key] = list(self.atomize(value))
            elif isinstance(value, Regex):
                self.data[key] = value.data
            elif isinstance(value, Sequence):
                self.data[key] = list(map(Atom, value))
            else:
                raise TypeError(f'Unsupported type for Regex assignment: {type(value)}')

    def __add__(self, other: object) -> Self:
        cls = self.__class__
        if isinstance(other, (str, Atom, Sequence, Regex)):
            return cls(self.data + cls(other).data)
        else:
            raise TypeError(f'Unsupported type for Regex addition: {type(other)}')

    def __lt__(self, other: object) -> bool:
        cls = self.__class__
        if isinstance(other, cls):
            return self.data < other.data
        elif isinstance(other, (str, Atom, Sequence)):
            return self.data < cls(other).data
        else:
            raise TypeError(f'Unsupported type for Regex comparison: {type(other)}')

    def __iter__(self) -> Iterator[Atom]:
        return iter(self.data)

    def __eq__(self, other: object) -> bool:
        cls = self.__class__
        if isinstance(other, cls):
            return self.data == other.data
        elif isinstance(other, (str, Atom, Sequence)):
            return self.data == cls(other).data
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
    # `*1` Properties
    # ---------------
    @property
    def first(self) -> Atom:
        """The first Atom in this expression, or an empty Atom if this expression is empty."""
        return self.data[0] if self else Atom()

    @property
    def last(self) -> Atom:
        """The last Atom in this expression, or an empty Atom if this expression is empty."""
        return self.data[-1] if self else Atom()

    @property
    def one(self) -> Atom:
        """The sole Atom in this expression, or an empty Atom if this expression is empty."""
        assert len(self) <= 1, 'Regex.one called on Regex with length != 1'
        return self.data[0] if self else Atom()

    @property
    def spans(self) -> list[tuple[int, int]]:
        """The raw-text (start, end) spans of each Atom in this expression."""
        ends = list(it.accumulate(map(len, self.data)))
        starts = [0, *ends[:-1]]
        return list(zip(starts, ends, strict=True))

    # ------------
    # `*2` Methods
    # ------------
    def quantify(self, quantifier: str | Quantifier, overwrite: bool = False) -> Self:
        """Create a new version of this expression that has the requested quantifier applied to it.

        Handles patterns that need to be wrapped before a quantifier is applied.

        Args:
            quantifier: The quantifier string to apply (e.g. `?`, `+`, `*`, `{2,5}`).
            overwrite: Whether to replace an existing expr-level quantifier rather than wrapping it.
        Returns:
            A new, quantified Regex (the original is NOT modified).
        Examples:
            Multi-atom expressions are wrapped before quantification; single atoms are not::

                >>> str(Regex(r'abc').quantify('+'))
                '(?:abc)+'
                >>> str(Regex(r'a').quantify('+'))
                'a+'
        """
        cls = self.__class__
        quantifier = Quantifier(quantifier)

        # Edge & null cases
        if not self:
            return self
        elif len(self) == 1 and (new := self.one.quantify(quantifier, overwrite)) is not None:
            return cls(new)
        else:
            # Base case: Must wrap multi-atom expression in a new group
            return cls(f'(?:{self}){quantifier}')

    @classmethod
    def is_split(cls, expr: str | Atom | Self) -> bool:
        """Check if the given expression contains any top-level `|` splitters.

        Examples:
            Splitters inside groups do not count::

                >>> Regex.is_split(r'a|b'), Regex.is_split(r'(?:a|b)')
                (True, False)
        """
        if isinstance(expr, str):
            return cls.SPLITTER in cls.atomize(expr)
        elif isinstance(expr, cls):
            return cls.SPLITTER in expr
        elif isinstance(expr, GroupAtom):
            return cls.SPLITTER in cls.atomize(expr.body)
        return False

    @classmethod
    def is_atomic(cls, expr: str | Atom | Self) -> bool:
        """Check if the given expression is atomic (i.e. composed of a single atom).

        Examples:
            A whole group is one atom; two literals are not::

                >>> Regex.is_atomic(r'(?:a|b)'), Regex.is_atomic(r'ab')
                (True, False)
        """
        if isinstance(expr, Atom) or not expr:
            return True
        elif isinstance(expr, Regex):
            return len(expr) == 1
        elif isinstance(expr, str):
            first_atom = mi.first(cls.atomize(expr), default=Atom(''))
            return len(first_atom) == len(expr)
        else:
            raise TypeError(f'Unsupported type for is_atomic check: {type(expr)}')

    def split(self) -> Iterator[Self]:
        """Split the Regex instance into branches at top-level `|` atoms.

        Examples:
            Split an alternation into its branches::

                >>> [str(branch) for branch in Regex(r'foo|bar|baz').split()]
                ['foo', 'bar', 'baz']
        """
        yield from map(self.__class__, mi.split_at(self.data, lambda atom: atom == self.SPLITTER))

    def startswith(self, other: str | Atom | Self) -> bool:
        """Check if this Regex starts with the given pattern."""
        other_atoms = Regex(other).data
        if len(other_atoms) > len(self):
            return False
        return self.data[: len(other_atoms)] == other_atoms

    def endswith(self, other: str | Atom | Self) -> bool:
        """Check if this Regex ends with the given pattern."""
        other_atoms = Regex(other).data
        if len(other_atoms) > len(self):
            return False
        return self.data[-len(other_atoms) :] == other_atoms

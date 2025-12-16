############
### HEAD ###
############
### STANDARD
from typing import Iterator, Self, Sequence, ClassVar, Literal, TypeGuard, Generator
import functools as ft
import itertools as it
import more_itertools as mi

### EXTERNAL

### INTERNAL
from ...types import Buffer
from .GroupKind import GroupKind
from .meta_patterns import META_RGXS
from .Quantifier import Quantifier
from .Atom import Atom
from .GroupAtom import GroupAtom
from .SetAtom import SetAtom


############
### DATA ###
############
NO_KIND = GroupKind(0)
PairMode = Literal['all', 'roots', 'leaves']
RegexBuffer = ft.partial(Buffer.new, fence_rgxs=['arrays'])


############
### BODY ###
############
@ft.total_ordering
class Expression:
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
            elif isinstance(arg, Expression):
                self.data.extend(arg.data)
            elif isinstance(arg, str):
                self.data.extend(self.atomize(arg))
            elif isinstance(arg, (Sequence | Iterator)):
                self.data.extend(arg)
            else:
                raise TypeError(f'Unsupported type for Expression initialization: {type(arg)}')

    @classmethod
    def atomize(cls, expr: str | Buffer | Self) -> Generator[Atom, None, None]:
        """
        Break a regex expression into its atomic components.

        Args:
            expr: The raw regular expression string to atomize.
            escape: If set, escape characters matching RGXS['special_characters'].
        Returns:
            Tuple of atomic regex components (characters, groups, character sets, etc.).
        """
        if isinstance(expr, cls):
            return iter(expr.data)

        expr = str(expr)
        n = len(expr)

        # I. Break up the expression into ranges of different types
        # I.i. First, find all the "root" (top-level) groups in the expression
        buf = RegexBuffer(expr)
        group_atoms = list(cls.group_iterator(buf, mode='roots'))
        group_spans = [group.span for group in group_atoms]

        # I.ii. Next, reuse the work already done by Buffer to find character sets (for exclusion)
        set_spans = [span for span in buf.fence_spans if not span.interects(group_spans)]
        assert all(set_spans), f'Identified empty set spans, which is impossible: {set_spans}'
        set_atoms = [SetAtom(data=expr[span[0] : span[1]], span=span) for span in set_spans]

        # I.iii. Finally, enumerate all the remaining "plain" spans between groups and sets
        x_prev = 0
        for atom in sorted(group_atoms + set_atoms, key=lambda atom: atom.span):
            x0, x1 = atom.span
            if x0 > x_prev:
                yield from Atom.plain_atomize(expr[x_prev:x0])
            yield atom
            x_prev = x1

        if x_prev < n:
            yield from Atom.plain_atomize(expr[x0:x1])

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
    @classmethod
    def group_iterator(
        cls,
        text: Buffer | str | list[str],
        mask: GroupKind = NO_KIND,
        mode: PairMode = 'all',
    ) -> Iterator[GroupAtom]:
        """
        Iterate over all groups in the given pattern (e.g. `(?:abc)`).

        Args:
            text: Text to search for groups (will be converted to Buffer).
            mask: Optional GroupKind filter to yield only matching group types.
            mode: 'all' by default, 'roots' to exclude nested groups, or 'leaves' for the opposite.
        Yields:
            1. span: The (start, end) indices of the full group match.
            2. kind: The GroupKind of the group.
            3. name: The name of the group (if applicable).
            4. body: The body text of the group.
            5. quant: Any quantifier applied to the group.
        """
        # I. Cast the input text to a charset-ignoring buffer
        if isinstance(text, list):
            text = RegexBuffer(''.join(text))
        elif isinstance(text, str):
            text = RegexBuffer(text)
        assert isinstance(text, Buffer), f'Invalid text buffer: {type(text)}'
        assert 'arrays' in text.fence_rgxs, f'Invalid buffer fences: {text.fence_rgxs}'

        # II. Use the Buffer's "pair" functionality to find matching parens
        for span, start, body, end in text.pair_iterator(META_RGXS['group'], mode):
            if not mask or (kind := GroupKind.read(start)) in mask:
                yield GroupAtom(
                    data=text[span[0] : span[1]],
                    span=span,
                    kind=kind,
                    start=start,
                    body=body,
                    quantifier=Quantifier(end),
                )

    @classmethod
    def set_iterator(cls, text: Buffer | str | list[str]) -> Iterator[SetAtom]:
        """
        Find and yield all the character sets (e.g. `[A-Za-z]`) in the given text.

        Args:
            text: Text to search for character sets.
        Yields:
            Atom.Set objects
        """
        if isinstance(text, list):
            text = ''.join(text)
        if isinstance(text, str):
            # RegexBuffer's *exclude* sets on purpose, so don't use that constructor here
            text = Buffer.new(text, no_fence=True)
        assert isinstance(text, Buffer)

        for span, _, body, end in text.pair_iterator(META_RGXS['set'], mode='roots'):
            yield SetAtom(
                data=text[span[0] : span[1]],
                span=span,
                body=body,
                quantifier=Quantifier(end),
            )

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
        raise TypeError(f'Unsupported type for Expression indexing: {type(key)}')

    @__getitem__.register
    def _get_pos(self, key: int) -> Atom:
        return self.data[key]

    @__getitem__.register
    def _get_slice(self, key: slice) -> Self:
        return self.__class__(self.data[key])

    @ft.singledispatchmethod
    def __setitem__(self, key, value):
        raise TypeError(f'Unsupported types for Expression assignment: {type(key)}, {type(value)}')

    @__setitem__.register
    def _set_pos(self, key: int, value: str | Atom) -> None:
        if isinstance(value, str):
            value = mi.one(self.atomize(value))
        self.data[key] = value

    @__setitem__.register
    def _set_slice(self, key: slice, value: str | Sequence[Atom] | Self) -> None:
        if isinstance(value, str):
            self.data[key] = list(self.atomize(value))
        elif isinstance(value, Expression):
            self.data[key] = value.data
        elif isinstance(value, Sequence):
            self.data[key] = list(map(Atom, value))
        else:
            raise TypeError(f'Unsupported type for Expression assignment: {type(value)}')

    def __add__(self, other: object) -> Self:
        cls = self.__class__
        if isinstance(other, (str, Atom, Sequence, Expression)):
            return cls(self.data + cls(other).data)
        else:
            raise TypeError(f'Unsupported type for Expression addition: {type(other)}')

    def __lt__(self, other: object) -> bool:
        if isinstance(other, (str, Atom, Sequence, Expression)):
            return self.data < self.__class__(other).data
        else:
            raise TypeError(f'Unsupported type for Expression comparison: {type(other)}')

    def __iter__(self) -> Iterator[Atom]:
        return iter(self.data)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, (str, Atom, Sequence, Expression)):
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
    def last(self) -> Atom:
        return self.data[-1] if self else Atom()

    @property
    def one(self) -> Atom:
        assert len(self) == 1, 'Expression.one called on Expression with length != 1'
        return self.data[0]

    @property
    def spans(self) -> list[tuple[int, int]]:
        ends = list(it.accumulate(map(len, self.data)))
        starts = [0] + ends[:-1]
        return list(zip(starts, ends, strict=True))

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
        atoms = Expression.atomize(expr) if isinstance(expr, str) else expr
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
    def is_split(cls, expr: str | Atom | Self) -> bool:
        if isinstance(expr, str):
            return cls.SPLITTER in cls.atomize(expr)
        elif isinstance(expr, cls):
            return cls.SPLITTER in expr
        elif isinstance(expr, GroupAtom):
            return cls.SPLITTER in cls.atomize(expr.body)
        return False

    @classmethod
    def is_atomic(cls, expr: str | Atom | Self) -> bool:
        if isinstance(expr, Atom) or not expr:
            return True
        elif isinstance(expr, Expression):
            return len(expr) == 1
        elif isinstance(expr, str):
            first_atom = mi.first(cls.atomize(expr), default=Atom(''))
            return len(first_atom) == len(expr)
        else:
            raise TypeError(f'Unsupported type for is_atomic check: {type(expr)}')

    def split(self) -> Iterator[Self]:
        """
        Split the Expression instance into branches at top-level '|' atoms.

        Yields:
            Expression instances representing alternate branches.
        """
        yield from map(Expression, mi.split_at(self.data, lambda atom: atom == self.SPLITTER))

############
### HEAD ###
############
### STANDARD
from typing import Generator, Iterator, Self, Literal
import functools as ft
import more_itertools as mi

### EXTERNAL
import pydantic as pyd

### INTERNAL
from ...types import Span, Buffer
from .GroupKind import GroupKind
from .Quantifier import Quantifier
from .meta_patterns import META_RGXS


############
### DATA ###
############
NO_KIND = GroupKind(0)

# A buffer built to hold Regex patterns
RegexBuffer = ft.partial(Buffer.new, fence_rgxs=['arrays'])


############
### BODY ###
############
@ft.total_ordering
class Atom(pyd.RootModel[str]):
    # -------------------
    # `0` Initial Methods
    # -------------------
    def __init__(self, data: str | Self = '') -> None:
        self.data = data.data if isinstance(data, Atom) else str(data)

    def quantify(self, quantifier: str | Quantifier, overwrite: bool = True) -> Self:
        """
        Create a copy of this atom with the given quantifier applied. Any existing quantifier is
        dropped.
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
        if opt := self.quantifier.as_optional():
            return self.quantify(opt)
        else:
            return self.quantify('?', overwrite=False)

    def as_required(self) -> Self:
        return self.quantify(self.quantifier.as_required)

    # -------------------
    # `-` Private Methods
    # -------------------
    @classmethod
    def set_iterator(cls, text: Buffer | str | list[str]) -> Iterator[tuple[Span, str, str]]:
        """
        Find and yield all the character sets (e.g. `[A-Za-z]`) in the given text.

        Args:
            text: Text to search for character sets.
        Yields:
            1. span: The (start, end) indices of the full set match.
            2. body: The body text of the set.
            3. quant: Any quantifier applied to the set.
        """
        if isinstance(text, list):
            text = ''.join(text)
        if isinstance(text, str):
            text = Buffer.new(text, no_fence=True)  # NOTE: Not a RegexBuffer, so no fence_rgxs
        assert isinstance(text, Buffer)

        for span, _, body, end in text.pair_iterator(META_RGXS['set'], mode='roots'):
            yield span, body, end[1:]

    @staticmethod
    def _cast_param(param: object) -> str:
        return param.data if isinstance(param, Atom) else str(param)

    # -------------------
    # `+` Primary Methods
    # -------------------
    @staticmethod
    def group_iterator(
        text: Buffer | str | list[str],
        mask: GroupKind = NO_KIND,
        mode: Literal['all', 'roots', 'leaves'] = 'all',
    ) -> Iterator[tuple[Span, GroupKind, str, str, str]]:
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
        # Cast the input text to a charset-ignoring buffer
        if isinstance(text, list):
            text = RegexBuffer(''.join(text))
        elif isinstance(text, str):
            text = RegexBuffer(text)
        assert isinstance(text, Buffer), f'Invalid text buffer: {type(text)}'
        assert 'arrays' in text.fence_rgxs, f'Invalid buffer fences: {text.fence_rgxs}'

        for span, start, body, end in text.pair_iterator(META_RGXS['group'], mode):
            kind = GroupKind.read(start)
            if mask and kind not in mask:
                continue

            if kind in GroupKind._NAMED:
                name = body.split('>', 1)[0]
                body = body[len(name) + 1 :]
            else:
                name = ''
            yield span, kind, name, body, end[1:]

    def as_group(self) -> tuple[GroupKind, str, str, str, str]:
        """
        Split up a group atom (e.g. '(?:some_*pattern)+?') into its component parts.

        Returns:
            1. kind: The GroupKind of this group.
            2. start: The starting sequence of the group (e.g. '(?:', '(?=').
            3. flags: Any inline flags specified in the group.
            4. body: The body text of the group.
            5. quant: Any quantifier applied to the group.
        """
        assert self.is_group, f'Invalid group atom: {self}'

        # I. Parse this atoms text as a group and ensure the result is singular
        span, kind, cname, body, quant = mi.one(self.group_iterator(self.data, mode='roots'))
        assert span == (0, len(self)), f'Invalid group atom: {self}'

        # II. The start of the group is all the text before the body text begins
        start = self.data[: self.data.index(body)]

        # III. Expand out inline flags (e.g. '(?im:pattern)')
        flags = ''
        if kind == GroupKind.FLAGS and start.endswith(':'):
            flags = start[2:-1]
            start = '(?:'
            kind = GroupKind.PLAIN

        return kind, start, flags, body, quant

    def as_set(self) -> tuple[bool, str, str]:
        """
        Split up a set atom (e.g. '[A-Za-z0-9]+') into its component parts.

        Returns:
            1. is_complex: Whether this set is complex (i.e. contains set operators).
            2. body: The body text of the set.
            3. quant: Any quantifier applied to the set.
        """
        assert self.is_set, f'Invalid set atom: {self}'
        body, quant = self.data[1:].rsplit(']', 1)
        return not self.is_complex_set, body, quant

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
        return self.data == self._cast_param(other)

    def __lt__(self, other: object) -> bool:
        return self.data < self._cast_param(other)

    def __contains__(self, item: object) -> bool:
        return self._cast_param(item) in self.data

    def __add__(self, other: object) -> Self:
        cls = self.__class__
        return cls(self.data + self._cast_param(other))

    def __radd__(self, other: object) -> Self:
        cls = self.__class__
        return cls(self._cast_param(other) + self.data)

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
        if len(self) >= 2:
            if self.is_group:
                # I. Look for quantifier after the closing ')'
                return Quantifier(self.data.rsplit(')', 1)[-1])
            elif match := META_RGXS['quant'].search(self.data):
                # II. Otherwise, just search with a regex that only matches at the end of the string
                return Quantifier(match[0])
        return Quantifier()

    @ft.cached_property
    def has_complex_quantifier(self) -> bool:
        return not self.quantifier.is_simple

    @ft.cached_property
    def is_optional(self) -> bool:
        return self.quantifier.is_optional

    @ft.cached_property
    def is_group(self) -> bool:
        return len(self) > 0 and self.data[0] == '('

    @ft.cached_property
    def is_set(self) -> bool:
        return len(self) >= 3 and self.data[0] == '['

    @ft.cached_property
    def is_complex_group(self) -> bool:
        if not self.is_group:
            return False
        kind, _, _, _, quant = self.as_group()
        return kind not in GroupKind._SIMPLE or quant not in ('', '?')

    @ft.cached_property
    def is_complex_set(self) -> bool:
        return self.is_set and bool(META_RGXS['set_operator'].search(self.data))

    @ft.cached_property
    def is_simple_set(self) -> bool:
        return self.is_set and not self.is_complex_set

    @ft.cached_property
    def is_simple(self) -> bool:
        # Don't include groups or quantified values
        return not any(
            [
                len(self) == 0,
                self.is_group,
                self.has_complex_quantifier,
                self.is_complex_set,
            ]
        )

    # ------------
    # `x2` Methods
    # ------------
    @classmethod
    def parse(cls, expr: str) -> Generator[Self, None, None]:
        n_chars = len(expr)

        x = 0
        for (x0, x1), *_ in cls.group_iterator(expr, mode='roots'):
            if x0 > x:
                # I.i. Yield any atoms between this and the last group
                yield from META_RGXS['atom'].findall(expr[x:x0])
            if x1 > x0:
                # I.ii. Yield this group
                yield expr[x0:x1]
            x = x1

        # II. Yield any atoms after the last group
        if x < n_chars:
            yield from META_RGXS['atom'].findall(expr[x:])

    @classmethod
    def is_atomic(cls, expr: str) -> bool:
        first_atom = mi.first(cls.parse(expr), default=Atom(''))
        return len(first_atom) == len(expr)

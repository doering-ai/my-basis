############
### HEAD ###
############
### STANDARD
from typing import Self
import functools as ft

### EXTERNAL
import pydantic as pyd

### INTERNAL
from ...types import Span, Buffer
from .meta_patterns import META_RGXS
from .GroupKind import GroupKind
from .Atom import Atom


############
### DATA ###
############
NO_KIND = GroupKind(0)

# A buffer built to hold Regex patterns
RegexBuffer = ft.partial(Buffer.new, fence_rgxs=['arrays'])


############
### BODY ###
############
class GroupAtom(Atom):
    """A single group in a regular expression, denoted by parentheses."""

    # Primary fields
    start: str = ''
    body: str = ''

    # Derived fields
    span: Span = pyd.Field(default_factory=lambda: Span(0, 0))
    kind: GroupKind = NO_KIND
    name: str = ''
    flags: set[str] = set()  # noqa: RUF012

    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyd.model_validator(mode='after')
    def _construct_group(self) -> Self:
        # I. Validate
        assert len(self.data) >= 2, f'Invalid group: {self.data}'
        assert self.data.startswith('(') and ')' in self.data, f'Invalid group: {self.data}'

        # I. Setup fields from scratch if we just have data
        if len(self.data) > 2 and not self.body:
            self.read_data()

        if self.kind in GroupKind._NAMED and not self.name:
            self.infer_name()

        if self.kind == GroupKind.FLAGS and not self.flags:
            self.infer_flags()

        return self

    # -------------------
    # `-` Private Methods
    # -------------------
    def read_data(self) -> None:
        # I.i. Separate out the opening syntax (e.g. `(?:`)
        match = META_RGXS['group'].match(self.data)
        assert match is not None, f'Invalid group: {self.data}'
        self.start = match.group('start')
        assert self.start, f'Invalid group start: {self.start}'

        # I.ii. Infer the kind
        self.kind = GroupKind.read(self.start)
        assert self.kind != NO_KIND, f'Unrecognized group kind: {self.start}'

        # I.iii. Separate out the closing paren and quantifier (if present)
        rest = self.data[len(self.start) :]
        self.body = rest.rsplit(')', 1)[0]

    def infer_name(self) -> None:
        if self.kind == GroupKind.PARAM:
            # I. Named capture groups's names are part of 'start', not 'body'
            assert '>' in self.body, f'Invalid named capture self: {self.body}'
            self.name, self.body = self.body.split('>', 1)
            self.start += f'{self.name}>'
        elif self.kind & GroupKind.INVOC | GroupKind.SUBST:
            # II. Invocations and substitutions have no body
            self.name, self.body = self.body, ''
            self.start += self.name

    def infer_flags(self) -> None:
        if self.start.endswith(':'):
            # I. Plain groups appear to be flag groups, but actually do have content
            self.kind = GroupKind.PLAIN
            self.flags = set(self.start[2:-1])  # e.g. '(?smi:' -> 'smi'
        else:
            # II. Dedicated inline flag groups have no body
            self.flags = set(self.body)
            self.start += self.body
            self.body = ''

    # -------------------
    # `+` Primary Methods
    # -------------------

    # ------------------
    # `*` Public Methods
    # ------------------
    def __hash__(self) -> int:
        return hash(str(self))

    @ft.cached_property
    def is_simple(self) -> bool:
        return super().is_simple and self.kind in GroupKind._SIMPLE

    @ft.cached_property
    def inline_flags(self) -> Atom:
        return Atom(rf'(?{"".join(sorted(self.flags))})') if self.flags else Atom('')

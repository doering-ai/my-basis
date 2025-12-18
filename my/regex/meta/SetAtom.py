############
### HEAD ###
############
### STANDARD
from typing import Self
import functools as ft

### EXTERNAL
import pydantic as pyd

### INTERNAL
from ...types import Span
from .meta_patterns import META_RGXS
from .Atom import Atom


############
### BODY ###
############
class SetAtom(Atom):
    span: Span = pyd.Field(default_factory=lambda: Span(0, 0))
    body: str = ''

    @pyd.model_validator(mode='after')
    def _construct_span(self) -> Self:
        assert len(self.data) >= 2, f'Invalid set data (too short): {self.data}'
        assert self.data.startswith('['), f'Invalid set data (missing `[`): {self.data}'

        if len(self.data) > 2 and not self.body:
            self.body = self.data[1:].rsplit(']', 1)[0]

        # Escape special characters found within the set

        return self

    @ft.cached_property
    def members(self) -> list[Atom]:
        assert self.is_simple, f'Cannot directly get members of non-simple SetAtom: {self.data}'
        escaped_body = META_RGXS['special_characters'].sub(r'\\\1', self.body)
        return list(Atom.plain_atomize(escaped_body))

    @ft.cached_property
    def is_simple(self) -> bool:
        return super().is_simple and not self._has_set_operator(self.body)

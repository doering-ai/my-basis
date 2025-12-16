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
from .Quantifier import Quantifier
from .Atom import Atom


############
### BODY ###
############
class SetAtom(Atom):
    span: Span = pyd.Field(default_factory=lambda: Span(0, 0))
    body: str = ''
    quantifier: Quantifier = pyd.Field(default_factory=Quantifier)

    @pyd.model_validator(mode='after')
    def _construct_span(self) -> Self:
        assert len(self.data) >= 2, f'Invalid set data (too short): {self.data}'
        assert self.data.startswith('['), f'Invalid set data (missing `[`): {self.data}'

        if len(self.data) > 2 and not self.body:
            self.body, end = self.data[1:].rsplit(']', 1)
            self.quantifier = Quantifier(end)
        return self

    @ft.cached_property
    def is_simple(self) -> bool:
        return super().is_simple and not bool(META_RGXS['set_operator'].search(self.body))

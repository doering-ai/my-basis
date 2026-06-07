############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import ClassVar, TYPE_CHECKING
import functools as ft

### EXTERNAL
import pydantic as pyd

### INTERNAL
if TYPE_CHECKING:
    from .Typist import Typist


############
### BODY ###
############
class _TypingBase(pyd.BaseModel):
    """The superclass of all type action files (i.e. typematch, typecheck, & typecast)."""

    #: The static interface for MATCHING, CHECKING, and TRANSFORMING types.
    TY: ClassVar[Typist]

    @ft.cached_property
    def ty(self) -> Typist:
        """The static interface for MATCHING, CHECKING, and TRANSFORMING types."""
        return self._ty()

    @staticmethod
    def _ty() -> Typist:
        if not hasattr(_TypingBase, 'TY'):
            from .Typist import typist

            _TypingBase.TY = typist
        return _TypingBase.TY

############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import ClassVar

# I/O

### EXTERNAL

### INTERNAL
# Local imports

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..typing.Typist import Typist

############
### DATA ###
############


############
### BODY ###
############
class _UtilsBase:
    ty: ClassVar[Typist]

    @staticmethod
    def set_typist(ty: Typist) -> None:
        _UtilsBase.ty = ty

    @staticmethod
    def typist() -> Typist:
        return _UtilsBase.ty

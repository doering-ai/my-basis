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
    """Shared base class wiring a late-bound `Typist` instance into every utility class."""

    ty: ClassVar[Typist]

    @staticmethod
    def set_typist(ty: Typist) -> None:
        """Install the shared `Typist` instance used by every utility class."""
        _UtilsBase.ty = ty

    @staticmethod
    def typist() -> Typist:
        """Return the shared `Typist` instance."""
        return _UtilsBase.ty

############
### HEAD ###
############
# --------
# Standard
# --------
from __future__ import annotations

from typing import TypeVar, Generic, TYPE_CHECKING

# --------
# External
# --------
if TYPE_CHECKING:
    import sublime as sb
import sublime_plugin as sbp

# --------
# Internal
# --------
from ..types.CommandArguments import CommandArguments
from ._MyBase import MyBase

_I = TypeVar('_I', bound=CommandArguments)


############
### BODY ###
############
class _MyViewCommand(Generic[_I], MyBase[_I], sbp.TextCommand):
    """A Sublime Text 4 command that is instantiated once per 'view' (i.e. tab).

    You should feel safe using `self.view` and `self.edit` in any method that executes
    synchronously, as they are set when the command is first run and cleared when exits.

    The `edit` token in particular is designed to *only* work synchronously, so make sure to use
    the primary `sublime_plugin` APIs when you need an async text command.
    For the large majority of use cases though, this shouldn't be necessary.

    Note:
        These are named with an `_` prefix in order to prevent sublime text from treating the
        abstract superclasses as instantiable. If you're setting up a lot of subclasses and want
        to centralize some shared functionality in another superclass, make sure to do the same with
        that class's name.

    """

    # -------------------
    # `.` Initial Methods
    # -------------------
    def __init__(self, view: sb.View, *args, **kwargs) -> None:
        """Initialize this class."""
        self.view = view  # type: ignore[bad-override]
        super().__init__(view, *args, **kwargs)

    # -------------------
    # `-` Private Methods
    # -------------------

    # -------------------
    # `+` Primary Methods
    # -------------------

    # ------------------
    # `x` Public Methods
    # ------------------
    @property
    def uid(self) -> str:
        val = self._view.id() if self._view is not None else '-'
        return f'{self.classname}[{val}]'

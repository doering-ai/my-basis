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
from .CommandArguments import CommandArguments
from ._MyBase import MyBase

_I = TypeVar('_I', bound=CommandArguments)


############
### BODY ###
############
class _MyCommand(Generic[_I], MyBase[_I], sbp.TextCommand):
    """A Sublime Text 4 command that is instantiated once per 'view' (i.e. tab).

    You should feel safe using `self.view` and `self.edit` in any method, as they are set when the
    command is first run.
    """

    # -------------------
    # `.` Initial Methods
    # -------------------
    def __init__(self, view: sb.View, *args, **kwargs) -> None:
        """Initialize this class."""
        self.view = view
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

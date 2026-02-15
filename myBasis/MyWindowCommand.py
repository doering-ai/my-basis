############
### HEAD ###
############
# --------
# Standard
# --------
from __future__ import annotations
from typing import ClassVar, TypeVar, Generic, TYPE_CHECKING

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

# ruff: noqa: UP046


############
### BODY ###
############
class MyWindowCommand(Generic[_I], MyBase[_I], sbp.WindowCommand):
    """A Sublime Text 4 command that is instantiated once per Window.

    This class excels for tasks that relate to multiple tabs ('views') at once, whether that means
    comparing them, modifying them, creating them, or rearranging them.
    It's recommended you use `MyCommand` instead (based off `sbp.TextCommand`) for a typical usecase
    involving reading and/or modifying a single tab's contents.
    """

    _ALLOW_OVERRIDES: ClassVar[bool] = True

    # -------------------
    # `.` Initial Methods
    # -------------------
    def __init__(self, window: sb.Window) -> None:
        """Initialize this class."""
        self.window = window

    # -------------------
    # `-` Private Methods
    # -------------------

    # -------------------
    # `+` Primary Methods
    # -------------------

    # ------------------
    # `x` Public Methods
    # ------------------

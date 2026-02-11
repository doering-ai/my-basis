############
### HEAD ###
############
# --------
# Standard
# --------
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sublime as sb

# --------
# External
# --------
import sublime_plugin as sbp
# import sublime as sb

# --------
# Internal
# --------
from ._MyBase import MyBase


############
### BODY ###
############
class MyWindowCommand(sbp.WindowCommand, MyBase):
    """A base class for Sublime Text commands with utilities for comment handling."""

    def __init__(self, window: sb.Window, **kwargs) -> None:
        """Initialize a window command."""
        self.window = window
        super().__init__(**kwargs)

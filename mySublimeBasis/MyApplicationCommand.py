############
### HEAD ###
############
# --------
# Standard
# --------
from __future__ import annotations
from typing import TYPE_CHECKING

# --------
# External
# --------
import sublime_plugin as sbp

if TYPE_CHECKING:
    import sublime as sb

# --------
# Internal
# --------
from ._MyBase import MyBase


############
### BODY ###
############
class MyApplicationCommand(sbp.ApplicationCommand, MyBase):
    """A Sublime Text 4 command that is instantiated just once per application."""

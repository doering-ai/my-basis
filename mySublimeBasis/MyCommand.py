############
### HEAD ###
############
# --------
# Standard
# --------
from __future__ import annotations
from typing import Any, TYPE_CHECKING
import inspect
from abc import abstractmethod

# --------
# External
# --------
import sublime_plugin as sbp
import regex as re
import pydantic as pyd

if TYPE_CHECKING:
    import sublime as sb

# --------
# Internal
# --------
from ._MyBase import MyBase


############
### BODY ###
############
class MyCommand(sbp.TextCommand, MyBase, sublime_interface={'run'}):
    """A Sublime Text 4 command that is instantiated once per 'view' (i.e. tab)."""

    edit: sb.Edit

    # -------------------
    # `.` Initial Methods
    # -------------------
    def run(self, edit: sb.Edit, **kwargs: Any):
        """Run the command with the given edit object and keyword arguments."""
        self.edit = edit
        self._set_attrs(**kwargs)
        for region in self.regions:
            self.main(region)

    def setup(self, **kwargs: Any) -> None:
        """Set up the command with the given keyword arguments."""
        self.kwargs = kwargs
        members = dict(inspect.getmembers(self))
        for key, value in kwargs.items():
            if key in members:
                setattr(self, key, value)

    # -------------------
    # `-` Private Methods
    # -------------------

    # -------------------
    # `+` Primary Methods
    # -------------------

    # ------------------
    # `x` Public Methods
    # ------------------
    @abstractmethod
    def main(self, region: sb.Region) -> Any:
        """The main method to be overridden by subclasses."""
        raise NotImplementedError("Tried to call abstract class's main method.")

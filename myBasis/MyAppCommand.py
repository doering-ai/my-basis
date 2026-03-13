############
### HEAD ###
############
# --------
# Standard
# --------
from __future__ import annotations
from typing import ClassVar, TypeVar, Generic

# --------
# External
# --------
import sublime_plugin as sbp
# import sublime as sb

# --------
# Internal
# --------
from .CommandArguments import CommandArguments
from ._MyBase import MyBase

_I = TypeVar('_I', bound=CommandArguments)


############
### BODY ###
############
class _MyAppCommand(Generic[_I], MyBase[_I], sbp.ApplicationCommand):
    """A Sublime Text 4 command that is instantiated just once per application.

    There's literally zero new logic in this base class as opposed to Command, so this can
    rightfully be considered the most basic type of command available.
    That said, it's recommended you use `MyCommand` (based off `sbp.TextCommand`) for a typical
    usecase involving reading and/or modifying  a single tab's contents.

    Obviously, keep in mind while subclassing that all member variables will live indefinitely;
    perform your own cleanup as needed.
    """

    _ALLOW_OVERRIDES: ClassVar[bool] = True

    # -------------------
    # `.` Initial Methods
    # -------------------

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
        return self.classname

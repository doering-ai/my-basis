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
# import sublime as sb
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
class _MyAppListener(Generic[_I], MyBase[_I], sbp.EventListener):
    """A base class for any commands that trigger automatically (rather than being called directly).

    For a list of available events you can attach to with `on_EVENT` methods, see
    `constants.EVENTS`.

    All the events mentioned in `constants.ASYNCABLE_EVENTS` have an `on_EVENT_async` variant,
    though it is only async 'behind the scenes', so-to-speak. To run `asyncio` code, choose one of
    those functions and wrap your logic in `asyncio.run()`.
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

############
### HEAD ###
############
# --------
# Standard
# --------
from __future__ import annotations
# from typing import TYPE_CHECKING
# if TYPE_CHECKING:
# from collections.abc import Iterator

# --------
# External
# --------
import sublime as sb
import sublime_plugin as sbp

# --------
# Internal
# --------
from ._MyBase import MyBase


############
### BODY ###
############
class MyListener(sbp.EventListener, MyBase):
    """A base class for any commands that trigger automatically (rather than being called direcly).

    For a list of available events you can attach to with `on_EVENT` methods, see
    `constants.EVENTS`.

    All the events mentioned in `constants.ASYNCABLE_EVENTS` have an `on_EVENT_async` variant,
    though it is only async 'behind the scenes', so-to-speak. To run `asyncio` code, choose one of
    those functions and wrap your logic in `asyncio.run()`.
    """

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

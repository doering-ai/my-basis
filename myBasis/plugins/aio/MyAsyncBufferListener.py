############
### HEAD ###
############
### STANDARD
from typing import TypeVar, Generic
# import asyncio as aio

### EXTERNAL
import sublime_aio as sbaio

### INTERNAL
from ...types.CommandArguments import CommandArguments
from .._MyBase import Meta
from ..MyBufferListener import _MyBufferListener


############
### DATA ###
############
_I = TypeVar('_I', bound=CommandArguments)


############
### META ###
############
class _BufferListenerMeta(Meta, sbaio.AsyncTextChangeListenerType):
    pass


############
### BODY ###
############
class _MyAsyncBufferListener(Generic[_I], _MyBufferListener[_I], meta=_BufferListenerMeta):
    """A base class for any commands that trigger automatically (rather than being called directly).

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

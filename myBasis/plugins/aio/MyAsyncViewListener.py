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
from ..MyViewListener import _MyViewListener


############
### DATA ###
############
_I = TypeVar('_I', bound=CommandArguments)


############
### META ###
############
class _ViewListenerMeta(Meta, sbaio.AsyncEventListenerType):
    pass


############
### BODY ###
############
class _MyAsyncViewListener(Generic[_I], _MyViewListener[_I], meta=_ViewListenerMeta):
    pass

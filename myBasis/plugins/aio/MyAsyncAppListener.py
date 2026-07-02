############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import TypeVar, Generic
# import asyncio as aio

### EXTERNAL
import sublime_aio as sbaio

### INTERNAL
from ...types.CommandArguments import CommandArguments
from .._MyBase import Meta
from ..MyAppListener import _MyAppListener


############
### DATA ###
############
_I = TypeVar('_I', bound=CommandArguments)


############
### META ###
############
class _AppListenerMeta(Meta, sbaio.AsyncEventListenerType):
    pass


############
### BODY ###
############
class _MyAsyncAppListener(Generic[_I], _MyAppListener[_I], meta=_AppListenerMeta):
    pass

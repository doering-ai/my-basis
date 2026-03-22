############
### HEAD ###
############
### STANDARD
from typing import ClassVar, TypeVar, Generic, Any
# import asyncio as aio

### EXTERNAL
import sublime_aio as sbaio

### INTERNAL
from ...types.CommandArguments import CommandArguments
from .._MyBase import MyBase


############
### DATA ###
############
_I = TypeVar('_I', bound=CommandArguments)


############
### BODY ###
############
class _MyAsyncAppCommand(Generic[_I], MyBase[_I], sbaio.ApplicationCommand):
    """A Sublime Text 4 command that is instantiated just once per system.

    This class excels for tasks that relate to multiple tabs ('views') at once, whether that means
    comparing them, modifying them, creating them, or rearranging them.
    It's recommended you use `MyCommand` instead (based off `sbp.TextCommand`) for a typical usecase
    involving reading and/or modifying a single tab's contents.
    """

    _ALLOW_OVERRIDES: ClassVar[bool] = True

    # -------------------
    # `.` Initial Methods
    # -------------------
    @property
    def uid(self) -> str:
        val = self._window.id() if self._window is not None else '-'
        return f'{self.classname}[{val}]'

    # -------------------
    # `-` Private Methods
    # -------------------

    # -------------------
    # `+` Primary Methods
    # -------------------

    # ------------------
    # `x` Public Methods
    # ------------------
    async def run(self, *args: Any, **kwargs: Any) -> Any:
        """Run the command with the given keyword arguments."""
        if args or kwargs:
            MyBase.cache_args(self, args, kwargs)
        self.args = self.Interface(**kwargs)
        return await self.main()

    async def main(self) -> Any:
        """The primary entry point for the command."""
        raise NotImplementedError('You must implement the `main` method to use this class.')

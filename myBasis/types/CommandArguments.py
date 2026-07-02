############
### HEAD ###
############
# --------
# Standard
# --------
from __future__ import annotations
from typing import ClassVar
from collections.abc import MutableSequence

# --------
# External
# --------
import pydantic as pyd
import more_itertools as mi

# --------
# Internal
# --------
from .StaticPrompt import StaticPrompt


############
### BODY ###
############
class CommandArguments(pyd.BaseModel):
    """A typed container for specifying command interfaces, meant to be subclassed."""

    #: A static description of a keyword arguments that can or must be supplied by the user once
    #: prompted via the Sublime Text command pallete.
    PROMPT: ClassVar[StaticPrompt | None] = None

    @classmethod
    def _interpolate(cls, data: dict) -> None:
        """Interpolate the `<character>` placeholder in all string values in the data dict."""
        if 'character' not in data:
            return

        for key, value in data.items():
            if isinstance(value, str):
                if '<character>' in value:
                    data[key] = value.replace('<character>', data['character'])
                    if data[key].isdigit():
                        data[key] = int(data[key])
            elif isinstance(value, dict):
                cls._interpolate(value)
            elif isinstance(value, MutableSequence):
                for i in mi.locate(value, lambda v: isinstance(v, str) and '<character>' in v):
                    value[i] = value[i].replace('<character>', data['character'])
                    if value[i].isdigit():
                        value[i] = int(value[i])

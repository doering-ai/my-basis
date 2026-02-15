############
### HEAD ###
############
# --------
# Standard
# --------
from __future__ import annotations

# --------
# External
# --------
import pydantic as pyd

# --------
# Internal
# --------


############
### BODY ###
############
class CommandArguments(pyd.BaseModel, extra='allow', arbitrary_types_allowed=True):
    """A typed container for specifying command interfaces, meant to be subclassed."""

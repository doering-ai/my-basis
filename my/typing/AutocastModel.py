############
### HEAD ###
############
### STANDARD
from typing import Any

### EXTERNAL
import pydantic as pyd

### INTERNAL
from .Typist import typist


############
### BODY ###
############
class AutocastModel(pyd.BaseModel):
    @pyd.model_validator(mode='before')
    @classmethod
    def _auto_validate(cls, data: dict) -> dict:
        return typist._cast_model_members(data.items(), cls)

    @pyd.model_serializer(mode='wrap')
    def _auto_serialize(self, handler) -> dict[str, Any]:
        """Serialize the Issue instance to a dictionary."""
        return typist.serialize(handler(self))

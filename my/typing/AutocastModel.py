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
    """
    Pydantic model that automatically casts field values during validation and serialization.

    Uses the Typist system to intelligently convert field values to their declared types
    during model construction and to simplify nested structures during serialization.
    """
    @pyd.model_validator(mode='before')
    @classmethod
    def _auto_validate(cls, data: dict) -> dict:
        """
        Automatically cast input data to match field types.

        Args:
            data: Input dictionary with potentially mistyped values.
        Returns:
            Dictionary with values cast to match model field types.
        """
        return typist._cast_model_members(data.items(), cls)

    @pyd.model_serializer(mode='wrap')
    def _auto_serialize(self, handler) -> dict[str, Any]:
        """
        Serialize the model instance with automatic type simplification.

        Args:
            handler: Default serialization handler.
        Returns:
            Serialized dictionary with simplified nested structures.
        """
        return typist.serialize(handler(self))

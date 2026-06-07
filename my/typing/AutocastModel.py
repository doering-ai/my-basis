############
### HEAD ###
############
### STANDARD
from typing import Any

### EXTERNAL
import pydantic as pyd

### INTERNAL
from .typecast import TypeCast
from .Typist import typist


############
### BODY ###
############
class AutocastModel(pyd.BaseModel):
    """Pydantic model that automatically casts field values during validation and serialization.

    When constructing an instance of a subclass, field values are intelligently cast to match their
    declared types using `Typist.flexcast()`. This eliminates boilerplate validators and makes
    models more permissive with input formats.

    During serialization, the model automatically simplifies nested structures in preparation for
    them to be saved to a flat mapping of some kind, be it YAML, JSON, SQL, or otherwise.
    Single-element lists become scalars, enums serialize to readable strings, and redundant nesting
    is flattened.
    """

    @pyd.model_validator(mode='before')
    @classmethod
    def _auto_validate(cls, data: dict) -> dict:
        """Automatically cast input data to match field types.

        Args:
            data: Input dictionary with potentially mistyped values.
        Returns:
            Dictionary with values cast to match model field types.
        """
        return TypeCast._cast_members(data, cls)

    @pyd.model_serializer(mode='wrap')
    def _auto_serialize(self, handler) -> dict[str, Any]:
        """Serialize the model instance with automatic type simplification.

        Args:
            handler: Default serialization handler.
        Returns:
            Serialized dictionary with simplified nested structures.
        """
        return typist.serialize(handler(self))

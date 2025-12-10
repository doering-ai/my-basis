############
### HEAD ###
############
### STANDARD
from typing import ClassVar

### EXTERNAL
import regex as re
import pydantic as pyd

### INTERNAL
from .meta_patterns import META_RGXS


############
### BODY ###
############
class Quantifier(pyd.RootModel[str]):
    RGX: ClassVar[re.Pattern] = META_RGXS['quant']

    data: str

    @pyd.model_validator(mode='after')
    def validate(self) -> 'Quantifier':
        assert self.RGX.fullmatch(self.data), f'Invalid quantifier: {self.data!r}'
        return self

    def __bool__(self) -> bool:
        return bool(self.data)

    @property
    def is_simple(self) -> bool:
        return self.data in ('', '?')

    @property
    def is_optional(self) -> bool:
        return bool(self.data) and (
            self.data[0] == '*' or self.data == '?' or self.data.startswith('{0,')
        )

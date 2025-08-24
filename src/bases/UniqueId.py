############
### HEAD ###
############
# Standard imports
from typing import ClassVar
from uuid import uuid4

# External imports
import regex as re
import pydantic as pyd

# Internal imports


############
### DATA ###
############
class UniqueId(pyd.RootModel[str]):
    """ Validates and operates on 32bit hex strings """
    RGX: ClassVar[re.Pattern] = re.compile(
        r'[[:xdigit:]]{8}-[[:xdigit:]]{4}-[[:xdigit:]]{4}-[[:xdigit:]]{4}-[[:xdigit:]]{12}', re.I
    )
    UID_LINE_RGX: ClassVar[re.Pattern] = re.compile(rf'(?m)\n?^[^\n]*{RGX.pattern}[^\n]*$', re.I)

    @pyd.field_validator('root', mode='after')
    @classmethod
    def validate_uid(cls, uid: str) -> str:
        assert cls.RGX.fullmatch(uid)
        return uid.lower()

    @classmethod
    def new(cls, uid: str = '') -> "UniqueId":
        return cls(uid or str(uuid4()))

    @classmethod
    def newstr(cls) -> str:
        return str(cls.new())

    def __hash__(self) -> int:
        return self.root.__hash__()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, UniqueId):
            return self.root == other.root
        elif isinstance(other, str):
            return self.root == other.lower()
        elif isinstance(other, int):
            return self.root == str(other).lower()
        return False

    def __str__(self) -> str:
        return self.root

    def __repr__(self) -> str:
        return self.root

    def __lt__(self, other: "UniqueId|str") -> bool:
        if isinstance(other, UniqueId):
            return self.root < other.root
        else:
            return self.root < other.lower()

    @classmethod
    def remove_uids(cls, text: str) -> str:
        return cls.UID_LINE_RGX.sub('', text)

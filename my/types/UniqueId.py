############
### HEAD ###
############
### STANDARD
from typing import ClassVar
from uuid import uuid4

### EXTERNAL
import regex as re
import pydantic as pyd

### INTERNAL


############
### BODY ###
############
class UniqueId(pyd.RootModel[str]):
    """A simple wrapper for uuid4 strings (32 hex digits, hyphenated), with validation & utilities.

    Also exported under the shorthand alias `Uid`.

    Attributes:
        root: The UUID string itself.

    Examples:
        Wrap an existing UUID string (normalized to lowercase), or generate a fresh one::

            >>> from my import Uid
            >>> uid = Uid('D6F00951-6E49-4C56-B443-56774EA3C71D')
            >>> str(uid)
            'd6f00951-6e49-4c56-b443-56774ea3c71d'
            >>> uid == 'D6F00951-6E49-4C56-B443-56774EA3C71D'
            True
            >>> bool(Uid.RGX.fullmatch(Uid.newstr()))
            True
    """

    RGX: ClassVar[re.Pattern] = re.compile(
        r'[[:xdigit:]]{8}-[[:xdigit:]]{4}-[[:xdigit:]]{4}-[[:xdigit:]]{4}-[[:xdigit:]]{12}', re.I
    )
    UID_LINE_RGX: ClassVar[re.Pattern] = re.compile(rf'(?m)\n?^[^\n]*{RGX.pattern}[^\n]*$', re.I)

    @pyd.field_validator('root', mode='after')
    @classmethod
    def validate_uid(cls, uid: str) -> str:
        """Validate and normalize a UUID string.

        Args:
            uid: UUID string to validate.
        Returns:
            Lowercase normalized UUID.
        Raises:
            AssertionError: If string is not a valid UUID format.
        """
        assert cls.RGX.fullmatch(uid)
        return uid.lower()

    @classmethod
    def new(cls, uid: str = '') -> 'UniqueId':
        """Create a new UniqueId, generating one if not provided.

        Args:
            uid: Optional UUID string. If empty, generates a new UUID.
        Returns:
            UniqueId instance.
        Examples:
            Wrap a known UUID (note the bare-string repr)::

                >>> from my import UniqueId
                >>> UniqueId.new('D6F00951-6E49-4C56-B443-56774EA3C71D')
                d6f00951-6e49-4c56-b443-56774ea3c71d
        """
        return cls(uid or str(uuid4()))

    @classmethod
    def newstr(cls) -> str:
        """Generate a new UUID as a string (just a convenience wrapper around `new()`)."""
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

    def __lt__(self, other: 'UniqueId|str') -> bool:
        if isinstance(other, UniqueId):
            return self.root < other.root
        else:
            return self.root < other.lower()

    @classmethod
    def remove_uids(cls, text: str) -> str:
        r"""Remove all lines containing UUIDs from the given text.

        Examples:
            Strip an identifier line from a block of text::

                >>> from my import UniqueId
                >>> text = 'keep me\nuid: d6f00951-6e49-4c56-b443-56774ea3c71d\nand me'
                >>> UniqueId.remove_uids(text)
                'keep me\nand me'
        """
        return cls.UID_LINE_RGX.sub('', text)


Uid = UniqueId

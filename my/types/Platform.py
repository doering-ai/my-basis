############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from enum import IntFlag
import platform
import itertools as it

### EXTERNAL

### INTERNAL
from ..utils import ut


############
### DATA ###
############
RGXS = ut.regex_dict(
    DOS=r'windows|dos|win',
    GNU=r'linux|gnu|unix|bsd|cygwin',
    MAC=r'darwin|mac|osx',
    IOS=r'\bios|iphone|apple',
    ANDROID=r'android|google',
    OLD=r'sunos|solaris|amigaos',
)
_SEARCH_RGXS = list(reversed(RGXS.items()))

_LOCAL: Platform | None = None
_COUNT = it.count(start=1)


def auto() -> int:
    """A custom implementation of `enum.auto()` that allows for bitwise flags."""
    return 1 << next(_COUNT)  # Super fancy version of `2**next(_COUNT)`! Gorgeous.


############
### BODY ###
############
class Platform(IntFlag):
    """An enumeration of supported platforms."""

    NONE = 0
    MOBILE = auto()

    GNU = auto()
    MAC = auto()
    DOS = auto()
    IOS = auto() | MOBILE | MAC
    ANDROID = auto() | MOBILE | GNU
    OLD = auto()

    ERR = OLD | NONE

    @classmethod
    def local(cls) -> Platform:
        """Detect the current platform."""
        global _LOCAL
        if not _LOCAL:
            uid = platform.system().lower().strip()
            key = next((_k.upper() for _k, _r in _SEARCH_RGXS if _r.search(uid)), 'NONE')
            _LOCAL = cls.__members__[key]
        return _LOCAL

    @staticmethod
    def _set_local(val: Platform | None) -> None:
        global _LOCAL
        _LOCAL = val

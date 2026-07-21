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
    """An enumeration of supported platforms, as combinable bitwise flags.

    The desktop members are `GNU`, `MAC`, and `DOS`; the mobile members `IOS` and `ANDROID` are
    defined as unions that include `MOBILE` and their parent desktop family, so flag containment
    checks read naturally. `NONE`, `OLD`, and `ERR` cover the degenerate cases.

    Examples:
        Test family membership via flag containment::

            >>> from my import Platform
            >>> Platform.MAC in Platform.IOS
            True
            >>> Platform.MOBILE in Platform.ANDROID
            True
            >>> Platform.DOS in Platform.IOS
            False

        Detect the platform of the current host (e.g. on a Linux machine)::

            >>> Platform.local()
            <Platform.GNU: 4>
    """

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
        """Detect the current platform, caching the result for subsequent calls.

        Returns:
            The member matching `platform.system()`, or `NONE` if nothing matches.
        """
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

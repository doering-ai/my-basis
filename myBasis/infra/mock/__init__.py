############
### HEAD ###
############
### STANDARD
from __future__ import annotations
import sys

### INTERNAL

############
### BODY ###
############
sb = sys.modules.get('sublime')
IS_LIVE: bool = sb is not None and getattr(sb, 'MODE', 'internal') != 'external'
__all__ = ['IS_LIVE']


def install() -> None:
    """Inject mock modules for sublime, sublime_plugin, and unittesting.

    Idempotent — safe to call multiple times.
    Uses setdefault so that a real ST runtime (which would have already populated sys.modules) is
    never overwritten.
    """
    global IS_LIVE
    if IS_LIVE:
        return
    from . import _sublime, _sublime_plugin, _unittesting

    # Import the mock modules *before* touching sys.modules so that any import-time errors surface
    # with a clear traceback.
    sys.modules.setdefault('sublime', _sublime)
    sys.modules.setdefault('sublime_plugin', _sublime_plugin)

    # Mock the whole unittesting package tree so sub-imports also resolve.
    sys.modules.setdefault('unittesting', _unittesting)
    sys.modules.setdefault('unittesting.core', _unittesting)
    sys.modules.setdefault('unittesting.helpers', _unittesting)

    IS_LIVE = True


if not IS_LIVE:
    install()

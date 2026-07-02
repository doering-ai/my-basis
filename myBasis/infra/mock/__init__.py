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
    Installing mocks never flips `IS_LIVE`: it stays `True` only when the *real* ``sublime``
    module was already present at import time (i.e. a live ST process).
    """
    if IS_LIVE:
        return
    from . import _sublime, _sublime_plugin, _unittesting, _sublime_api

    # Import the mock modules *before* touching sys.modules so that any import-time errors surface
    # with a clear traceback.
    sys.modules.setdefault('sublime', _sublime)
    sys.modules.setdefault('sublime_plugin', _sublime_plugin)
    sys.modules.setdefault('sublime_api', _sublime_api)

    # Mock the whole unittesting package tree so sub-imports also resolve.
    sys.modules.setdefault('unittesting', _unittesting)
    sys.modules.setdefault('unittesting.core', _unittesting)
    sys.modules.setdefault('unittesting.helpers', _unittesting)


if not IS_LIVE:
    install()

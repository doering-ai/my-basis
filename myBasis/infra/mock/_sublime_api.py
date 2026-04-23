############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import Any
from unittest.mock import MagicMock

### EXTERNAL

### INTERNAL

############
### DATA ###
############
# Catch-all: ALl attributes of the sublime API are lazily mocked.
_KNOWN_MOCKS = {}


def __getattr__(name: str) -> Any:
    return _KNOWN_MOCKS.setdefault(name, MagicMock(name=f'sublime_api.{name}'))

############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import Callable
from datetime import datetime
from pathlib import Path

### EXTERNAL
import pytest as pyt
import pydantic as pyd
import regex as re

### INTERNAL
from my import ut, env

re.DEFAULT_VERSION = re.VERSION1  # type: ignore

############
### DATA ###
############
MY_LOGS = env.path('MY_LOGS', '~/local/logs', mkdir=True)

############
### BODY ###
############
# --------
# I. Setup
# --------
ut.setup_logging(
    package='my',
    is_dev=True,
    logdir=MY_LOGS,
    fire_token=env.FIRE_TOKEN,
)


# ------------
# II. Fixtures
# ------------
type Patch = pyt.MonkeyPatch


@pyt.fixture
def patch(monkeypatch: Patch) -> Patch:
    """A fixture that provides a `MonkeyPatch` object for use in tests."""
    return monkeypatch


@pyt.fixture
def mock_posix(patch: Patch) -> Callable[[], datetime]:
    """Set al.posix() to always return a `datetime(2025-01-01)` object when called."""

    def mocked() -> datetime:
        return datetime(2025, 1, 1)

    patch.setattr(ut, 'posix', mocked)
    return mocked


# --------------
# III. Utilities
# --------------
def to_tuple(arg: object, base_type: type) -> tuple:
    """Convert an argument to a tuple if it is not already a tuple or the base type."""
    return (arg,) if (not isinstance(arg, tuple) or isinstance(arg, base_type)) else arg


def boolmap(
    *,
    false: list | None = None,
    true: list | None = None,
    base_type: type = str,
) -> list[tuple]:
    """Generate parameter sets for boolean tests.

    Args:
        false: List of argument tuples that should evaluate to `False`.
        true: List of argument tuples that should evaluate to `True`.
        base_type: The base type to check against when converting arguments to tuples. If an
            argument is not a tuple or is an instance of the base type, it will be converted to a
            single-element tuple.

    Returns:
        A valid list of tuple argument sets for `pytest.mark.parametrize()`.
    """
    return [
        *((*to_tuple(param, base_type), False) for param in (false or [])),
        *((*to_tuple(param, base_type), True) for param in (true or [])),
    ]

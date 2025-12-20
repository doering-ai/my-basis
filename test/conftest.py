############
### HEAD ###
############
### STANDARD
from typing import Callable
from datetime import datetime
from pathlib import Path

### EXTERNAL
import pytest as pyt
import pydantic as pyd
import regex as re

### INTERNAL
from my import ut, env

re.DEFAULT_VERSION = re.VERSION1

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
@pyt.fixture(scope='session')
def root() -> pyd.DirectoryPath:
    return Path(__file__).parent.parent.resolve()


@pyt.fixture
def mock_posix(monkeypatch) -> Callable[[], datetime]:
    """Set al.posix() to always return a `datetime(2025-01-01)` object when called."""

    def mocked() -> datetime:
        return datetime(2025, 1, 1)

    monkeypatch.setattr(ut, 'posix', mocked)
    return mocked


# --------------
# III. Utilities
# --------------
def to_tuple(arg: object, base_type: type) -> tuple:
    return (arg,) if (not isinstance(arg, tuple) or isinstance(arg, base_type)) else arg


def boolmap(
    *, false: list | None = None, true: list | None = None, base_type: type = str
) -> list[tuple]:
    """Generate parameter sets for boolean tests.

    Args:
        true (list[tuple]): List of argument tuples that should evaluate to `True`.
        false (list[tuple]): List of argument tuples that should evaluate to `False`.

    Returns:
        list[tuple]: Combined list of argument tuples with expected boolean results.
    """
    return [
        *(to_tuple(param, base_type) + (False,) for param in (false or [])),
        *(to_tuple(param, base_type) + (True,) for param in (true or [])),
    ]

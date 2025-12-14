############
### HEAD ###
############
### STANDARD
from typing import Callable, TypeVar
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
def _normalize_tuples(args: list) -> list[tuple]:
    """Normalize input into a list of tuples.

    Args:
        args (list[T] | T): Input arguments.

    Returns:
        list[tuple]: Normalized list of tuples.
    """
    return [(arg if isinstance(arg, tuple) else (arg,)) for arg in args]


def boolmap(*, false: list, true: list) -> list[tuple]:
    """Generate parameter sets for boolean tests.

    Args:
        true (list[tuple]): List of argument tuples that should evaluate to `True`.
        false (list[tuple]): List of argument tuples that should evaluate to `False`.

    Returns:
        list[tuple]: Combined list of argument tuples with expected boolean results.
    """
    return [
        *(f + (False,) for f in _normalize_tuples(false)),
        *(t + (True,) for t in _normalize_tuples(true)),
    ]

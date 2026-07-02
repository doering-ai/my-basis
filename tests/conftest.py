############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from collections.abc import Callable
from datetime import datetime

### EXTERNAL
import pytest as pyt
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
    """Set ut.posix() to always return a `datetime(2025-01-01)` object when called."""

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


def type_ids(cases: list[tuple], index: int = -2) -> list[str]:
    """Derive readable pytest ids from the target-type element of each parametrize case.

    Large parametrize matrices (60+ rows) otherwise collapse any non-scalar leading argument
    (a list, dict, set, ...) to an opaque `dataN` id, which makes failures/selection painful to
    read (`test_check[data37-target37]`). Stringifying just the target-type element gives every
    case a readable id -- collisions (several rows sharing one target type) are still resolved by
    pytest's own numeric-suffix de-duplication, which is far more legible than a blanket `dataN`.

    Args:
        cases: Parameter tuples as passed to `@pyt.mark.parametrize`.
        index: Position of the target-type argument within each tuple. Defaults to the
            second-to-last slot, matching this suite's `data, tvar/target, expected` convention.

    Returns:
        One id string per case, suitable for `@pyt.mark.parametrize(..., ids=type_ids(CASES))`.
    """
    return [tvar.__name__ if isinstance(tvar := case[index], type) else str(tvar) for case in cases]


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

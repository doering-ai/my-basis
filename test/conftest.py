############
### HEAD ###
############
### STANDARD
from typing import Callable
from datetime import datetime
from pathlib import Path
import os

### EXTERNAL
import pytest as pyt
import pydantic as pyd
import regex as re

### INTERNAL
from my.base import utils as ut

re.DEFAULT_VERSION = re.VERSION1

############
### DATA ###
############
MY_LOGS = Path(os.environ.get('MY_LOGS', '~/local/logs')).expanduser().resolve()
FIRE_TOKEN = os.environ.get('FIRE_TOKEN', '')

############
### BODY ###
############
ut.setup_logging(
    package='my',
    is_dev=True,
    logdir=MY_LOGS,
    fire_token=FIRE_TOKEN,
)


@pyt.fixture(scope='session')
def root() -> pyd.DirectoryPath:
    return Path(__file__).parent.parent.resolve()


# @pyt.fixture(scope='session')
# def examples(root: pyd.DirectoryPath) -> pyd.DirectoryPath:
#     path = root / 'test/examples'
#     assert path.exists() and path.is_dir()
#     return path


@pyt.fixture(scope='function')
def mock_posix(monkeypatch) -> Callable[[], datetime]:
    """ Set al.posix() to always return a `datetime(2025-01-01)` object when called. """
    def mocked() -> datetime:
        return datetime(2025, 1, 1)

    monkeypatch.setattr(ut, 'posix', mocked)
    return mocked

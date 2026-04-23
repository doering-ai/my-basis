from .MyEnum import MyEnum
from .UniqueId import UniqueId, Uid
from .Span import Span
from .Buffer import Buffer
from .Predicate import Predicate
from .Command import Command

from ..utils import ut
from unittest.mock import MagicMock

if ut.is_installed('sqlalchemy'):
    from .MyEnumRow import MyEnumRow, MyEnumSetRow
else:
    MyEnumRow = MagicMock(name='my.types.MyEnumRow')
    MyEnumSetRow = MagicMock(name='my.types.MyEnumSetRow')

__all__ = [
    'MyEnum',
    'UniqueId',
    'Uid',
    'Span',
    'Buffer',
    'Predicate',
    'MyEnumRow',
    'MyEnumSetRow',
    'Command',
]


def __getattr__(name: str):
    """Lazily load submodules when attributes are accessed."""
    if name in __all__:
        return globals()[name]

    return MagicMock(name=f'my.types.{name}')

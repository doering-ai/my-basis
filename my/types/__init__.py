"""Extensible, Ergonomic Miscellaneous Types

The `types` subpackage provides enhanced data structures and type abstractions that extend Python's built-in types with domain-specific functionality. These types are designed to integrate seamlessly with Pydantic for validation and serialization.
"""
from .MyEnum import MyEnum
from .UniqueId import UniqueId, Uid
from .Span import Span
from .Buffer import Buffer
from .Predicate import Predicate
from .Command import Command
from .Platform import Platform

from ..utils import ut

if ut.is_installed('sqlalchemy'):
    from .MyEnumRow import MyEnumRow, MyEnumSetRow
else:
    from unittest.mock import MagicMock
    MyEnumRow = MagicMock(name='my.types.MyEnumRow')
    MyEnumSetRow = MagicMock(name='my.types.MyEnumSetRow')

__all__ = [
    'Buffer',
    'Command',
    'MyEnum',
    'MyEnumRow',
    'MyEnumSetRow',
    'Platform',
    'Predicate',
    'Span',
    'Uid',
    'UniqueId',
]

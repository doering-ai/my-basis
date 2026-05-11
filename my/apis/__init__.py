"""API Wrappers

This subpackage provides convenient interfaces for external services and system resources.
Currently it focuses on two primary concerns: environment variable management and Google Sheets integration.
"""
from .Environment import Environment, ENV, env
from .Filesystem import Filesystem, FS, fs, PATHS

from ..utils import ut
from unittest.mock import MagicMock

if ut.is_installed('pandas', 'googleapiclient'):
    from .GoogleSheet import GoogleSheet
else:
    GoogleSheet = MagicMock(name='my.apis.GoogleSheet')

__all__ = ['GoogleSheet', 'Environment', 'ENV', 'env', 'Filesystem', 'FS', 'fs', 'PATHS']

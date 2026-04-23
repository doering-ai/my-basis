from .Environment import Environment, env

from ..utils import ut
from unittest.mock import MagicMock

if not ut.is_installed('pandas', 'googleapiclient'):
    GoogleSheet = MagicMock(name='my.apis.GoogleSheet')
else:
    from .GoogleSheet import GoogleSheet

__all__ = ['GoogleSheet', 'Environment', 'env']

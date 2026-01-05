from .IterUtils import IterUtils, iter_utils
from .SyntaxUtils import SyntaxUtils, syntax_utils  # USES: iter
from .SemanticUtils import SemanticUtils, semantic_utils  # USES: iter
from .TextUtils import TextUtils, text_utils  # USES: iter
from .SystemUtils import SystemUtils, system_utils  # USES: text


class Utils(IterUtils, TextUtils, SystemUtils, SemanticUtils, SyntaxUtils):
    """A class combining all of the the utility classes into one convenient static interface."""


ut = Utils
utils = Utils


__all__ = [
    'Utils',
    'ut',
    'utils',
    'IterUtils',
    'iter_utils',
    'TextUtils',
    'text_utils',
    'SystemUtils',
    'system_utils',
    'SemanticUtils',
    'semantic_utils',
    'SyntaxUtils',
    'syntax_utils',
]

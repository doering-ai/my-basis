from .IterUtils import IterUtils, iter_utils
from .SyntaxUtils import SyntaxUtils, syntax_utils  # <- iter
from .TextUtils import TextUtils, text_utils  # <- iter
from .SemanticUtils import SemanticUtils, semantic_utils  # <- text, iter
from .SystemUtils import SystemUtils, system_utils  # <- text (<- iter)
from .MetricUtils import MetricUtils, metric_utils  # <- system (<- text <- iter)


class Utils(IterUtils, TextUtils, SystemUtils, SemanticUtils, SyntaxUtils, MetricUtils):
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
    'MetricUtils',
    'metric_utils',
]

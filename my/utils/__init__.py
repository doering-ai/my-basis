"""Pure, Typed Functional Utilities.

The `utils` subpackage provides a comprehensive collection of utility functions organized into
specialized classes that are combined into a unified `Utils` interface and exported under the alias
`ut`. This design allows methods to be called as `ut.method()` regardless of which utility class
defines them, providing a clean, flat namespace for common operations.

Individual utility classes can still be imported for more specific use cases or when a smaller
import footprint is desired (e.g. `from my.utils.IterUtils import IterUtils`).

`MetricUtils` remains available through the same combined facade, but its optional Pandas,
Logfire, and OpenTelemetry dependencies are imported only when a metrics attribute is first used.

Note -- `utils` is the *class*, on purpose:
    Both `utils` and `ut` are bound to the `Utils` **class** itself (`utils = ut = Utils`), not to
    this submodule. That is deliberate: `from my import utils as ut` hands consumers the aggregating
    facade, so `ut.clean_string(...)`, `ut.validate_dir(...)`, etc. resolve across every base
    class through one flat namespace.

    The consequence is that the `my.utils` attribute *is* the `Utils` class, which **shadows** this
    submodule: `my.utils.iter_utils` does not resolve (the class has no such attribute) and
    `hasattr(my.utils, 'iter_utils')` is `False`. This is a design choice, not a bug -- do **not**
    "fix" it by dropping `utils` from the top-level facade; downstream code (e.g. `means`, via
    `from my import utils as ut`) depends on `utils` naming the class. See the guard test in
    `tests/utils/test_utils_facade.py`.

    To reach a specific singleton or class instead, use the names the top-level facade re-exports
    (`my.iter_utils`, `my.system_utils`, `my.SystemUtils`, ...) or import from the concrete module
    (`from my.utils.SystemUtils import SystemUtils`).
"""

from types import ModuleType
from typing import TYPE_CHECKING, Any, ClassVar
import importlib
import sys

import regex as re

from .IterUtils import IterUtils, iter_utils
from .SyntaxUtils import SyntaxUtils, syntax_utils  # <- iter
from .TextUtils import TextUtils, text_utils  # <- iter
from .SemanticUtils import SemanticUtils, semantic_utils  # <- text, iter
from .SystemUtils import SystemUtils, system_utils  # <- text, iter

if TYPE_CHECKING:
    from .MetricUtils import MetricUtils, metric_utils


#: Names inherited from `MetricUtils` by the historical all-in-one facade. Keeping this
#: lightweight manifest here lets a typo fail without warming the optional metrics stack.
_METRIC_FACADE_ATTRS = frozenset(
    {
        'LOCAL_OTLP_HOSTS',
        'LOGGERS',
        'METRICS_INSTALLED',
        'METRICS_SETUP',
        'SAFE_FIRE_KWARGS',
        'TELEMETRY_IDENTITY',
        'TELEMETRY_READY',
        'WARNINGS_SETUP',
        'get_package_name',
        'measure_context',
        'monitor',
        'setup_fire_logging',
        'setup_logging',
        'setup_metrics',
        'setup_py_logging',
        'setup_warnings',
    }
)
_METRIC_MODULE = f'{__name__}.MetricUtils'


def _load_metric_utils() -> type:
    """Load and cache the concrete metrics class only when its public surface is requested."""
    module = importlib.import_module(_METRIC_MODULE)
    metric_cls = module.MetricUtils
    globals()['MetricUtils'] = metric_cls
    globals()['metric_utils'] = module.metric_utils
    return metric_cls


class _UtilsMeta(type):
    """Bridge the historical combined class to its optional metrics base on demand."""

    def __getattr__(cls, name: str) -> Any:
        if name not in _METRIC_FACADE_ATTRS and _METRIC_MODULE not in sys.modules:
            raise AttributeError(f'type {cls.__name__!r} has no attribute {name!r}')

        metric_cls = _load_metric_utils()
        for base in metric_cls.__mro__:
            if name in base.__dict__:
                descriptor = base.__dict__[name]
                if isinstance(descriptor, (classmethod, staticmethod)) or callable(descriptor):
                    type.__setattr__(cls, name, descriptor)
                    return getattr(cls, name)
                return getattr(metric_cls, name)
        raise AttributeError(f'type {cls.__name__!r} has no attribute {name!r}')

    def __dir__(cls) -> list[str]:
        return sorted(set(type.__dir__(cls)) | _METRIC_FACADE_ATTRS)


class _UtilsModule(ModuleType):
    """Keep a direct submodule import from replacing the package's class facade."""

    def __getattribute__(self, name: str) -> Any:
        value = ModuleType.__getattribute__(self, name)
        if name == 'MetricUtils' and isinstance(value, ModuleType):
            metric_cls = value.MetricUtils
            namespace = ModuleType.__getattribute__(self, '__dict__')
            namespace['MetricUtils'] = metric_cls
            namespace['metric_utils'] = value.metric_utils
            return metric_cls
        return value


sys.modules[__name__].__class__ = _UtilsModule


if TYPE_CHECKING:

    class Utils(IterUtils, TextUtils, SystemUtils, SemanticUtils, SyntaxUtils, MetricUtils):
        """A class combining all of the utility classes into one convenient static interface."""

        RGXS: ClassVar[dict[str, re.Pattern]] = TextUtils.RGXS | SystemUtils.RGXS

else:

    class Utils(
        IterUtils, TextUtils, SystemUtils, SemanticUtils, SyntaxUtils, metaclass=_UtilsMeta
    ):
        """A class combining all utility classes while loading optional metrics on demand."""

        # `TextUtils` and `SystemUtils` each declare their own `RGXS` ClassVar; plain multiple
        # inheritance would let MRO order silently shadow one with the other (whichever base is
        # listed first "wins" for every subclass, including this one), leaving classmethods that
        # were written against the shadowed dict (e.g. `SystemUtils.from_file`) raising `KeyError`
        # the moment they're invoked through the combined `Utils`/`ut` facade instead of their own
        # class directly. Re-merge both dicts explicitly so every inherited method sees its keys.
        RGXS: ClassVar[dict[str, re.Pattern]] = TextUtils.RGXS | SystemUtils.RGXS


def __getattr__(name: str) -> object:
    """Lazily expose the concrete metrics class and singleton from this package."""
    if name in {'MetricUtils', 'metric_utils'}:
        _load_metric_utils()
        return globals()[name]
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


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

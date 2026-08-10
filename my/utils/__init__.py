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
_METRIC_STATIC_METHODS = frozenset({'setup_logging', 'setup_warnings'})
_METRIC_CLASS_METHODS = frozenset(
    {
        'get_package_name',
        'measure_context',
        'monitor',
        'setup_fire_logging',
        'setup_metrics',
        'setup_py_logging',
    }
)
_METRIC_MODULE = f'{__name__}.MetricUtils'


def _load_metric_utils() -> type:
    """Load and activate the concrete metrics base when its public surface is requested."""
    module = importlib.import_module(_METRIC_MODULE)
    return _activate_metric_utils(module.MetricUtils)


def _uninitialized_metric_method(*args: Any, **kwargs: Any) -> Any:
    """Stand in for a metric descriptor until its first binding request."""
    raise RuntimeError('Lazy metric descriptor was invoked without binding.')


class _LazyMetricAttribute:
    """Load a concrete metric class attribute when normal MRO lookup reaches this base."""

    def __init__(self, name: str):
        self.name = name

    def __get__(self, instance: object, owner: type | None = None) -> Any:
        return getattr(_load_metric_utils(), self.name)


class _LazyMetricStaticMethod(staticmethod):
    """A statically inspectable method descriptor that loads its concrete definition on bind."""

    def __init__(self, name: str):
        super().__init__(_uninitialized_metric_method)
        self.name = name

    def __get__(self, instance: object, owner: type | None = None) -> Any:
        descriptor = _load_metric_utils().__dict__[self.name]
        return descriptor.__get__(instance, owner)


class _LazyMetricClassMethod(classmethod):
    """A statically inspectable classmethod that loads its concrete definition on bind."""

    def __init__(self, name: str):
        super().__init__(_uninitialized_metric_method)
        self.name = name

    def __get__(self, instance: object, owner: type | None = None) -> Any:
        descriptor = _load_metric_utils().__dict__[self.name]
        return descriptor.__get__(instance, owner)


if TYPE_CHECKING:
    from .MetricUtils import MetricUtils, metric_utils

    _LazyMetricUtils = MetricUtils

else:

    def _build_lazy_metric_base() -> type:
        """Build the lightweight runtime base without importing optional metric dependencies."""
        namespace: dict[str, object] = {
            name: _LazyMetricAttribute(name)
            for name in _METRIC_FACADE_ATTRS - _METRIC_STATIC_METHODS - _METRIC_CLASS_METHODS
        }
        namespace.update({name: _LazyMetricStaticMethod(name) for name in _METRIC_STATIC_METHODS})
        namespace.update({name: _LazyMetricClassMethod(name) for name in _METRIC_CLASS_METHODS})
        return type('_LazyMetricUtils', (), namespace)

    _LazyMetricUtils = _build_lazy_metric_base()


class _UtilsModule(ModuleType):
    """Keep a direct submodule import from replacing the package's class facade."""

    def __getattribute__(self, name: str) -> Any:
        value = ModuleType.__getattribute__(self, name)
        if name == 'MetricUtils' and isinstance(value, ModuleType):
            return _activate_metric_utils(value.MetricUtils)
        return value


sys.modules[__name__].__class__ = _UtilsModule


class Utils(
    IterUtils,
    TextUtils,
    SystemUtils,
    SemanticUtils,
    SyntaxUtils,
    _LazyMetricUtils,
):
    """Combine eager utility bases with a metrics base activated on first demand."""

    # `TextUtils` and `SystemUtils` each declare their own `RGXS` ClassVar; plain multiple
    # inheritance would let MRO order silently shadow one with the other (whichever base is
    # listed first "wins" for every subclass, including this one), leaving classmethods that
    # were written against the shadowed dict (e.g. `SystemUtils.from_file`) raising `KeyError`
    # the moment they're invoked through the combined `Utils`/`ut` facade instead of their own
    # class directly. Re-merge both dicts explicitly so every inherited method sees its keys.
    RGXS: ClassVar[dict[str, re.Pattern]] = TextUtils.RGXS | SystemUtils.RGXS


def _activate_metric_utils(metric_cls: type) -> type:
    """Replace the lightweight base with the concrete class and publish both aliases."""
    bases = Utils.__bases__
    new_bases = tuple(
        metric_cls
        if base is _LazyMetricUtils
        or (base.__module__ == _METRIC_MODULE and base.__name__ == 'MetricUtils')
        else base
        for base in bases
    )
    if new_bases != bases:
        # Changing the existing class keeps already-defined downstream subclasses coherent.
        Utils.__bases__ = new_bases
    globals().update(MetricUtils=metric_cls, metric_utils=metric_cls)
    return metric_cls


def __getattr__(name: str) -> object:
    """Lazily expose the concrete metrics class and singleton from this package."""
    if name in {'MetricUtils', 'metric_utils'}:
        _load_metric_utils()
        return globals()[name]
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


def __dir__() -> list[str]:
    """Advertise the complete public package surface before metrics are loaded."""
    return sorted(__all__)


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

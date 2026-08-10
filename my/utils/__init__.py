"""Pure, Typed Functional Utilities.

The `utils` subpackage provides a comprehensive collection of utility functions organized into
specialized classes that are combined into a unified `Utils` interface and exported under the alias
`ut`. This design allows methods to be called as `ut.method()` regardless of which utility class
defines them, providing a clean, flat namespace for common operations.

Individual utility classes can still be imported for more specific use cases or when a smaller
import footprint is desired (e.g. `from my.utils.IterUtils import IterUtils`).

`MetricUtils` remains available through the same combined facade, but its optional Pandas,
Logfire, and OpenTelemetry dependencies are imported only when a metrics method is called or the
implementation submodule is explicitly imported.

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

from collections.abc import Callable
from types import ModuleType
from typing import Any, ClassVar
import importlib
import importlib.util
import logging as lg
import sys

import pydantic as pyd
import regex as re

from ._UtilsBase import _UtilsBase
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
_METRIC_PRIVATE_ATTRS = frozenset(
    {
        '_configure_cached_logger',
        '_configure_fire',
        '_editable_distribution_name',
        '_export_python_logs',
        '_fire_settings',
        '_guard',
        '_instrument',
        '_instrument_app',
        '_instrument_system_metrics',
        '_measure',
        '_resolve_fire_token',
        '_resolve_log_level',
        '_resolve_setup_package',
        '_source_project_name',
        '_try_fire_logging',
        '_validate_fire_configuration',
    }
)
_METRIC_MODULE = f'{__name__}.MetricUtils'


def _metrics_extra_available() -> bool:
    """Check the optional stack without importing any of its runtime packages."""
    for name in ('pandas', 'logfire', 'opentelemetry'):
        try:
            if importlib.util.find_spec(name) is None:
                return False
        except (ImportError, ModuleNotFoundError):
            return False
    return True


class _MetricUtilsMeta(type):
    """Resolve implementation-private helpers without weakening the public cold facade."""

    def __getattr__(cls, name: str) -> Any:
        if name not in _METRIC_PRIVATE_ATTRS:
            raise AttributeError(f'type {cls.__name__!r} has no attribute {name!r}')
        _load_metric_implementation()
        try:
            return type.__getattribute__(cls, name)
        except AttributeError:
            raise AttributeError(f'type {cls.__name__!r} has no attribute {name!r}') from None


class MetricUtils(_UtilsBase, metaclass=_MetricUtilsMeta):
    """Methods for logging, telemetry, and measurement with cold call-time implementations.

    These methods require the optional `metrics` dependency. Their descriptors, signatures,
    class state, and inheritance remain available to the combined facade without importing
    Pandas, Logfire, OpenTelemetry, or the implementation module.
    """

    METRICS_INSTALLED: ClassVar[bool] = _metrics_extra_available()
    WARNINGS_SETUP: ClassVar[bool] = False
    METRICS_SETUP: ClassVar[bool] = False
    LOGGERS: ClassVar[dict[str, lg.Logger]] = {}
    TELEMETRY_READY: ClassVar[set[str]] = set()
    SAFE_FIRE_KWARGS: ClassVar[frozenset[str]] = frozenset(
        {'inspect_arguments', 'scrubbing', 'send_to_logfire'}
    )
    TELEMETRY_IDENTITY: ClassVar[re.Pattern[str]] = re.compile(r'[A-Za-z0-9][A-Za-z0-9._/-]{0,127}')
    LOCAL_OTLP_HOSTS: ClassVar[frozenset[str]] = frozenset(
        {'127.0.0.1', '::1', 'host.containers.internal', 'localhost', 'otel-collector'}
    )

    @classmethod
    def setup_py_logging(
        cls,
        logdir: pyd.DirectoryPath,
        is_dev: bool,
        package: str,
        logger: lg.Logger | None = None,
        app: Any | None = None,
        maxsize: int = 2**26,
        maxcount: int = 2**10,
    ) -> lg.Logger:
        """Load and invoke the rotating-file logging implementation."""
        return _call_metric_method(
            'setup_py_logging',
            cls,
            logdir,
            is_dev,
            package,
            logger,
            app,
            maxsize,
            maxcount,
        )

    @classmethod
    def setup_fire_logging(
        cls,
        fire_token: str,
        package: str,
        logger: lg.Logger,
        is_dev: bool = True,
        app: Any | None = None,
        export_logs: bool = False,
        system_metrics: bool = False,
        log_level: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Load and invoke the Logfire configuration implementation."""
        return _call_metric_method(
            'setup_fire_logging',
            cls,
            fire_token,
            package,
            logger,
            is_dev,
            app,
            export_logs,
            system_metrics,
            log_level,
            **kwargs,
        )

    @classmethod
    def get_package_name(cls) -> str:
        """Load the implementation and resolve the current distribution name."""
        return _call_metric_method('get_package_name', cls)

    @staticmethod
    def setup_logging(
        logdir: pyd.DirectoryPath,
        is_dev: bool,
        fire_token: str,
        package: str = '',
        logger: lg.Logger | None = None,
        app: Any | None = None,
        maxsize: int = 2**26,
        maxcount: int = 2**10,
        export_logs: bool = False,
        system_metrics: bool = False,
        log_level: str | None = None,
        **fire_kwargs: Any,
    ) -> lg.Logger:
        """Load and invoke the combined Python and Logfire setup implementation."""
        return _call_metric_method(
            'setup_logging',
            MetricUtils,
            logdir,
            is_dev,
            fire_token,
            package,
            logger,
            app,
            maxsize,
            maxcount,
            export_logs,
            system_metrics,
            log_level,
            **fire_kwargs,
        )

    @staticmethod
    def setup_warnings():
        """Load and invoke the warning-filter setup implementation."""
        return _call_metric_method('setup_warnings', MetricUtils)

    @classmethod
    def setup_metrics(cls, metrics: pyd.DirectoryPath, logger: lg.Logger):
        """Load and invoke the Prometheus directory setup implementation."""
        return _call_metric_method('setup_metrics', cls, metrics, logger)

    @classmethod
    def measure_context(cls, name: str, counter: dict[str, float]):
        """Load and return the metric timing context manager."""
        return _call_metric_method('measure_context', cls, name, counter)

    @classmethod
    def monitor(cls, *args: Any, **kwargs: Any) -> Callable:
        """Load and return the Logfire instrumentation decorator."""
        return _call_metric_method('monitor', cls, *args, **kwargs)


# These wrappers are the public class, including for direct submodule imports and
# documentation. Their implementation globals remain here so calls retain the cold boundary.
MetricUtils.__module__ = _METRIC_MODULE
for _metric_method_name in _METRIC_STATIC_METHODS | _METRIC_CLASS_METHODS:
    _metric_descriptor = MetricUtils.__dict__[_metric_method_name]
    _metric_descriptor.__func__.__module__ = _METRIC_MODULE

_METRIC_CLASS = MetricUtils
metric_utils = MetricUtils


def _register_metric_implementation(metric_impl: type) -> type[MetricUtils]:
    """Attach private helpers and synchronize availability after the implementation imports."""
    for name, descriptor in metric_impl.__dict__.items():
        if (
            name.startswith('_')
            and not (name.startswith('__') and name.endswith('__'))
            and name not in MetricUtils.__dict__
        ):
            setattr(MetricUtils, name, descriptor)
    MetricUtils.METRICS_INSTALLED = metric_impl.METRICS_INSTALLED
    return MetricUtils


def _load_metric_implementation() -> type:
    """Import the implementation and restore package aliases importlib temporarily shadows."""
    module = importlib.import_module(_METRIC_MODULE)
    implementation = module._MetricUtilsImplementation
    globals().update(MetricUtils=_METRIC_CLASS, metric_utils=_METRIC_CLASS)
    return implementation


def _call_metric_method(name: str, owner: type, *args: Any, **kwargs: Any) -> Any:
    """Bind one implementation descriptor to the public class or requesting subclass."""
    descriptor = _load_metric_implementation().__dict__[name]
    return descriptor.__get__(None, owner)(*args, **kwargs)


class _UtilsModule(ModuleType):
    """Keep a direct submodule import from replacing the package's class facade."""

    def __getattribute__(self, name: str) -> Any:
        value = ModuleType.__getattribute__(self, name)
        if name == 'MetricUtils' and isinstance(value, ModuleType):
            namespace = ModuleType.__getattribute__(self, '__dict__')
            namespace.update(MetricUtils=_METRIC_CLASS, metric_utils=_METRIC_CLASS)
            return _METRIC_CLASS
        return value


sys.modules[__name__].__class__ = _UtilsModule


class Utils(
    IterUtils,
    TextUtils,
    SystemUtils,
    SemanticUtils,
    SyntaxUtils,
    MetricUtils,
):
    """Combine eager utility bases with the cold public metrics contract."""

    # `TextUtils` and `SystemUtils` each declare their own `RGXS` ClassVar; plain multiple
    # inheritance would let MRO order silently shadow one with the other (whichever base is
    # listed first "wins" for every subclass, including this one), leaving classmethods that
    # were written against the shadowed dict (e.g. `SystemUtils.from_file`) raising `KeyError`
    # the moment they're invoked through the combined `Utils`/`ut` facade instead of their own
    # class directly. Re-merge both dicts explicitly so every inherited method sees its keys.
    RGXS: ClassVar[dict[str, re.Pattern]] = TextUtils.RGXS | SystemUtils.RGXS


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

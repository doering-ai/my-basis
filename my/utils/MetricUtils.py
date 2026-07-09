############
### HEAD ###
############
### STANDARD
from collections.abc import Callable
from pathlib import Path
from time import perf_counter_ns
from typing import Any, ClassVar
from types import FunctionType
import contextlib as ctx
import functools as ft
import importlib.metadata as impm
import logging as lg
import logging.handlers as lgh
import os
import subprocess as sbp
import sys
import warnings
import inspect

### EXTERNAL
import pydantic as pyd

### INTERNAL (NOTE: If adding new internal imports, update the comments in `__init__.py`)
from ._UtilsBase import _UtilsBase
from .SystemUtils import SystemUtils

INSTALLED: bool = True
try:
    import pandas as pd
    from opentelemetry.metrics import Counter as OpenTelemetryCounter
    import logfire as fire
except ImportError:
    INSTALLED = False


############
### DATA ###
############
type Metrics = OpenTelemetryCounter | dict[str, int] | pd.Series


############
### BODY ###
############
class MetricUtils(_UtilsBase):
    """Methods deal with logging, telemetry, and other measurement tasks.

    ```{important}
    These methods are only present if the **optional** `metrics` dependency is installed.
    If you try to call them without it, an `ImportError` will be thrown.
    ```
    """

    METRICS_INSTALLED: ClassVar[bool] = INSTALLED
    WARNINGS_SETUP: ClassVar[bool] = False
    METRICS_SETUP: ClassVar[bool] = False
    LOGGERS: ClassVar[dict[str, lg.Logger]] = {}

    @staticmethod
    def _guard[F: FunctionType](fn: F) -> F:
        @ft.wraps(fn)
        def _wfn(*args, **kwargs):
            if not MetricUtils.METRICS_INSTALLED:
                name = fn.__name__
                raise ImportError(f'`utils.{name}()` requires the optional `[metrics]` dependency.')
            return fn(*args, **kwargs)

        return _wfn  # type: ignore

    # -----------
    # `1` LOGGING
    # -----------
    @classmethod
    @_guard
    def setup_py_logging(
        cls,
        logdir: pyd.DirectoryPath,
        is_dev: bool,
        package: str,
        logger: lg.Logger | None = None,
        app: Any | None = None,
        maxsize: int = 2**26,  # 64 MB
        maxcount: int = 2**10,  # 1024 backups
    ) -> lg.Logger:
        """Configure Python file-based logging with rotation.

        Args:
            logdir: Directory for log files.
            is_dev: If True, use DEBUG level; otherwise INFO.
            package: Package name for logger identification.
            logger: Existing logger to configure, or None to create new.
            app: Optional ASGI app to register logger with.
            maxsize: Maximum log file size in bytes (default: 64 MB).
            maxcount: Maximum number of backup files (default: 1024).
        Returns:
            Configured Logger instance.
        """
        # I. Validate log directory and logging object
        SystemUtils.validate_dir(logdir)
        if logger is None:
            try:
                name = impm.metadata(package)['Name']
            except impm.PackageNotFoundError:
                name = package
            logger = lg.getLogger(name)

        # II. Name and setup a new file in this dir
        file = logdir / f'{logger.name}_{SystemUtils.posix().strftime("%y%m%d-%H%M%S")}.log'
        assert not file.exists(), f'Log file {file} already exists.'

        file_handler = lgh.RotatingFileHandler(file, maxBytes=maxsize, backupCount=maxcount)
        file_handler.setLevel(lg.DEBUG if is_dev else lg.INFO)
        file_handler.setFormatter(lg.Formatter('[%(asctime)s %(levelname)s] %(message)s'))

        # III. Register handler(s) with logger, defaulting to the universal one
        logger.addHandler(file_handler)

        # IV. Register logger with our ASGI HTTPS app, if present
        if app is not None:
            for handler in logger.handlers:
                app.logger.addHandler(handler)
            app.logger.setLevel(logger.level)
            app.config['DEBUG'] = is_dev

        return logger

    @classmethod
    @_guard
    def setup_fire_logging(
        cls,
        fire_token: str,
        package: str,
        logger: lg.Logger,
        is_dev: bool = True,
        app: Any | None = None,
        **kwargs: Any,
    ) -> None:
        """Configure Logfire observability and logging.

        Args:
            fire_token: Logfire API token.
            package: Package name for service identification.
            logger: Logger to attach Logfire handler to.
            is_dev: If True, use development mode with console output (default: True).
            app: Optional ASGI app to instrument.
            **kwargs: Additional configuration options for Logfire.
        Raises:
            AssertionError: If fire_token or package is missing.
        """
        assert fire_token and package, 'Tried to initialize fire logging w/o token or package.'

        try:
            name = impm.metadata(package)['Name']
            version = impm.version(package)
        except impm.PackageNotFoundError:
            name = package
            version = '0.0.0'

        # I. Choose basic configuration settings
        settings: dict = dict(
            token=fire_token,
            service_name=name,
            service_version=version,
            environment='development' if is_dev else 'production',
            send_to_logfire=not is_dev,
            scrubbing=False,
            inspect_arguments=True,
        )
        if is_dev:
            settings['console'] = fire.ConsoleOptions(
                min_log_level='debug',
                span_style='indented',
                show_project_link=False,
            )
        if kwargs:
            settings |= kwargs
        fire.configure(**settings)

        # II. Register special handlers
        # II.i. Automatically record performance metrics
        fire.instrument_system_metrics()
        # fire.log_slow_async_callbacks() # NOTE: not for now?
        # fire.instrument_pydantic() # NOTE: done in pyproject.toml

        # II.ii. Register logfire w/ the default python logger
        logfire_handler = fire.LogfireLoggingHandler()
        logfire_handler.setLevel(lg.DEBUG if is_dev else lg.INFO)
        logger.addHandler(logfire_handler)

        # II.iii. Register logfire with our ASGI HTTPS app
        if app is not None:
            # see opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation
            # Check if aiohtpp is present:
            if 'aiohttp' in sys.modules:
                fire.instrument_aiohttp_client()
            app.asgi_app = fire.instrument_asgi(app.asgi_app)

    @classmethod
    @_guard
    def get_package_name(cls) -> str:
        """Retrieve the current package name from metadata."""
        current_module = sys.modules[__name__]
        package_name = current_module.__package__ or __name__
        root_package = package_name.split('.', 1)[0]
        ret = impm.packages_distributions().get(root_package, root_package)
        if isinstance(ret, list):
            ret = ret[0]
        return ret

    @staticmethod
    @_guard
    def setup_logging(
        logdir: pyd.DirectoryPath,
        is_dev: bool,
        fire_token: str,
        package: str = '',
        logger: lg.Logger | None = None,
        app: Any | None = None,
        maxsize: int = 2**26,  # 64 MB
        maxcount: int = 2**10,  # 1024 backups
        **fire_kwargs: Any,
    ) -> lg.Logger:
        """Configure comprehensive logging (Python file logging + Logfire).

        Args:
            logdir: Directory for log files.
            is_dev: If True, use development mode with DEBUG level.
            fire_token: Logfire API token (empty string to skip Logfire).
            package: Package name (auto-detected if empty).
            logger: Existing logger to configure, or None to create new.
            app: Optional ASGI app to instrument.
            maxsize: Maximum log file size in bytes (default: 64 MB).
            maxcount: Maximum number of backup files (default: 1024).
            **fire_kwargs: Additional Logfire configuration options.
        Returns:
            Configured Logger instance (cached per package).
        """
        cls = MetricUtils
        if not package:
            package = cls.get_package_name()

        if package in cls.LOGGERS:
            return cls.LOGGERS[package]

        logger = cls.setup_py_logging(
            logdir=logdir,
            is_dev=is_dev,
            package=package,
            logger=logger,
            app=app,
            maxsize=maxsize,
            maxcount=maxcount,
        )

        if fire_token:
            cls.setup_fire_logging(
                fire_token=fire_token,
                package=package,
                is_dev=is_dev,
                logger=logger,
                app=app,
                **fire_kwargs,
            )
        else:
            logger.warning('No Fire token provided -- skipping logfire setup.')

        cls.LOGGERS[package] = logger
        return logger

    @_guard
    def setup_warnings():
        """Configure warning filters to suppress common deprecation warnings.

        Filters out warnings for class-based config, config key changes, and
        pkg_resources deprecation. Only runs once per session.
        """
        if MetricUtils.WARNINGS_SETUP:
            return

        warnings.filterwarnings('ignore', r'.*Support for class-based (?:\S+ +)+is deprecated')
        warnings.filterwarnings('ignore', r'.*Valid config keys have changed')
        warnings.filterwarnings('ignore', r'.*pkg_resources is deprecated as an API')
        MetricUtils.WARNINGS_SETUP = True

    # -----------
    # `4` METRICS
    # -----------
    @classmethod
    @_guard
    def setup_metrics(cls, metrics: pyd.DirectoryPath, logger: lg.Logger):
        """Perform setup for Prometheus metrics, ensuring directory exists and is empty.

        Args:
            metrics: Directory for Prometheus multiprocess metrics.
            logger: Logger for recording setup actions.
        Raises:
            AssertionError: If PROMETHEUS_MULTIPROC_DIR not set or mismatches metrics path.
        """
        if MetricUtils.METRICS_SETUP:
            return

        # I. Ensure Prometheus has what it needs
        raw_prometheus = os.getenv('PROMETHEUS_MULTIPROC_DIR')
        assert raw_prometheus is not None, 'PROMETHEUS_MULTIPROC_DIR not set.'
        prometheus = Path(raw_prometheus).expanduser().resolve()
        assert prometheus == metrics, f'Mismatch; {prometheus.as_posix()} != {metrics.as_posix()}'

        # II. Clear the metrics directory
        if not metrics.exists():
            logger.info(f'Creating metrics directory at {metrics}.')
            metrics.mkdir(exist_ok=True, parents=True)
        elif files := list(metrics.iterdir()):
            logger.info(f'Clearing {len(files)} files from {metrics}.')
            sbp.run(f'rm -rf {metrics}/*')
        MetricUtils.METRICS_SETUP = True

    @classmethod
    @_guard
    def _measure(cls, name: str, counter: Metrics, start: int):
        """Record elapsed time in milliseconds to a counter.

        Args:
            name: Metric name (used for dict/Series counters).
            counter: Counter object (OpenTelemetry, dict, or pandas Series).
            start: Start time from perf_counter_ns().
        """
        if dur_ms := (perf_counter_ns() - start) // 1_000_000:
            if isinstance(counter, OpenTelemetryCounter):
                counter.add(dur_ms)
            else:
                counter[name] = counter.get(name, 0) + dur_ms

    @classmethod
    @_guard
    def _instrument[**Ps, R](cls, func: Callable[Ps, R], counter: Metrics) -> Callable[Ps, R]:
        """Wrap a function to automatically measure and record execution time.

        Args:
            func: Function to instrument (sync or async).
            counter: Counter to record timing metrics.
        Returns:
            Wrapped function that measures execution time.
        """
        if inspect.iscoroutinefunction(func):

            @ft.wraps(func)
            async def async_wrapper(*args: Ps.args, **kwargs: Ps.kwargs) -> R:
                start = perf_counter_ns()
                ret = await func(*args, **kwargs)
                cls._measure(getattr(func, '__name__', 'unknown'), counter, start)

                return ret

            return async_wrapper  # ty: ignore

        @ft.wraps(func)
        def wrapper(*args: Ps.args, **kwargs: Ps.kwargs) -> R:
            start = perf_counter_ns()
            ret = func(*args, **kwargs)
            cls._measure(getattr(func, '__name__', 'unknown'), counter, start)

            return ret

        return wrapper

    @classmethod
    @ctx.contextmanager
    @_guard
    def measure_context(cls, name: str, counter: dict[str, int]):
        """Context manager to measure execution time of a code block.

        Timing is recorded even if the block raises, so a slow-then-crashing path still shows
        up in `counter`.

        Args:
            name: Metric name for recording.
            counter: Dictionary counter to record elapsed time.
        Yields:
            None (timing measured around context block).
        """
        start = perf_counter_ns()
        try:
            yield
        finally:
            cls._measure(name, counter, start)

    @classmethod
    @_guard
    def monitor(cls, *args: Any, **kwargs: Any) -> Callable:
        """Create a Logfire instrumentation decorator for a function.

        Args:
            *args: Positional arguments for fire.instrument().
            **kwargs: Keyword arguments for fire.instrument().
        Returns:
            Decorator that instruments function with Logfire monitoring.
        """
        return fire.instrument(*args, extract_args=False, **kwargs)


metric_utils = MetricUtils
"""An alias of `MetricUtils`, cased so as to imply static usage."""

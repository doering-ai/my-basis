############
### HEAD ###
############
### STANDARD
from collections.abc import Callable
from pathlib import Path
from time import perf_counter_ns
from typing import Any, ClassVar
from types import FunctionType
from urllib.parse import urlsplit
import contextlib as ctx
import functools as ft
import importlib.metadata as impm
import logging as lg
import logging.handlers as lgh
import os
import re
import shutil
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
    TELEMETRY_READY: ClassVar[set[str]] = set()
    SAFE_FIRE_KWARGS: ClassVar[frozenset[str]] = frozenset(
        {'inspect_arguments', 'scrubbing', 'send_to_logfire'}
    )
    TELEMETRY_IDENTITY: ClassVar[re.Pattern[str]] = re.compile(r'[A-Za-z0-9][A-Za-z0-9._/-]{0,127}')
    LOCAL_OTLP_HOSTS: ClassVar[frozenset[str]] = frozenset(
        {'127.0.0.1', '::1', 'host.containers.internal', 'localhost', 'otel-collector'}
    )

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
    def _validate_fire_configuration(
        cls,
        package: str,
        is_dev: bool,
        kwargs: dict[str, Any],
    ) -> tuple[str, str, str]:
        """Validate privacy, identity, and destination before changing global providers."""
        unknown = kwargs.keys() - cls.SAFE_FIRE_KWARGS
        if unknown:
            names = ', '.join(sorted(unknown))
            raise ValueError(f'Unsupported telemetry configuration: {names}.')

        if 'scrubbing' in kwargs:
            scrubbing = kwargs['scrubbing']
            known_fields = {'callback', 'extra_patterns'}
            if (
                not isinstance(scrubbing, fire.ScrubbingOptions)
                or vars(scrubbing).keys() - known_fields
                or scrubbing.callback is not None
            ):
                raise ValueError('Telemetry privacy controls cannot be weakened.')
        if kwargs.get('inspect_arguments', False) is not False:
            raise ValueError('Telemetry privacy controls cannot be weakened.')
        if kwargs.get('send_to_logfire', 'if-token-present') != 'if-token-present':
            raise ValueError('Telemetry destination policy cannot be weakened.')

        try:
            service_name = impm.metadata(package)['Name']
            version = impm.version(package)
        except impm.PackageNotFoundError:
            service_name = package
            version = '0.0.0'
        service_name = os.getenv('OTEL_SERVICE_NAME') or service_name
        environment = os.getenv('OTEL_DEPLOYMENT_ENVIRONMENT') or (
            'development' if is_dev else 'production'
        )
        for field, value in (
            ('OTEL_SERVICE_NAME', service_name),
            ('OTEL_DEPLOYMENT_ENVIRONMENT', environment),
        ):
            if not cls.TELEMETRY_IDENTITY.fullmatch(value):
                raise ValueError(f'{field} is not a bounded telemetry identity.')

        for field in ('OTEL_EXPORTER_OTLP_ENDPOINT', 'OTEL_EXPORTER_OTLP_TRACES_ENDPOINT'):
            if not (raw_endpoint := os.getenv(field)):
                continue
            endpoint = urlsplit(raw_endpoint)
            host = endpoint.hostname or ''
            is_local = host in cls.LOCAL_OTLP_HOSTS
            is_gitlab = bool(re.fullmatch(r'[0-9]+\.gitlab-o11y\.com', host))
            if (
                endpoint.scheme not in {'http', 'https'}
                or not host
                or endpoint.username is not None
                or endpoint.password is not None
                or endpoint.query
                or endpoint.fragment
                or not (is_local or is_gitlab)
                or (is_gitlab and endpoint.scheme != 'https')
            ):
                raise ValueError(f'{field} is not an approved telemetry destination.')

        return service_name, version, environment

    @classmethod
    def _fire_settings(
        cls,
        package: str,
        is_dev: bool,
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        """Build the closed, content-safe Logfire configuration surface."""
        service_name, version, environment = cls._validate_fire_configuration(
            package, is_dev, kwargs
        )
        settings: dict[str, Any] = dict(
            service_name=service_name,
            service_version=version,
            environment=environment,
            console=False,
            send_to_logfire='if-token-present',
            inspect_arguments=False,
            distributed_tracing=False,
        )
        settings |= kwargs
        return settings

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
        export_logs: bool = False,
        system_metrics: bool = False,
        **kwargs: Any,
    ) -> None:
        """Configure Logfire observability and logging.

        Args:
            fire_token: Logfire API token; an empty value falls back to `LOGFIRE_TOKEN`
                and permits an OTLP-only destination.
            package: Package name for service identification.
            logger: Logger to attach Logfire handler to.
            is_dev: If True, use development mode with console output (default: True).
            app: Optional ASGI app to instrument.
            export_logs: Attach the Python logging handler for already-scrubbed event names.
            system_metrics: Enable Logfire's per-process system metrics instrumentation.
            **kwargs: Additional configuration options for Logfire.
        Raises:
            ValueError: If the service identity/destination is missing or a privacy control
                is weakened.
        """
        if not package:
            raise ValueError('Telemetry service package is required.')
        token = fire_token or os.getenv('LOGFIRE_TOKEN', '')
        otlp_destination = any(
            os.getenv(name)
            for name in ('OTEL_EXPORTER_OTLP_ENDPOINT', 'OTEL_EXPORTER_OTLP_TRACES_ENDPOINT')
        )
        if not token and not otlp_destination:
            raise ValueError('No telemetry destination configured.')
        # I. Choose basic configuration settings
        settings = cls._fire_settings(package, is_dev, kwargs)
        if token:
            settings['token'] = token
        if is_dev:
            settings['console'] = fire.ConsoleOptions(
                min_log_level='debug',
                span_style='indented',
                show_project_link=False,
            )
        fire.configure(**settings)

        # II. Register special handlers
        # II.i. Automatically record performance metrics only when explicitly requested
        if system_metrics:
            try:
                fire.instrument_system_metrics()
            except Exception:
                logger.warning('System telemetry instrumentation failed.')
        # fire.log_slow_async_callbacks() # NOTE: not for now?
        # fire.instrument_pydantic() # NOTE: done in pyproject.toml

        # II.ii. Register logfire w/ the default python logger
        if export_logs:
            try:
                logfire_handler = fire.LogfireLoggingHandler()
                logfire_handler.setLevel(lg.DEBUG if is_dev else lg.INFO)
                logger.addHandler(logfire_handler)
            except Exception:
                logger.warning('Python log export setup failed.')

        # II.iii. Register logfire with our ASGI HTTPS app
        if app is not None:
            try:
                # see opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation
                if 'aiohttp' in sys.modules:
                    fire.instrument_aiohttp_client()
                app.asgi_app = fire.instrument_asgi(app.asgi_app)
            except Exception:
                logger.warning('Application telemetry instrumentation failed.')

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
        export_logs: bool = False,
        system_metrics: bool = False,
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
            export_logs: Export already-scrubbed Python log records through Logfire.
            system_metrics: Enable per-process system metrics instrumentation.
            **fire_kwargs: Additional Logfire configuration options.
        Returns:
            Configured Logger instance (cached per package).
        """
        cls = MetricUtils
        if not package:
            package = cls.get_package_name()

        cls._validate_fire_configuration(package, is_dev, fire_kwargs)
        if package in cls.LOGGERS:
            cached = cls.LOGGERS[package]
            if package in cls.TELEMETRY_READY:
                cached.warning('Logging already configured; later setup options were not applied.')
                return cached
            try:
                cls.setup_fire_logging(
                    fire_token=fire_token,
                    package=package,
                    is_dev=is_dev,
                    logger=cached,
                    app=app,
                    export_logs=export_logs,
                    system_metrics=system_metrics,
                    **fire_kwargs,
                )
            except Exception:
                cached.warning('Remote telemetry setup failed; continuing without export.')
            else:
                cls.TELEMETRY_READY.add(package)
            return cached

        logger = cls.setup_py_logging(
            logdir=logdir,
            is_dev=is_dev,
            package=package,
            logger=logger,
            app=app,
            maxsize=maxsize,
            maxcount=maxcount,
        )

        try:
            cls.setup_fire_logging(
                fire_token=fire_token,
                package=package,
                is_dev=is_dev,
                logger=logger,
                app=app,
                export_logs=export_logs,
                system_metrics=system_metrics,
                **fire_kwargs,
            )
        except Exception:
            logger.warning('Remote telemetry setup failed; continuing without export.')
        else:
            cls.TELEMETRY_READY.add(package)

        cls.LOGGERS[package] = logger
        return logger

    @staticmethod
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
            for entry in files:
                if entry.is_dir() and not entry.is_symlink():
                    shutil.rmtree(entry)
                else:
                    entry.unlink()
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

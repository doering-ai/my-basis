############
### HEAD ###
############
### STANDARD
from datetime import datetime, timezone, timedelta
from pathlib import Path
from shutil import get_terminal_size
from time import perf_counter_ns
from typing import Any, Callable, Iterable, ClassVar
import asyncio as aio
import contextlib as ctx
import functools as ft
import importlib.metadata as impm
import itertools as it
import logging as lg
import logging.handlers as lgh
import os
import subprocess as sbp
import sys
import textwrap
import warnings

### EXTERNAL
from opentelemetry.metrics import Counter as OpenTelemetryCounter
import logfire as fire
import pandas as pd
import pydantic as pyd

### INTERNAL
from .TextUtils import text_utils


############
### BODY ###
############
class SystemUtils:
    # ---------------
    # `0` DATE & TIME
    # ---------------
    @classmethod
    def posix(cls, val: int | float | datetime | None = None) -> datetime:
        """
        Convert a timestamp or datetime to UTC datetime.

        Args:
            val: Unix timestamp (int/float), datetime object, or None for current time.

        Returns:
            Timezone-aware datetime in UTC.
        """
        if val is None:
            return datetime.now(timezone.utc)
        elif isinstance(val, datetime):
            return val.astimezone(timezone.utc)
        else:
            return datetime.fromtimestamp(val, timezone.utc)

    @classmethod
    def posix_since(cls, val: int | float | datetime | None = None) -> timedelta:
        """
        Calculate time elapsed since a given timestamp.

        Args:
            val: Unix timestamp (int/float), datetime object, or None.

        Returns:
            Timedelta representing elapsed time, or zero if val is falsy.
        """
        if not val:
            return timedelta(0)
        else:
            return cls.posix() - cls.posix(val)

    # --------------
    # `1` FILESYSTEM
    # --------------
    @classmethod
    def validate_dir(cls, *paths: pyd.DirectoryPath) -> bool:
        """
        Validate that all provided paths are existing directories.

        Args:
            *paths: One or more directory paths to validate.

        Returns:
            True if all paths are valid directories.

        Raises:
            AssertionError: If any path is invalid or not a directory.
        """
        for path in paths:
            assert path and path.exists() and path.is_dir(), f'Invalid directory: {path.as_posix()}'
        return True

    @classmethod
    def validate_file(cls, *paths: pyd.FilePath) -> bool:
        """
        Validate that all provided paths are existing files.

        Args:
            *paths: One or more file paths to validate.

        Returns:
            True if all paths are valid files.

        Raises:
            AssertionError: If any path is invalid or not a file.
        """
        for path in paths:
            assert path and path.exists() and path.is_file(), f'Invalid file: {path.as_posix()}'
        return True

    @classmethod
    def path_sub(cls, path: Path, old: str, new: str) -> Path:
        """
        Substitute a path component with a new value.

        Args:
            path: Path object to modify.
            old: Path component to replace.
            new: Replacement path component.

        Returns:
            New Path with substitution applied, or original if old not found.
        """
        parts = path.parts
        if old in parts:
            i = parts.index(old)
            return Path(*parts[:i], new, *parts[i + 1 :])
        else:
            return path

    # ------------
    # `2` TERMINAL
    # ------------
    WARNINGS_SETUP: ClassVar[bool] = False
    METRICS_SETUP: ClassVar[bool] = False
    AUTO_CONFIRM: ClassVar[bool] = False
    LOGGERS: ClassVar[dict[str, lg.Logger]] = {}

    @classmethod
    def _assemble_args(cls, args: Iterable[Any]) -> Iterable[str]:
        """
        Convert positional arguments to shell-safe strings.

        Args:
            args: Iterable of arguments to convert.

        Yields:
            String representations with appropriate quoting.
        """
        for arg in args:
            if isinstance(arg, int | float):
                yield f'{arg}'
            else:
                arg = str(arg)
                yield f'"{arg}"' if '"' not in arg else f'{arg}'

    @classmethod
    def _assemble_kwargs(
        cls, kwargs: dict[str, Any], _ud: bool = False, _sd: bool = False
    ) -> Iterable[str]:
        """
        Convert keyword arguments to shell command flags.

        Args:
            kwargs: Dictionary of keyword arguments.
            _ud: If True, preserve underscores in keys (default: False).
            _sd: If True, use single dashes for all flags (default: False).

        Yields:
            Formatted command-line flags (e.g., '--key value', '-k').
        """
        for key, val in kwargs.items():
            if '_' in key and not _ud:
                key = key.replace('_', '-')
            key = ('-' if _sd or len(key) == 1 else '--') + key
            if isinstance(val, bool) and val:
                yield key
            elif isinstance(val, int | float):
                yield f'{key} {val}'
            else:
                yield f'{key} "{val}"'

    @classmethod
    def _assemble_command(
        cls,
        cmd: str,
        *args: Any,
        _final: bool = False,
        _verbose: bool = False,
        _single_dash: bool = False,
        _underlines: bool = False,
        _out: str = '',
        _pipe: str = '',
        **kwargs: Any,
    ) -> str:
        """
        Assemble a complete shell command from components.

        Args:
            cmd: Base command name.
            *args: Positional arguments.
            _final: If True, place kwargs after positional args (default: False).
            _verbose: If True, print the command before returning (default: False).
            _single_dash: If True, use single dashes for flags (default: False).
            _underlines: If True, preserve underscores in flag names (default: False).
            _out: If provided, append redirect to this file.
            _pipe: If provided, append pipe to this command.
            **kwargs: Keyword arguments converted to flags.

        Returns:
            Complete shell command string.
        """
        parts = [cmd]
        if args or kwargs:
            # I. Assemble the main parts of the command
            positional = list(cls._assemble_args(args)) if args else []
            keyword = (
                list(cls._assemble_kwargs(kwargs, _underlines, _single_dash)) if kwargs else []
            )

            # II. Order the positional & keyword segments appropriately
            parts.extend(it.chain(keyword, positional) if _final else it.chain(positional, keyword))

        if _out:
            parts.append(f'>> {_out}')
        elif _pipe:
            parts.append(f'| {_pipe}')

        cmd = ' '.join(parts)
        if _verbose:
            print(cmd)
        return cmd

    @classmethod
    def command(cls, cmd: str, *args: Any, **kwargs: Any) -> tuple[int, str, str]:
        """
        Execute a shell command synchronously.

        Args:
            cmd: Base command to execute.
            *args: Positional arguments.
            **kwargs: Keyword arguments (converted to flags).

        Returns:
            Tuple of (return_code, stdout, stderr).
        """
        cmd = cls._assemble_command(cmd, *args, **kwargs)
        ret = sbp.run(cmd, capture_output=True, text=True, shell=True)
        return (
            ret.returncode or 0,
            (ret.stdout or '').strip(),
            (ret.stderr or '').strip(),
        )

    @classmethod
    async def run_command(cls, cmd: str, *args: Any, **kwargs: Any) -> tuple[int, str, str]:
        """
        Execute a shell command asynchronously.

        Args:
            cmd: Base command to execute.
            *args: Positional arguments.
            **kwargs: Keyword arguments (converted to flags).

        Returns:
            Tuple of (return_code, stdout, stderr).
        """
        cmd = cls._assemble_command(cmd, *args, **kwargs)
        subprocess = await aio.create_subprocess_shell(
            cmd,
            stdout=aio.subprocess.PIPE,
            stderr=aio.subprocess.PIPE,
            shell=True,
        )
        stdout, stderr = await subprocess.communicate()

        return (
            subprocess.returncode or 0,
            (stdout or b'').decode().strip(),
            (stderr or b'').decode().strip(),
        )

    @classmethod
    def get_terminal_width(cls) -> int:
        """
        Get the current terminal width in characters.

        Returns:
            Terminal width (defaults to 100 if unavailable).
        """
        return get_terminal_size((100, 100))[0]

    @classmethod
    def terminal_linewrap(cls, text: str, indent: int = 0) -> str:
        """
        Wrap text to fit within terminal width.

        Args:
            text: Text to wrap.
            indent: Number of characters to reserve for indentation (default: 0).

        Returns:
            Text wrapped to terminal width minus indent.
        """
        return textwrap.fill(
            text_utils.unwrap_paragraphs(text), width=cls.get_terminal_width() - indent
        )

    @staticmethod
    def auto_confirm() -> None:
        """Enable auto-confirmation mode for all confirmation prompts."""
        SystemUtils.AUTO_CONFIRM = True

    @staticmethod
    def confirm(prompt: str, default_no: bool = False) -> bool:
        """
        Prompt user for confirmation with y/n input.

        Args:
            prompt: Question to display to user.
            default_no: If True, default to 'no' (default: False defaults to 'yes').

        Returns:
            True if user confirms, False otherwise. Always True if auto-confirm enabled.
        """
        if SystemUtils.AUTO_CONFIRM:
            return True
        elif default_no:
            return not input(f'{prompt} [y/N] ').lower().strip().startswith('y')
        else:
            return not input(f'{prompt} [Y/n] ').lower().strip().startswith('n')

    # -----------
    # `3` LOGGING
    # -----------
    @classmethod
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
        """
        Configure Python file-based logging with rotation.

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
        cls.validate_dir(logdir)
        if logger is None:
            try:
                name = impm.metadata(package)['Name']
            except impm.PackageNotFoundError:
                name = package
            logger = lg.getLogger(name)

        # II. Name and setup a new file in this dir
        file = logdir / f'{logger.name}_{cls.posix().strftime("%y%m%d-%H%M%S")}.log'
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
    def setup_fire_logging(
        cls,
        fire_token: str,
        package: str,
        logger: lg.Logger,
        is_dev: bool = True,
        app: Any | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Configure Logfire observability and logging.

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
            fire.instrument_aiohttp_client()
            app.asgi_app = fire.instrument_asgi(app.asgi_app)  # type:ignore

    @classmethod
    def get_package_name(cls) -> str:
        """
        Retrieve the current package name from metadata.

        Returns:
            Package name as string, derived from module metadata.
        """
        current_module = sys.modules[__name__]
        package_name = current_module.__package__ or __name__
        root_package = package_name.split('.', 1)[0]
        ret = impm.packages_distributions().get(root_package, root_package)
        if isinstance(ret, list):
            ret = ret[0]
        return ret

    @classmethod
    def setup_logging(
        cls,
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
        """
        Configure comprehensive logging (Python file logging + Logfire).

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

    @staticmethod
    def setup_warnings():
        """
        Configure warning filters to suppress common deprecation warnings.

        Filters out warnings for class-based config, config key changes, and
        pkg_resources deprecation. Only runs once per session.
        """
        if SystemUtils.WARNINGS_SETUP:
            return

        warnings.filterwarnings('ignore', r'.*Support for class-based (?:\S+ +)+is deprecated')
        warnings.filterwarnings('ignore', r'.*Valid config keys have changed')
        warnings.filterwarnings('ignore', r'.*pkg_resources is deprecated as an API')
        SystemUtils.WARNINGS_SETUP = True

    # -----------
    # `4` METRICS
    # -----------
    @classmethod
    def setup_metrics(cls, metrics: pyd.DirectoryPath, logger: lg.Logger):
        """
        Perform setup for Prometheus metrics, ensuring directory exists and is empty.

        Args:
            metrics: Directory for Prometheus multiprocess metrics.
            logger: Logger for recording setup actions.

        Raises:
            AssertionError: If PROMETHEUS_MULTIPROC_DIR not set or mismatches metrics path.
        """
        if SystemUtils.METRICS_SETUP:
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
        SystemUtils.METRICS_SETUP = True

    @classmethod
    def _measure(
        cls, name: str, counter: OpenTelemetryCounter | dict[str, int] | pd.Series, start: int
    ):
        """
        Record elapsed time in milliseconds to a counter.

        Args:
            name: Metric name (used for dict/Series counters).
            counter: Counter object (OpenTelemetry, dict, or pandas Series).
            start: Start time from perf_counter_ns().
        """
        if dur_ms := (perf_counter_ns() - start) // 1_000_000:
            if isinstance(counter, OpenTelemetryCounter):
                counter.add(dur_ms)
            else:
                counter[name] += dur_ms

    @classmethod
    def _instrument(
        cls, func: Callable, counter: OpenTelemetryCounter | dict[str, int] | pd.Series
    ) -> Callable:
        """
        Wrap a function to automatically measure and record execution time.

        Args:
            func: Function to instrument (sync or async).
            counter: Counter to record timing metrics.

        Returns:
            Wrapped function that measures execution time.
        """
        @ft.wraps(func)
        def wrapper(*args: Any, **kwargs: Any):
            start = int(perf_counter_ns())
            ret = func(*args, **kwargs)
            cls._measure(getattr(func, '__name__', 'unknown'), counter, start)

            return ret

        @ft.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any):
            start = int(perf_counter_ns())
            ret = await func(*args, **kwargs)
            cls._measure(getattr(func, '__name__', 'unknown'), counter, start)

            return ret

        return async_wrapper if aio.iscoroutinefunction(func) else wrapper

    @ctx.contextmanager
    @classmethod
    def measure_context(cls, name: str, counter: dict[str, int]):
        """
        Context manager to measure execution time of a code block.

        Args:
            name: Metric name for recording.
            counter: Dictionary counter to record elapsed time.

        Yields:
            None (timing measured around context block).
        """
        start = perf_counter_ns()
        yield
        cls._measure(name, counter, start)

    @classmethod
    def monitor(cls, *args: Any, **kwargs: Any) -> Callable:
        """
        Create a Logfire instrumentation decorator for a function.

        Args:
            *args: Positional arguments for fire.instrument().
            **kwargs: Keyword arguments for fire.instrument().

        Returns:
            Decorator that instruments function with Logfire monitoring.
        """
        return fire.instrument(*args, extract_args=False, **kwargs)

    @classmethod
    def print_in_color(cls, text: str) -> None:
        """
        Print colored text using zsh prompt expansion.

        Args:
            text: Text with zsh color codes to print.

        Note:
            Requires zsh to be available in the system PATH.
        """
        ret = sbp.run(f'zsh -c \'print -P "{text}"\'', capture_output=True, text=True, shell=True)
        print((ret.stdout or '').strip('\n'))


system_utils = SystemUtils

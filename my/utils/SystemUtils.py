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
        if val is None:
            return datetime.now(timezone.utc)
        elif isinstance(val, datetime):
            return val.astimezone(timezone.utc)
        else:
            return datetime.fromtimestamp(val, timezone.utc)

    @classmethod
    def posix_since(cls, val: int | float | datetime | None = None) -> timedelta:
        if not val:
            return timedelta(0)
        else:
            return cls.posix() - cls.posix(val)

    # --------------
    # `1` FILESYSTEM
    # --------------
    @classmethod
    def validate_dir(cls, *paths: pyd.DirectoryPath) -> bool:
        for path in paths:
            assert path and path.exists() and path.is_dir(), f'Invalid directory: {path.as_posix()}'
        return True

    @classmethod
    def validate_file(cls, *paths: pyd.FilePath) -> bool:
        for path in paths:
            assert path and path.exists() and path.is_file(), f'Invalid file: {path.as_posix()}'
        return True

    @classmethod
    def path_sub(cls, path: Path, old: str, new: str) -> Path:
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
        cmd = cls._assemble_command(cmd, *args, **kwargs)
        ret = sbp.run(cmd, capture_output=True, text=True, shell=True)
        return (
            ret.returncode or 0,
            (ret.stdout or '').strip(),
            (ret.stderr or '').strip(),
        )

    @classmethod
    async def run_command(cls, cmd: str, *args: Any, **kwargs: Any) -> tuple[int, str, str]:
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
        return get_terminal_size((100, 100))[0]

    @classmethod
    def terminal_linewrap(cls, text: str, indent: int = 0) -> str:
        return textwrap.fill(
            text_utils.unwrap_paragraphs(text), width=cls.get_terminal_width() - indent
        )

    @staticmethod
    def auto_confirm() -> None:
        SystemUtils.AUTO_CONFIRM = True

    @staticmethod
    def confirm(prompt: str, default_no: bool = False) -> bool:
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
    def get_package_name(
        cls,
    ):
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
        Perform the necessary setup for Prometheus metrics, including ensuring the metrics
        directory is present and empty.
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
        if dur_ms := (perf_counter_ns() - start) // 1_000_000:
            if isinstance(counter, OpenTelemetryCounter):
                counter.add(dur_ms)
            else:
                counter[name] += dur_ms

    @classmethod
    def _instrument(
        cls, func: Callable, counter: OpenTelemetryCounter | dict[str, int] | pd.Series
    ) -> Callable:
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
        start = perf_counter_ns()
        yield
        cls._measure(name, counter, start)

    @classmethod
    def monitor(cls, *args: Any, **kwargs: Any) -> Callable:
        return fire.instrument(*args, extract_args=False, **kwargs)

    @classmethod
    def print_in_color(cls, text: str) -> None:
        """Use zsh to process the prompt expansion."""
        ret = sbp.run(f'zsh -c \'print -P "{text}"\'', capture_output=True, text=True, shell=True)
        print((ret.stdout or '').strip('\n'))


system_utils = SystemUtils

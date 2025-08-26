############
### HEAD ###
############
### STANDARD
import asyncio as aio
from typing import (
    Any,
    Annotated,
    Callable,
    Collection,
    Container,
    Iterable,
    Iterator,
    Literal,
    Mapping,
    Sequence,
    TypeVar,
)
from types import ModuleType
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
from shutil import get_terminal_size
from time import perf_counter_ns
import contextlib as ctx
import functools as ft
import importlib as imp
import importlib.metadata as impm
import itertools as it
import logging as lg
import logging.handlers
import os
import subprocess as sbp
import sys
import textwrap
import warnings

### EXTERNAL
## General
import pydantic as pyd
from pydantic_core import core_schema as pyd_schema
import pandas as pd
import more_itertools as mi

## Metrics
import logfire as fire
from opentelemetry.metrics import Counter as OpenTelemetryCounter

## Serialization
from unidecode import unidecode
import regex as re
from regex import Pattern, Match

### INTERNAL

############
### DATA ###
############
# Initialize generic type variable
T = TypeVar('T')
C = TypeVar('C')

# Specific type helpers
Key = TypeVar('Key')
Value = TypeVar('Value')

# Type Aliases
Series = list | tuple | set | deque
Atomic = str | int | float | bool


############
### BODY ###
############
# -------------------
# 1. System Utilities
# -------------------
def posix(timestamp: int | float | None = None) -> datetime:
    if timestamp is None:
        return datetime.now(timezone.utc)
    else:
        return datetime.fromtimestamp(timestamp, timezone.utc)


def _instrument(
    func: Callable, counter: OpenTelemetryCounter | dict[str, int] | pd.Series
) -> Callable:
    @ft.wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        start = int(perf_counter_ns())
        ret = func(*args, **kwargs)
        _measure(func.__name__, counter, start)

        return ret

    @ft.wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any):
        start = int(perf_counter_ns())
        ret = await func(*args, **kwargs)
        _measure(func.__name__, counter, start)

        return ret

    return async_wrapper if aio.iscoroutinefunction(func) else wrapper


@ctx.contextmanager
def measure_context(name: str, counter: dict[str, int]):
    start = perf_counter_ns()
    yield
    _measure(name, counter, start)


def monitor(*args: Any, **kwargs: Any) -> Callable:
    return fire.instrument(*args, extract_args=False, **kwargs)


def _assemble_args(args: Iterable[Any]) -> Iterable[str]:
    for arg in args:
        if isinstance(arg, int | float):
            yield f'{arg}'
        else:
            arg = str(arg)
            yield f'"{arg}"' if '"' not in arg else f'{arg}'


def _assemble_kwargs(kwargs: dict[str, Any], _ud: bool = False, _sd: bool = False) -> Iterable[str]:
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


def _assemble_command(
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
        positional = list(_assemble_args(args)) if args else []
        keyword = list(_assemble_kwargs(kwargs, _underlines, _single_dash)) if kwargs else []

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


def command(cmd: str, *args: Any, **kwargs: Any) -> int:
    cmd = _assemble_command(cmd, *args, **kwargs)
    return os.system(cmd)


async def run_command(cmd: str, *args: Any, **kwargs: Any) -> tuple[int, str, str]:
    cmd = _assemble_command(cmd, *args, **kwargs)
    subprocess = await aio.create_subprocess_shell(
        cmd, stdout=aio.subprocess.PIPE, stderr=aio.subprocess.PIPE
    )
    stdout, stderr = await subprocess.communicate()

    return (
        subprocess.returncode or 0,
        (stdout or b'').decode().strip(),
        (stderr or b'').decode().strip(),
    )


def wrap(line: str, prefix: str = '', char: str = '-', width: int = 2) -> str:
    n = (len(line) + 2 + 2 * width) if width else len(line)
    wrapper = prefix + (char * n)
    return '\n'.join([
        '',
        wrapper,
        prefix + (f'{char*width} {line} {char*width}' if width else line),
        wrapper,
    ])


def validate_dir(*paths: pyd.DirectoryPath) -> bool:
    for path in paths:
        assert path and path.exists() and path.is_dir(), f"Invalid directory: {path.as_posix()}"
    return True


def validate_file(*paths: pyd.FilePath) -> bool:
    for path in paths:
        assert path and path.exists() and path.is_file(), f"Invalid file: {path.as_posix()}"
    return True


def validate_arch_dir(*paths: pyd.DirectoryPath) -> bool:
    # I. Ensure they're all directories
    validate_dir(*paths)

    # II. Ensure they're all descended from the architectonic root
    rootstr = str(ROOT)
    pathstrs = [str(p.expanduser().resolve()) for p in paths]
    invalid = [ps for ps in pathstrs if not ps.startswith(rootstr)]
    assert not invalid, f'Invalid directory paths: {invalid}'

    return True


def validate_arch_file(*paths: pyd.FilePath) -> bool:
    # I. Ensure they're all directories
    validate_file(*paths)

    # II. Ensure they're all descended from the architectonic root
    rootstr = str(ROOT)
    pathstrs = [str(p.expanduser().resolve()) for p in paths]
    invalid = [ps for ps in pathstrs if not ps.startswith(rootstr)]
    assert not invalid, f'Invalid directory paths: {invalid}'

    return True


async def find_file(pattern: str, root: pyd.DirectoryPath) -> Path | None:
    """
    Find a file matching the given pattern in the specified root directory.
    Returns the first matching file or None if no match is found.
    """
    assert pattern, "Pattern must not be empty."
    assert root.exists() and root.is_dir(), f"Invalid directory: {root.as_posix()}"
    code, stdout, stderr = await run_command(
        fr'find "{root}" -regex ".*\b{pattern}\b"',
        _pipe=r'grep -v "node_modules|\.git|\.venv|build|prof"',
    )
    if code == 0 and stdout:
        file = root / stdout.strip().splitlines()[0]
        assert file.exists() and file.is_file()
        return file
    else:
        return None


async def find_files(*names: str, root: pyd.DirectoryPath) -> list[Path]:
    ret: list[Path] = []
    for name in names:
        if not name:
            pass
        elif name[0] in '~/':
            ret.append(Path(name).expanduser().resolve())
        elif name.startswith('./'):
            ret.append(root / name[2:])
        else:
            file = await find_file(name, root)
            assert file is not None, f"File {name} not found in {root.as_posix()}"
            ret.append(file)

    assert all(file.exists() for file in ret)
    return ret


def indent(text: str, n: int = 4) -> str:
    if not n:
        return text
    return textwrap.indent(text, ' ' * n)


def unindent(text: str, n: int = 4) -> str:
    """ Unindent each line in the given string or iterable of strings by n tabs. """
    fn = ft.partial(re.compile(rf'^ {{1,{n * 4}}}').sub, '')
    return '\n'.join(map(fn, text))


STARTS_RGX = re.compile(r'(?m)^ ?[*](?: |$)')

PROSE_LINE = re.compile(r' *[[:punct:]]*([[:alpha:]]|\d+[^\d.])')


def unwrap_paragraphs(text: str) -> str:
    text = textwrap.dedent(text.strip('\n'))
    text = STARTS_RGX.sub('', text)
    lines = text.splitlines()
    prose_mask = [bool(PROSE_LINE.match(line)) for line in lines]

    acc = lines[0].strip()
    for (prev, prev_is_prose), (cur, cur_is_prose) in it.pairwise(zip(lines, prose_mask)):
        if not (_stripped := cur.strip()):
            acc += '\n'
        elif prev_is_prose and cur_is_prose:
            if prev.endswith('-') and _stripped[0].isalpha():
                acc += _stripped
            else:
                acc += f' {_stripped}'
        elif cur_is_prose:
            acc += f'\n{_stripped}'
        else:
            acc += f'\n{cur}'

    return acc


def wrap_paragraphs(text: str, width: int = 100) -> str:
    return textwrap.fill(text, width=width)


def get_terminal_width() -> int:
    return get_terminal_size((100, 100))[0]


def terminal_linewrap(text: str, indent: int = 0) -> str:
    return textwrap.fill(unwrap_paragraphs(text), width=get_terminal_width() - indent)


def _name_logfile(logger_name: str) -> str:
    return f"{logger_name}_{posix().strftime('%y%m%d-%H%M%S')}.log"


def get_package_name():
    current_module = sys.modules[__name__]
    package_name = current_module.__package__ or __name__
    root_package = package_name.split('.', 1)[0]
    return impm.packages_distributions().get(root_package, root_package)


# def get_package_name():
#     # Look for pyproject.toml starting from current directory
#     file = None
#     for parent in Path.cwd().parents:
#         if (file := parent / "pyproject.toml").exists():
#             break

#     if file is not None:
#         try:
#             import tomllib  # Python 3.11+
#             with open(file, "rb") as f:
#                 pyproject_data = tomllib.load(f)
#             return pyproject_data["tool"]["poetry"]["name"]
#         except ImportError:
#             if match := re.search(r'(?m)^name *= *["\'](.+?)["\'] *$', file.read_text()):
#                 return match[1]
#             else:
#                 raise ValueError(f'Could not parse {file}')
#     else:
#         raise FileNotFoundError("Could not find pyproject.toml")


def setup_py_logging(
    logdir: pyd.DirectoryPath,
    is_dev: bool,
    package: str,
    logger: lg.Logger | None = None,
    app: Any | None = None,
    maxsize: int = 2**26,  # 64 MB
    maxcount: int = 2**10,  # 1024 backups
) -> lg.Logger:
    # I. Validate log directory and logging object
    validate_dir(logdir)
    if logger is None:
        try:
            name = impm.metadata(package)['Name']
        except impm.PackageNotFoundError:
            name = package
        logger = lg.getLogger(name)

    # I. Name and setup a new file in this dir
    file = logdir / _name_logfile(logger.name)
    assert not file.exists(), f"Log file {file} already exists."

    file_handler = lg.handlers.RotatingFileHandler(file, maxBytes=maxsize, backupCount=maxcount)
    file_handler.setLevel(lg.DEBUG if is_dev else lg.INFO)
    file_handler.setFormatter(lg.Formatter('[%(asctime)s %(levelname)s] %(message)s'))

    # IV. Register handler(s) with logger, defaulting to the universal one
    logger.addHandler(file_handler)

    # V. Register logger with our ASGI HTTPS app, if present
    if app is not None:
        for handler in logger.handlers:
            app.logger.addHandler(handler)
        app.logger.setLevel(logger.level)
        app.config["DEBUG"] = is_dev

    return logger


def setup_fire_logging(
    fire_token: str,
    package: str,
    logger: lg.Logger,
    is_dev: bool = True,
    app: Any | None = None,
    **kwargs: Any,
) -> None:
    assert fire_token and package, "Tried to initialize fire logging w/o token or package."

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
        environment="development" if is_dev else "production",
        send_to_logfire=not is_dev,
        scrubbing=False,
        inspect_arguments=True,
    )
    if is_dev:
        settings['console'] = fire.ConsoleOptions(
            min_log_level="debug",
            span_style="indented",
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


WARNINGS_SETUP = False
METRICS_SETUP = False
LOGGERS: dict[str, lg.Logger] = {}


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
    if not package:
        package = get_package_name()

    global LOGGERS
    if package in LOGGERS:
        return LOGGERS[package]

    logger = setup_py_logging(
        logdir=logdir,
        is_dev=is_dev,
        package=package,
        logger=logger,
        app=app,
        maxsize=maxsize,
        maxcount=maxcount,
    )

    if fire_token:
        setup_fire_logging(
            fire_token=fire_token,
            package=package,
            is_dev=is_dev,
            logger=logger,
            app=app,
            **fire_kwargs,
        )
    else:
        logger.warning("No Fire token provided -- skipping logfire setup.")

    LOGGERS[package] = logger
    return logger


def setup_metrics(metrics: pyd.DirectoryPath, logger: lg.Logger):
    """
    Perform the necessary setup for Prometheus metrics, including ensuring the metrics
    directory is present and empty.
    """
    global METRICS_SETUP
    if METRICS_SETUP:
        return

    # I. Ensure Prometheus has what it needs
    raw_prometheus = os.getenv('PROMETHEUS_MULTIPROC_DIR')
    assert raw_prometheus is not None, 'PROMETHEUS_MULTIPROC_DIR not set.'
    prometheus = Path(raw_prometheus).expanduser().resolve()
    assert prometheus == metrics, f'Mismatch; {prometheus.as_posix()} != {metrics.as_posix()}'

    # II. Clear the metrics directory
    if not metrics.exists():
        logger.info(f"Creating metrics directory at {metrics}.")
        metrics.mkdir(exist_ok=True, parents=True)
    elif files := list(metrics.iterdir()):
        logger.info(f"Clearing {len(files)} files from {metrics}.")
        sbp.run(f"rm -rf {metrics}/*")
    METRICS_SETUP = True


def setup_warnings():
    global WARNINGS_SETUP
    if WARNINGS_SETUP:
        return

    warnings.filterwarnings("ignore", r'.*Support for class-based (?:\S+ +)+is deprecated')
    warnings.filterwarnings("ignore", r'.*Valid config keys have changed')
    warnings.filterwarnings("ignore", r'.*pkg_resources is deprecated as an API')
    WARNINGS_SETUP = True


# ----------------------
# 2. Functional Wrappers
# ----------------------
def build(val: Value, *functions: Callable[[Value], Value]) -> Value:
    return ft.reduce(lambda acc, fn: fn(acc), functions, val)


def find(container: Iterable[Value], predicate: Callable[[Value], bool] | Value = bool) -> int:
    predicate = predicate if callable(predicate) else predicate.__eq__
    return next(mi.locate(container, predicate), -1)


def find_key(
    items: Mapping[Key, Value] | Iterable[tuple[Key, Value]],
    predicate: Callable[[Value], bool] | Value = bool,
    default: Key | None = None
) -> Key | None:
    """
    Find the first key in the mapping for which the predicate returns True.
    If no such key exists, return None.
    """
    predicate = predicate if callable(predicate) else predicate.__eq__
    return next(
        (key for key, value in map_items(items) if predicate(value)),  # type:ignore
        default
    )


def _measure(name: str, counter: OpenTelemetryCounter | dict[str, int] | pd.Series, start: int):
    if dur_ms := (perf_counter_ns() - start) // 1_000_000:
        if isinstance(counter, OpenTelemetryCounter):
            counter.add(dur_ms)
        else:
            counter[name] += dur_ms


def val_map(
    func: Callable[[Value], T],
    data: Mapping[Key, Value] | Iterable[tuple[Key, Value]] | Iterable[Key],
    drop: bool = False,
) -> dict[Key, T]:
    """ Map a function over the values of a mapping or iterable, returning a new dictionary. """
    if not data:
        return {}
    elif items := map_items(data):  # type:ignore
        ret = {key: func(val) for key, val in items}  # type:ignore
    else:
        ret = {val: func(val) for val in data}  # type:ignore

    if drop:
        ret = dict(filter(all, ret.items()))
    return ret  # type:ignore


def attr_map(obj: object, fields: Iterable[str], drop: bool = False) -> dict[str, Any]:
    fn = ft.partial(getattr, obj, **(dict(default='') if drop else dict()))
    return val_map(fn, {f: f for f in fields}, drop)


def chain_map(funcs: Iterable[Callable[[T], C]], item: T) -> Iterator[C]:
    for func in funcs:
        if ret := func(item):
            yield ret


def condense(items: Iterable[T], pred: Callable[[T], bool] = bool) -> list[T]:
    return list(filter(pred, items))


def multi_partition(items: Iterable[T], **preds: Callable[[T], object]) -> dict[str, list[T]]:
    assert 'rest' not in preds.keys(), 'Cannot use key "rest" in multi_partition()'

    ret: dict[str, list[T]] = {key: [] for key in preds.keys()}
    ret['rest'] = list(items)
    for key, pred in preds.items():
        ret['rest'], ret[key] = map(list, mi.partition(pred, ret['rest']))
        if not ret['rest']:
            break
    return ret


def map_condense(
    items: Mapping[Key, Value] | Iterable[tuple[Key, Value]],
    pred: Callable[[Value], bool] = bool
) -> Iterator[tuple[Key, Value]]:
    """ Filter a mapping by a predicate function. """
    yield from filter(lambda tup: pred(tup[1]), map_items(items))


def get_all(dictionary: dict[str, T], *args: str, mandatory: bool = False) -> dict[str, T]:
    ret = {key: dictionary[key] for key in args if key in dictionary}
    if mandatory and len(ret) < len(args):
        return {}
    else:
        return ret


def get_any(
    dictionary: dict[str, T],
    *args: str,
    default: T | None = None,
    unique: bool = False
) -> T | None:
    ret: dict[str, T] = {
        key: dictionary[key]
        for key in args
        if dictionary.get(key, default) != default
    }
    if len(ret) == 0:
        return default
    if len(ret) > 1 and unique:
        raise ValueError(f"Multiple keys found in dictionary: {ret.keys()}")
    else:
        return list(ret.values())[0]


# async def wait_for_first(
#     tasks: Iterable[Coroutine[None, None, T | None]],
#     **kwargs: Any,
# ) -> T | None:
#     done, pending = await aio.wait(tasks, return_when=aio.FIRST_COMPLETED, **kwargs)
#     for task in pending:
#         task.cancel()
#     return done.pop().result() if done else None

# async def wait_for_all(
#     tasks: Iterable[Coroutine[None, None, T | None]],
#     **kwargs: Any,
# ) -> list[T | None]:
#     done, pending = await aio.wait(tasks, return_when=aio.ALL_COMPLETED, **kwargs)
#     for task in pending:
#         task.cancel()
#     return [task.result() for task in done] if done else []


def repeat_until_complete(func: Callable[[C, T], tuple[int, T]]) -> Callable:
    @ft.wraps(func)
    def wrapper(cls: C, value: T, **kwargs: Any) -> tuple[int, T]:
        run_results: list[int] = []
        while not run_results or run_results[-1] > 0:
            num_changes, value = func(cls, value, **kwargs)
            run_results.append(num_changes)

        return sum(run_results), value

    return wrapper


def replace(string: str, *args: tuple[str | Pattern, str | Callable[[Match[str]], str]]) -> str:
    for pattern, repl in args:
        string = re.sub(pattern, repl, string)
    return string


def split_into(text: str, pattern: str | Pattern, n: int = 2, rhs: bool = True) -> list[str]:
    """
    Splits a string using regex a given number of times AT MINIMUM, padding on the left or right
    for any missing values.

    Args:
        text: The string to split.
        pattern: The regex pattern to split by.
        n: The EXACT number of parts to split into.
        rhs: If True, pad on the right; if False, pad on the left.
    """
    if not text:
        return [''] * n

    assert n > 1, f'Passed invalid array length `{n}` to split_into(); must be > 1.'
    parts = re.split(pattern, text, n - 1)
    if delta := n - len(parts):
        if rhs:
            parts.extend([''] * delta)
        else:
            parts = ([''] * delta) + parts
    assert len(parts) == n, f'Failed to correctly split {text} by {pattern} into {n}, got {parts}'
    return parts


# ---------------
# Presence Checks
# ---------------
def has_all(container: Container[Value], *args: Value) -> bool:
    return _has(container, *args, mode='all')


def has_any(container: Container[Value], *args: Value) -> bool:
    return _has(container, *args, mode='any')


def _has(container: Container, *args: Any, mode: Literal['any', 'all'] = 'any') -> bool:
    fn = any if mode == 'any' else all
    return fn(arg in container for arg in args) if container else False


def has_only(container: Collection[Value], *args: Value) -> bool:
    if isinstance(container, str):
        return len(container) == sum(map(len, args)) and has_all(container, *args)  # type:ignore
    return set(container) == set(args)


def has_none(container: Container[Value], *args: Value) -> bool:
    return not has_any(container, *args)


def all_has_all(containers: Iterable[Container[Value]], *args: Value) -> bool:
    return all(has_all(cont, *args) for cont in containers) if containers else False


def any_has_all(containers: Iterable[Container[Value]], *args: Value) -> bool:
    return any(has_all(cont, *args) for cont in containers) if containers else False


def all_has_any(containers: Iterable[Container[Value]], *args: Value) -> bool:
    return all(has_any(cont, *args) for cont in containers) if containers else False


def any_has_any(containers: Iterable[Container[Value]], *args: Value) -> bool:
    return any(has_any(cont, *args) for cont in containers) if containers else False


def drop_at(data: Sequence[T], mask: Iterable[int]) -> list[T]:
    return [item for i, item in enumerate(data) if i not in mask]


def shared_prefix(*strings: str) -> str:
    return ''.join(mi.longest_common_prefix(strings))


def shared_suffix(*strings: str) -> str:
    return ''.join(reversed(list(mi.longest_common_prefix(map(reversed, strings)))))


def common_elements(lhs: Sequence[T] | set[T], rhs: Sequence[T] | set[T]) -> list[T]:
    if isinstance(lhs, set) or isinstance(rhs, set):
        return list(set(lhs) & set(rhs))
    else:
        c0, c1 = Counter(lhs), Counter(rhs)
        shared = (set(c0.keys()) & set(c1.keys()))
        return [val for val in shared for _ in range(min(c0[val], c1[val]))]


def next_in(container: Container[Value], items: Iterable[Value]) -> Value | None:
    return next(filter(container.__contains__, items), None)


# --------------------------
# 3. Serialization Functions
# --------------------------
def regex_dict(
    dictionary: dict[T, str | tuple[str, ...] | Pattern] | dict[T, str] = {},
    compile_function: Callable[..., Pattern] = re.compile,
) -> dict[T, Pattern]:
    ret = {}
    for key, val in dictionary.items():
        if isinstance(val, Pattern):
            ret[key] = val
        else:
            ret[key] = compile_function(val)
    return ret


def regex_array(
    array: Iterable[tuple[str | Pattern, str]],
    compile_function: Callable[..., Pattern] = re.compile,
) -> list[tuple[Pattern, str]]:
    ret = []
    for key, val in array:
        if isinstance(key, Pattern):
            ret.append((key, val))
        else:
            ret.append((compile_function(key), val))
    return ret


def spaced_rgx(pattern: str) -> str:
    return r'\s*'.join(' '.split(pattern))


def multi_rgx(*rgxs: str | list[str], sep: str = r' ?', branching: bool = False) -> str:
    parts = [(rgx if isinstance(rgx, str) else sep.join(rgx)) for rgx in rgxs]
    contents = r"|".join(parts)
    return rf'(?{"|"if branching else ":"}{contents})'


def strip_quotes(string: str) -> str:
    string = string.strip()
    while len(string) > 2 and (c := string[0]) in '_*\'"':
        if c == string[-2] and not string[-1].isalnum():
            string = string[:-1]

        if c == string[-1]:
            string = string.strip(c).strip()
        else:
            break

    return string


CLEANING_RGXS = regex_dict(
    dict(
        newlines=r'\n+',
        punctuation=r'[\'".]+|(?<=\d),+(?=\d)',
        nonwords=r' *[^-\w\s]+ *',  # All non-whitespace breaks are underlines
        spaces=r' +',  # Spaces are just hyphens
        multihyphens=r'-{2,}',
    )
)


def _clean_nonwords(string: str) -> str:
    return replace(
        string,
        (CLEANING_RGXS['newlines'], ' '),
        (CLEANING_RGXS['punctuation'], ''),
        (CLEANING_RGXS['nonwords'], '_'),
        (CLEANING_RGXS['spaces'], '-'),
        (CLEANING_RGXS['multihyphens'], '-'),
    ).strip('_-')


def clean_string(string: str, case: Literal['lower', 'none', 'upper'] = 'lower') -> str:
    ret = build(string, unidecode, str.strip, _clean_nonwords)
    if case == 'lower':
        return ret.lower()
    elif case == 'upper':
        return ret.upper()
    else:
        return ret


WORD_RGX = re.compile(r'\w+')


def to_words(text: str) -> list[str]:
    return list(WORD_RGX.findall(text))


def line_num(article: str, pos: int | str) -> int:
    if isinstance(pos, int):
        return article.count('\n', 0, pos) + 1
    else:
        return article.count('\n', 0, article.index(pos)) + 1


# ------------------
# 4. Code Reflection
# ------------------
@ft.lru_cache(maxsize=1024)
def instance_fields(cls: type[pyd.BaseModel]) -> dict[str, type]:
    return {
        field: info.annotation
        for field, info in cls.model_fields.items()
        if field.islower() and info.annotation is not None
    }


@ft.lru_cache(maxsize=1024)
def instance_aliases(cls: type[pyd.BaseModel]) -> dict[str, type]:
    ret = {}
    for field, info in cls.model_fields.items():
        if field.islower() and info.annotation is not None:
            if alias := info.alias:
                field = alias
            elif v_alias := info.validation_alias:
                if isinstance(v_alias, pyd.AliasChoices):
                    v_alias = v_alias.choices[0]

                if isinstance(v_alias, pyd.AliasPath):
                    field = str(v_alias.convert_to_aliases()[0])
                else:
                    field = v_alias
            ret[field] = info.annotation
    return ret


def nested_replace(obj: Collection | pyd.BaseModel, old: Any, new: Any, depth: int = 0) -> bool:
    next_iter: Collection[Collection | pyd.BaseModel] | None = None
    if isinstance(obj, Series):
        if old in obj:
            if isinstance(obj, Sequence):
                index = obj.index(old)
                if isinstance(obj, list | deque):
                    obj[index] = new
                elif isinstance(obj, tuple):
                    obj = tuple(obj[:index] + (new, ) + obj[index + 1:])
            else:
                obj.remove(old)
                obj.add(new)
            return True
        else:
            next_iter = obj

    elif isinstance(obj, Mapping):
        if key := find_key(obj, old):
            obj[key] = new  # type:ignore
            return True
        else:
            next_iter = list(obj.values())

    elif isinstance(obj, pyd.BaseModel):
        attrs = attr_map(obj, instance_fields(type(obj)).keys())
        if field := find_key(attrs, old):
            setattr(obj, field, new)
            return True
        else:
            next_iter = list(attrs.values())

    if next_iter and depth < 10:
        return any(
            map(
                ft.partial(nested_replace, old=old, new=new, depth=depth + 1),
                filter(
                    lambda val: val and isinstance(val, Collection | pyd.BaseModel),
                    next_iter,
                )
            )
        )
    return False


def parse_domain(url: str, default: str = '') -> str:
    if url:
        try:
            if host := pyd.HttpUrl(url).host:
                return host.replace('www.', '')
        except Exception:
            pass
    return default


def import_module(file: pyd.FilePath, root: pyd.DirectoryPath) -> ModuleType:
    validate_arch_file(file)
    pathstr = file.with_suffix('').relative_to(root).as_posix().replace('/', '.')
    return imp.import_module(pathstr)


# --------------------
# 5. Semantic Coercion
# --------------------
ROMAN_ARR = ['M', 'D', 'C', 'L', 'X', 'V', 'I']
ROMAN_MAP = dict(
    M=1000,
    D=500,
    C=100,
    L=50,
    X=10,
    V=5,
    I=1,
)

QUAD_RGX = re.compile(r'C{4}|X{4}|I{4}')
ROMAN_RGX = re.compile(r'(?i)(?:M{1,4}|CM|C?D|D?C{1,3}|XC|X?L|L?X{1,3}|IX|I?V|V?I{1,3})')


def decimal_to_roman(decimal: int) -> str:
    ans = ''
    for i, (char, val) in enumerate(ROMAN_MAP.items()):
        while decimal >= val:
            ans += char
            decimal -= val

        if decimal == 0:
            break

    # Fix quads of tens-places (e.g. IIII -> IV, XXXX -> XL, CCCC -> CD)
    for match in reversed(list(QUAD_RGX.finditer(ans))):
        char = match[0][0]
        d_idx = ROMAN_ARR.index(char)
        x0, x1 = match.span()
        half = ROMAN_ARR[d_idx - 1]
        if x0 > 0 and ans[x0 - 1] == half:
            ans = ans[:x0 - 1] + char + ROMAN_ARR[d_idx - 2] + ans[x1:]
        else:
            ans = ans[:x0] + char + half + ans[x1:]

    return ans


def roman_to_decimal(roman: str) -> int:
    ans = 0
    last_index = 0
    for match in ROMAN_RGX.finditer(roman):
        if match.start() != last_index:
            return 0
        else:
            last_index = match.end()

        v = [ROMAN_MAP[char] for char in match[0]]
        n_unique = len(set(v))
        if n_unique == 2:
            mod = v[0] * (-1 if v[1] > v[0] else 1)
            main = v[1] * (len(v) - 1)
            ans += main + mod
        elif n_unique == 1:
            ans += v[0] * len(v)
        else:
            return 0
    if last_index != len(roman):
        return 0

    return ans


BASELINES = [(10**9, 'B', 'GB'), (10**6, 'M', 'MB'), (10**3, 'K', 'KB'), (1, '', 'B')]


def format_amount(amount: int, unit: Literal['num', 'mem'] = 'num', width: int = 0) -> str:
    index = find(BASELINES, lambda trip: amount >= trip[0])
    if index > -1:
        suffix = str(BASELINES[index][1 if unit == 'num' else 2])
        content = round(amount / BASELINES[index][0])
        if width:
            return f'{content:>{width - len(suffix)}.{width-3}f}{suffix}'
        else:
            return f'{content}{suffix}'
    return f'{amount}'


# ---------------------
# 6. Syntactic Coercion
# ---------------------
def map_items(value: object) -> list[tuple[Any, Any]]:
    if not value:
        pass
    elif hasattr(value, 'items') and callable(value.items):
        return list(value.items())
    elif isinstance(value, Series) and all(isinstance(v, tuple) and len(v) == 2 for v in value):
        return list(value)
    return []


def pyd_schemify(tvar: type) -> pyd.GetPydanticSchema:
    return pyd.GetPydanticSchema(lambda _, __: pyd_schema.is_instance_schema(cls=tvar))


Regex = Annotated[re.Pattern, pyd_schemify(re.Pattern)]
PydDataFrame = Annotated[pd.DataFrame, pyd_schemify(pd.DataFrame)]

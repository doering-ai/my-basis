############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import Any, overload, TypeVar, TYPE_CHECKING
from collections.abc import Collection, Sequence, Iterable, Generator
from datetime import datetime, timedelta, UTC
from pathlib import Path
from shutil import get_terminal_size
from typing import ClassVar
from unittest.mock import MagicMock
import asyncio as aio
import functools as ft
import contextlib as ctx
import itertools as it
import shlex
import subprocess as sbp
import sys
import textwrap
import os
import logging
import regex as re

# I/O
import pickle
import tomllib

### EXTERNAL
import pydantic as pyd
import more_itertools as mi

### INTERNAL (NOTE: If adding new internal imports, update the comments in `__init__.py`)
# Local imports
from ..infra.constants import NOWHERE
from ..infra.types import (
    Atom,
    Vec,
    Struct,
)
from ._UtilsBase import _UtilsBase
from .TextUtils import text_utils

# `srsly`/`tomli_w` are unconditional dependencies (see `pyproject.toml`), but are imported
# lazily through `_UtilsBase._optional_import()` at each call site below so bare `import my`
# does not require them -- only the methods that actually serialize YAML/JSON/TOML do.
if TYPE_CHECKING:
    from srsly._yaml_api import CustomYaml

# from typing import TYPE_CHECKING
# if TYPE_CHECKING:
#     from ..typing.Typist import Typist

############
### DATA ###
############
_branch = text_utils.multi_rgx


# Misc aliases
File = pyd.FilePath
Directory = pyd.DirectoryPath

ClassType = TypeVar('ClassType')

FileParam = str | bytes | Path | None
RawJsonData = str | int | float | bool | list | dict | None

F = TypeVar('F')
logger = logging.getLogger(__name__)


############
### BODY ###
############
class SystemUtils(_UtilsBase):
    """Methods that deal with low-level system resources & APIs."""

    AUTO_CONFIRM: ClassVar[bool] = False
    #: Built and configured lazily by `_yaml_config()` -- never read this directly.
    _YAML_CONFIG: ClassVar[CustomYaml | None] = None
    LOGGER: ClassVar[logging.Logger] = logger

    ### Regular Expressions (can't use RegexStore because it depends on this class)
    RGXS: ClassVar[dict[str, re.Pattern]] = text_utils.regex_dict(
        ### Filetypes
        filetype=_branch(
            r'(?P<json>jso?n[\dc]|(?:geo|topo|nd)?json)',
            r'(?P<yaml>ya?ml)',
            r'(?P<pickle>pkl|pickle|bin|dat)',
            r'(?P<toml>to?ml)',
            r'(?P<xml>xml|html)',
            pre=r'(?i)\.',
        ),
        pathy=_branch(
            r'[/\\]',
            r'\.\.',
            r'~',
        ),
        yaml_fence=(
            r'(?ims)\A\s*```[ \t]*ya?ml[ \t]*\r?\n'
            r'(?P<content>.*?)^```[ \t]*(?:\r?\n)?\s*\Z'
        ),
    )

    # ---------------
    # `0` DATE & TIME
    # ---------------
    @classmethod
    def posix(cls, val: int | float | datetime | None = None) -> datetime:
        """Convert a timestamp or datetime to UTC datetime.

        Args:
            val: Unix timestamp (int/float), datetime object, or None for current time. Naive
                datetimes are interpreted as UTC; aware datetimes are converted to UTC.
        Returns:
            Timezone-aware datetime in UTC.
        Examples:
            Everything becomes an aware UTC datetime::

                >>> from my import ut
                >>> ut.posix(0)
                datetime.datetime(1970, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)
        """
        if val is None:
            return datetime.now(UTC)
        elif isinstance(val, datetime):
            if val.tzinfo is None or val.utcoffset() is None:
                return val.replace(tzinfo=UTC)
            return val.astimezone(UTC)
        else:
            return datetime.fromtimestamp(val, UTC)

    @classmethod
    def posix_since(cls, val: int | float | datetime | None = None) -> timedelta:
        """Calculate time elapsed since a given timestamp.

        Args:
            val: Unix timestamp (int/float), datetime object, or None.
        Returns:
            Timedelta representing elapsed time, or zero when val is None.
        Examples:
            A missing value yields zero; Unix epoch remains a real timestamp::

                >>> from my import ut
                >>> ut.posix_since(None)
                datetime.timedelta(0)
                >>> ut.posix_since(0).total_seconds() > 0
                True
        """
        if val is None:
            return timedelta(0)
        else:
            return cls.posix() - cls.posix(val)

    @classmethod
    def milliseconds(cls, val: int | float | datetime | timedelta | None = None) -> int:
        """Convert a timedelta, datetime, or numeric timestamp to milliseconds.

        Args:
            val: A timedelta, a datetime, a numeric timestamp, or None for the current time.
                A numeric value `< 10` is treated as already being in seconds (e.g. a small
                relative duration) rather than a Unix timestamp, and scaled up.
        Returns:
            The equivalent millisecond count, rounded to the nearest integer.
        Examples:
            A `timedelta` and a `datetime` both convert directly::

                >>> from datetime import timedelta, datetime, timezone
                >>> from my import ut
                >>> ut.milliseconds(timedelta(seconds=1))
                1000
                >>> ut.milliseconds(datetime(1970, 1, 2, tzinfo=timezone.utc))
                86400000
        """
        if val is None:
            val = cls.posix()

        if isinstance(val, timedelta):
            return round(val.total_seconds() * 1000)
        elif isinstance(val, datetime):
            return round(val.timestamp() * 1000)
        else:
            return int((val * 1000) if val < 10 else val)

    # --------------
    # `1` FILESYSTEM
    # --------------
    @classmethod
    def validate_dir(cls, *paths: pyd.DirectoryPath) -> bool:
        """Validate that all provided paths are existing directories.

        Args:
            *paths: One or more directory paths to validate.
        Returns:
            True if all paths are valid directories.
        Raises:
            AssertionError: If any path is invalid or not a directory.
        Examples:
            Existing directories pass::

                >>> from pathlib import Path
                >>> from my import ut
                >>> ut.validate_dir(Path('/tmp'))
                True
        """
        for path in paths:
            assert path and path.exists() and path.is_dir(), f'Invalid directory: {path.as_posix()}'
        return True

    @classmethod
    def validate_file(cls, *paths: pyd.FilePath) -> bool:
        """Validate that all provided paths are existing files.

        Args:
            *paths: One or more file paths to validate.
        Returns:
            True if all paths are valid files.
        Raises:
            AssertionError: If any path is invalid or not a file.
        Examples:
            Only real files pass::

                >>> import tempfile
                >>> from pathlib import Path
                >>> from my import ut
                >>> file = Path(tempfile.mkdtemp()) / 'data.txt'
                >>> _ = file.write_text('hi')
                >>> ut.validate_file(file)
                True
        """
        for path in paths:
            assert path and path.exists() and path.is_file(), f'Invalid file: {path.as_posix()}'
        return True

    @classmethod
    def path_sub(cls, path: Path, old: str, new: str) -> Path:
        """Substitute a path component with a new value.

        Args:
            path: Path object to modify.
            old: Path component to replace.
            new: Replacement path component.
        Returns:
            New Path with substitution applied, or original if old not found.
        Examples:
            Swap a single component::

                >>> from pathlib import Path
                >>> from my import ut
                >>> ut.path_sub(Path('/repo/src/app.py'), 'src', 'lib')
                PosixPath('/repo/lib/app.py')
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
    @classmethod
    def get_terminal_width(cls) -> int:
        """Get the current terminal width in characters.

        Returns:
            Terminal width (defaults to 100 if unavailable).
        """
        return get_terminal_size((100, 100))[0]

    @classmethod
    def terminal_linewrap(cls, text: str, indent: int = 0) -> str:
        r"""Wrap text to fit within terminal width.

        Args:
            text: Text to wrap.
            indent: Number of characters to reserve for indentation (default: 0).
        Returns:
            Text wrapped to terminal width minus indent.
        Examples:
            Re-wrap prose to the current terminal (width varies by session)::

                >>> from my import ut
                >>> ut.terminal_linewrap('A very long paragraph ...')  # doctest: +SKIP
                'A very long\nparagraph ...'
        """
        return textwrap.fill(
            text_utils.unwrap_paragraphs(text), width=cls.get_terminal_width() - indent
        )

    @staticmethod
    def osc11_sequence(hex_color: str) -> str:
        r"""Build the OSC 11 (set terminal background color) escape sequence.

        Args:
            hex_color: The hex color value (e.g. ``'#1A2B3C'``).
        Returns:
            The raw escape sequence, unemitted.
        Examples:
            The sequence is `\x1b]11;` + color + BEL::

                >>> from my import ut
                >>> ut.osc11_sequence('#212225')
                '\x1b]11;#212225\x07'
        """
        return f'\033]11;{hex_color}\007'

    @classmethod
    def _emit_osc(cls, seq: str, stdout_fallback: bool) -> bool:
        """Write a raw OSC escape sequence to the terminal device. See `emit_osc11()`."""
        if sys.platform == 'win32':
            with ctx.suppress(Exception):
                import ctypes

                kernel32 = ctypes.windll.kernel32
                kernel32.SetConsoleMode(kernel32.GetStdHandle(-10), 7)
        else:
            with ctx.suppress(OSError), Path('/dev/tty').open('w') as tty:
                tty.write(seq)
                return True
        if not stdout_fallback:
            return False
        sys.stdout.write(seq)
        sys.stdout.flush()
        return False

    @classmethod
    def emit_osc11(cls, hex_color: str, stdout_fallback: bool = True) -> bool:
        r"""Set the terminal's background color via an OSC 11 escape sequence.

        Writes to ``/dev/tty`` on POSIX -- robust against stdout redirection, so a caller
        whose stdout is captured (e.g. a harness hook) still tints -- after attempting to
        enable VT processing on Windows.

        Args:
            hex_color: The hex color value (e.g. ``'#1A2B3C'``).
            stdout_fallback: When True (default), write the sequence to ``sys.stdout`` when
                ``/dev/tty`` is unavailable -- right for CLIs and shell prompts, where stdout
                *is* the terminal. Pass False from callers whose stdout is captured (hooks,
                pipelines), where a leaked escape would surface as transcript garbage.
        Returns:
            True if the sequence went to ``/dev/tty``, False if it fell back to stdout or
            was suppressed.
        Examples:
            Tint the current terminal's background::

                >>> from my import ut
                >>> ut.emit_osc11('#212225')  # doctest: +SKIP
                True
        """
        return cls._emit_osc(cls.osc11_sequence(hex_color), stdout_fallback)

    @classmethod
    def set_tab_title(cls, title: str, stdout_fallback: bool = True) -> bool:
        r"""Set the terminal tab/window title via an OSC 0 escape sequence.

        Same ``/dev/tty`` discipline and `stdout_fallback` contract as `emit_osc11()`.

        Args:
            title: The new icon name + window title.
            stdout_fallback: See `emit_osc11()`.
        Returns:
            True if the sequence went to ``/dev/tty``, False if it fell back to stdout or
            was suppressed.
        Examples:
            Title the current tab::

                >>> from my import ut
                >>> ut.set_tab_title('corpus:main')  # doctest: +SKIP
                True
        """
        return cls._emit_osc(f'\033]0;{title}\007', stdout_fallback)

    @staticmethod
    def auto_confirm() -> None:
        """Enable auto-confirmation mode for all confirmation prompts.

        Examples:
            Make every subsequent `confirm()` return True (skipped: flips global state)::

                >>> from my import ut
                >>> ut.auto_confirm()      # doctest: +SKIP
                >>> ut.confirm('Proceed?')  # doctest: +SKIP
                True
        """
        SystemUtils.AUTO_CONFIRM = True

    @staticmethod
    def zsh_colorize(
        text: str,
        color: str,
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
    ) -> str:
        r"""Wrap text in zsh color codes with optional styles.

        Args:
            text: Text to colorize.
            color: Zsh color name or code.
            bold: If True, apply bold style (default: False).
            italic: If True, apply italic style (default: False).
            underline: If True, apply underline style (default: False).
        Returns:
            Colorized text with zsh codes, or original text if color is empty.
        Examples:
            Wrap text in zsh prompt-expansion codes, plus ANSI styling::

                >>> from my import ut
                >>> ut.zsh_colorize('hi', 'red')
                '%F{red}hi%f'
                >>> ut.zsh_colorize('hi', 'red', bold=True)
                '\x1b[1m%F{red}hi%f\x1b[22m'
        """
        # I. Validate arguments
        if not (text and color):
            return text or ''

        # II. Wrap text in (relatively-fancy) zsh coloring syntax
        ret = f'%F{{{color}}}{text}%f'

        # III. Wrap result in universal ANSI codes for bold/italic/underline
        if bold:
            ret = f'\033[1m{ret}\033[22m'
        if italic:
            ret = f'\033[3m{ret}\033[23m'
        if underline:
            ret = f'\033[4m{ret}\033[24m'

        return ret

    @classmethod
    def print_in_color(cls, text: str, **kwargs: Any) -> None:
        """Print colored text using zsh prompt expansion.

        Note:
            Requires zsh to be available in the system PATH. `text` is passed as an argv
            value (never interpolated into a shell string), so it reaches `print -P` via
            `$1` and cannot trigger `$(...)`/backtick command substitution.

        Args:
            text: Text with zsh color codes already present.
            **kwargs: Additional arguments for `print()`.
        Examples:
            Render zsh color codes to the terminal::

                >>> from my import ut
                >>> ut.print_in_color(ut.zsh_colorize('done', 'green'))  # doctest: +SKIP
                done
        """
        ret = sbp.run(
            ['zsh', '-c', 'print -P -- "$1"', 'zsh', text],
            capture_output=True,
            text=True,
            shell=False,
        )
        print((ret.stdout or '').strip('\n'), **kwargs)

    @staticmethod
    def confirm(prompt: str, default_no: bool = False) -> bool:
        """Prompt user for confirmation with y/n input.

        Args:
            prompt: Question to display to user.
            default_no: If True, default to 'no' (default: False defaults to 'yes').
        Returns:
            True if user confirms, False otherwise. Always True if auto-confirm enabled.
        Examples:
            Prompt interactively (unless `auto_confirm()` was enabled)::

                >>> from my import ut
                >>> ut.confirm('Overwrite?')  # doctest: +SKIP
                Overwrite? [Y/n] y
                True
        """
        if SystemUtils.AUTO_CONFIRM:
            return True
        elif default_no:
            return input(f'{prompt} [y/N] ').lower().strip().startswith('y')
        else:
            return not input(f'{prompt} [Y/n] ').lower().strip().startswith('n')

    @staticmethod
    def is_installed(*modules: str) -> bool:
        """Check if specified Python modules are installed.

        Args:
            *modules: Importable module names to check.
        Returns:
            True if every module imports cleanly, False otherwise.
        Examples:
            Probe for optional dependencies::

                >>> from my import ut
                >>> ut.is_installed('json')
                True
                >>> ut.is_installed('not_a_module')
                False
        """
        try:
            for module in modules:
                __import__(module)
        except ImportError:
            return False
        return True

    @staticmethod
    def mock_if_uninstalled(target: str, *dependencies: str) -> bool:
        """Mock the target module if any of the specified dependencies are not installed.

        Args:
            target: Module name to replace with a MagicMock in `sys.modules`.
            *dependencies: Modules that must all be installed to leave the target untouched.
        Returns:
            True if all dependencies are installed, False if the target was mocked.
        Examples:
            Stub out an optional integration when its backend is missing::

                >>> from my import ut
                >>> ut.mock_if_uninstalled('my_pkg.viz', 'matplotlib')  # doctest: +SKIP
                False
        """
        if not SystemUtils.is_installed(*dependencies):
            sys.modules[target] = MagicMock()
            return False
        return True

    @classmethod
    def _multiprint_data(
        cls,
        data: Collection[tuple | pyd.BaseModel | dict] | pyd.BaseModel | dict | Any | None,
        shorten: bool = False,
        depth: int = 0,
    ) -> Iterable[str]:
        """Internal method to recursively format nested data structures for `multiprint()`."""
        _in = '\t' * depth
        if data is None:
            return

        # I. Series
        elif isinstance(data, str):
            yield f'{_in}{textwrap.shorten(data, 64, placeholder="...")}'
            return
        elif isinstance(data, (set, Sequence)):
            if len(str(data)) < 32:
                yield f'{_in}{data}'
                return

            for item in data:
                for child_line in cls._multiprint_data(item, shorten, depth + 1):
                    if mi.ilen(it.takewhile(lambda s: s == '\t', child_line)) == depth + 1:
                        yield f'{_in}- {child_line.strip()}'
                    else:
                        yield f'  {child_line}'

        # II. Mappings
        elif isinstance(data, (dict, pyd.BaseModel)):
            if isinstance(data, pyd.BaseModel):
                data = data.model_dump(exclude_defaults=True)

            if len(str(data)) < 32:
                yield f'{_in}{data}'
                return

            for key, val in data.items():
                children = list(cls._multiprint_data(val, shorten, depth + 1))
                if len(children) == 1:
                    yield f'{_in}{key}: {children[0].strip()}'
                else:
                    yield f'{_in}{key}:'
                    yield from children

        # III. All Others
        elif isinstance(data, type):
            yield f'{_in}{data.__name__}'
        else:
            yield f'{_in}{data}'

    @classmethod
    def multiprint(
        cls,
        *items: Any,
        title: str = '',
        lines: Iterable[str] | None = None,
        data: dict | pyd.BaseModel | set | Sequence | None = None,
        indent: int = 0,
        indent_range: tuple[int, int] = (0, 0),
        shorten: bool = False,
        quiet: bool = False,
        margins: tuple[int, int] = (0, 1),
        **kwargs: Any,
    ) -> str:
        """Flexibly print multiple lines with a few convenient features for plaintext formatting.

        Args:
            *items: Items to print after being converted to strings.
            title: Title line(s) to print before any indented content. Sets indent to 4 if unset.
            lines: Additional lines to print (in addition to the items), as an iterable of strings.
            data: Additional key-value pairs to print as "key: value" lines after the items.
            indent: Number of spaces to indent each line by.
            indent_range: Optional subset of line indices to apply the indent to.
            shorten: If true, apply some basic shortening techniques to the output.
            quiet: Do not print anything to stdout, just return the formatted string.
            margins: Number of newlines to print before and after the content.
            **kwargs: Additional keyword arguments to pass to `print()`.
        Returns:
            The constructed multiline string.
        Examples:
            Compose a titled block; `quiet` returns it without printing::

                >>> from my import ut
                >>> out = ut.multiprint('a', 'b', title='Letters:', quiet=True)
                >>> print(out, end='')
                Letters:
                    a
                    b
        """
        # I. Preprocess items into lines
        lines = list(
            mi.flatten(
                map(
                    str.splitlines,
                    it.chain(
                        lines or [],
                        map(str, items),
                        cls._multiprint_data(data, shorten),
                    ),
                )
            )
        )

        # II. Handle title lines, which are merely shorthand for indented lines at the top
        if title:
            indent = indent or 4
            indent_range = (indent_range[0] + 1, indent_range[1])
            lines.insert(0, title)

        # III. Handle indents, which can apply to all or just some of the output
        if indent:
            prefix = ' ' * indent
            for i in range(indent_range[0], (indent_range[1] or len(lines))):
                lines[i] = f'{prefix}{lines[i]}'

        # IV. Join the lines into a single result, and optionally print it to stdout if requested
        ret = ('\n' * margins[0]) + '\n'.join(lines) + ('\n' * margins[1])
        if not quiet:
            print(ret, **kwargs)
        return ret

    @staticmethod
    @ctx.contextmanager
    def debug_fence(
        content: Any,
        mark: str = '-',
        width: int = -1,
        indent: int = 0,
    ) -> Generator:
        """Context manager for printing debug information with a clear visual fence.

        Args:
            content: Header content to display in the middle of the fence's start.
            mark: Character(s) to use for the fence lines.
            width: Total width of the fence lines. Leave empty to try to infer terminal width.
            indent: Number of spaces to indent the fence lines.
        Examples:
            Fence a noisy block of output::

                >>> from my import ut
                >>> with ut.debug_fence('start', width=20):
                ...     print('body')
                --------------------
                ------ start -------
                body
                --------------------
        """
        if indent:
            width -= indent
            pre = ' ' * indent
        else:
            pre = ''

        if not width or width <= 0:
            width = SystemUtils.get_terminal_width()

        mark = mark.strip()
        if not mark:
            mark = '-'
        delim = (mark * (width // len(mark) + 1))[:width]
        print(f'{pre}{delim}')
        if content:
            content = f' {content} '
            remaining = width - len(content)
            _halves = (remaining // 2, remaining // 2 + (1 if remaining % 2 else 0))
            left, right = tuple((mark * (_half // len(mark) + 1))[:_half] for _half in _halves)
            print(f'{pre}{left}{content}{right}')
        yield
        print(f'{pre}{delim}')

    @staticmethod
    @ft.lru_cache(maxsize=2**9)
    def _path(pathstr: str) -> Path:
        # Refuse empty paths and unexpanded vars
        pathstr = os.path.expandvars(pathstr)
        if pathstr.startswith('$') or not pathstr.strip():
            return NOWHERE
        return Path(pathstr).expanduser().resolve()

    @classmethod
    def path(cls, raw: str | Path | None) -> Path:
        """Attempt to resolve path with a flexible set of intuitive, iterative steps.

        Args:
            raw: A path which may or may not be absolute, existent, or even valid.
        Returns:
            Ideally a resolved version of that same path, else `NOWHERE`. `NOWHERE` is the
            single, non-traversable sentinel used across `my` for "no path": it reports
            `exists()` as ``False`` and yields nothing from traversal methods.
        Examples:
            Expand and resolve; unusable input collapses to the `NOWHERE` sentinel::

                >>> from my import ut
                >>> ut.path('~/notes.txt').is_absolute()
                True
                >>> ut.path(None)
                NOWHERE
        """
        return cls._path(str(raw or ''))

    @classmethod
    def log(cls, *args: Any, _level: int = 0, **kwargs: Any) -> None:
        """Log the provided collection of strings, applying common-sense transformations.

        Nested iterables are flattened and stringified before joining, so `info()`, `warn()`, and
        `error()` all accept loosely-structured arguments.

        Args:
            *args: Values (or nested iterables of values) to join into one message.
            _level: Numeric logging level to emit at.
            **kwargs: Reserved for logger compatibility; currently unused.
        Examples:
            Compose one message from loose parts::

                >>> from my import ut
                >>> ut.info('loaded', [1, 2], 'records')  # doctest: +SKIP
        """
        message = ' '.join(map(str, mi.collapse(args or [''], base_type=str)))
        cls.LOGGER.log(_level, message)

    @classmethod
    def info(cls, *args: Any, **kwargs: Any) -> None:
        """Log the provided collection of strings at the INFO level."""
        cls.log(args, _level=logging.INFO, **kwargs)

    @classmethod
    def error(cls, *args: Any, **kwargs: Any) -> None:
        """Log the provided collection of strings at the ERROR level."""
        cls.log(args, _level=logging.ERROR, **kwargs)

    @classmethod
    def warn(cls, *args: Any, **kwargs: Any) -> None:
        """Log the provided collection of strings at the WARNING level."""
        cls.log(args, _level=logging.WARN, **kwargs)

    # ------------
    # `3` FILE I/O
    # ------------
    @overload
    @classmethod
    def from_file(cls, file: FileParam) -> dict: ...
    @overload
    @classmethod
    def from_file(cls, file: FileParam, tvar: type[F], cast: bool = True) -> F: ...
    @classmethod
    def from_file(
        cls,
        file: FileParam,
        tvar: type[F] = dict,  # ty:ignore[invalid-parameter-default]
        cast: bool = True,
    ) -> F:
        """Load data from local JSON, YAML, TOML, or Pickle file, then cast to target type.

        In order to cast between the by-far two most common expected types--dict and list--Typist
        will wrap uncastable values in a dict (w/ one key, `'content'`) or a list (w/ one value).

        Args:
            file: Path to the file to load. Note that raw content is NOT accepted here.
            tvar: Target type to cast the loaded data to (dict by default). Like `cast()`, you
                  can use complex, nested types here if desired.
            cast: If True, try to coerce unexpected types before raising an error.
        Returns:
            Loaded and cast data from the file.
        Examples:
            Round-trip a mapping through YAML on disk::

                >>> import tempfile
                >>> from pathlib import Path
                >>> from my import ut
                >>> file = Path(tempfile.mkdtemp()) / 'cfg.yaml'
                >>> ut.to_file({'name': 'basis', 'tags': ['a', 'b']}, file)
                >>> ut.from_file(file)
                {'name': 'basis', 'tags': ['a', 'b']}
        """
        if not file:
            raise ValueError('No file provided.')
        # NOTE: don't round-trip through `cls.ty.cast(file, str)` here -- the generic type-cast
        # machinery has no registered `Path -> str` transform (only `String`-family sources), so
        # it silently returns `None` for `Path`/`Traversable` inputs. `cls.path()` already
        # accepts `str | Path | None` directly (mirroring the `isinstance(file, Path)` branches
        # in the sibling `from_json`/`from_yaml` loaders), so hand it the raw value instead.
        resolved = cls.path(file)  # type: ignore[arg-type]
        if not resolved or not resolved.is_file():
            raise ValueError(f'No/Invalid file provided: {file}')
        elif match := cls.RGXS['filetype'].fullmatch(resolved.suffix):
            # `groupdict()` maps every named alternative to `None` except the one that matched --
            # filter on the *values* to find which key matched, not the (always-truthy) key names.
            group = next(k for k, v in match.groupdict().items() if v)
            if fn := getattr(cls, f'from_{group}', None):
                return fn(resolved, tvar, cast)
        raise ValueError(f'Unsupported file type: {resolved}')

    @classmethod
    def to_file(cls, data: Atom | Struct, file: str | File) -> None:
        """Save data to local JSON, YAML, TOML, or Pickle file (depending on file suffix).

        Args:
            data: The data to save.
            file: Path to the file to save. Note that raw strings are NOT allowed here.
        Examples:
            The suffix picks the serialization format::

                >>> import tempfile
                >>> from pathlib import Path
                >>> from my import ut
                >>> file = Path(tempfile.mkdtemp()) / 'data.json'
                >>> ut.to_file([1, 2], file)
                >>> ut.from_json(file, list)
                [1, 2]
        """
        if not file:
            return
        elif not isinstance(file, Path):
            file = Path(file).expanduser()

        file.parent.mkdir(parents=True, exist_ok=True)
        if file.suffix in ['.yml', '.yaml']:
            file.write_text(cls.to_yaml(data))
        elif file.suffix in ['.json']:
            file.write_text(cls.to_json(data))
        elif file.suffix in ['.tml', '.toml']:
            file.write_text(cls.to_toml(data))
        elif file.suffix in ['.pkl']:
            file.write_bytes(cls.to_pickle(data))
        else:
            cls.LOGGER.error(f'Unsupported file type: {file}')

    @overload
    @classmethod
    def from_json(cls, file: FileParam) -> dict: ...

    @overload
    @classmethod
    def from_json(cls, file: FileParam, tvar: type[F], cast: bool = True) -> F: ...

    @classmethod
    def from_json(
        cls,
        file: FileParam,
        tvar: type[F] = dict,  # ty:ignore[invalid-parameter-default]
        cast: bool = True,
    ):
        """Load data from JSON file or string, then cast to target type. See `from_file()`.

        Args:
            file: Path to the file to load, or raw JSON string/bytes.
            tvar: Target type to cast the loaded data to (dict by default). Like `cast()`, you
                  can use complex, nested types here if desired.
            cast: If False, data that doesn't match the expected return type raises an error.
        Returns:
            Loaded and cast data from the file/string.
        Examples:
            Parse a raw string, casting to the requested type::

                >>> from my import ut
                >>> ut.from_json('{"a": 1}')
                {'a': 1}
                >>> ut.from_json('[1, 2]', list)
                [1, 2]
        """
        if not file:
            return tvar()  # type: ignore
        elif isinstance(file, Path):
            cls.validate_file(file)
            ret = cls._optional_import('srsly').read_json(file)
        elif (text := cls.ty.cast(file, str)) is not None:
            ret = cls._optional_import('srsly').json_loads(text)
        else:
            raise ValueError(f'Unsupported input type for JSON loading: {type(file)}')

        if isinstance(ret, tvar):
            return ret
        elif cast:
            return tvar(ret)  # type: ignore
        else:
            raise TypeError(f'Expected `{tvar}`, got `{type(ret)}`.')

    @classmethod
    def is_pathy(cls, text: str) -> bool:
        """Heuristic check for whether a string looks like a file path.

        Args:
            text: Candidate string.
        Returns:
            True if the string is path-length and contains path-like markers.
        Examples:
            Separate paths from prose::

                >>> from my import ut
                >>> ut.is_pathy('~/notes/todo.md')
                True
                >>> ut.is_pathy('hello')
                False
        """
        return bool(4 < len(text) < 255 and cls.RGXS['pathy'].search(text))

    @overload
    @classmethod
    def from_yaml(cls, file: FileParam) -> dict: ...
    @overload
    @classmethod
    def from_yaml(cls, file: FileParam, tvar: type[F], cast: bool = True) -> F: ...
    @classmethod
    def from_yaml(
        cls,
        file: FileParam,
        tvar: type[F] = dict,  # ty:ignore[invalid-parameter-default]
        cast: bool = True,
    ) -> F:
        r"""Load data from YAML file or string, then cast to target type. See `from_file()`.

        Note:
            Complete markdown fences tagged `yaml` or `yml` are unwrapped case-insensitively;
            spaces around the tag and surrounding block are ignored.

        Args:
            file: Path to the file to load, or raw YAML string/bytes.
            tvar: Target type to cast the loaded data to (dict by default). Like `cast()`, you
                  can use complex, nested types here if desired.
            cast: If False, data that doesn't match the expected return type raises an error.
        Returns:
            Loaded and cast data from the file/string.
        Raises:
            ValueError: If an input beginning with a markdown fence is not a complete `yaml` or
                `yml` block.
        Examples:
            Parse raw or markdown-fenced YAML::

                >>> from my import ut
                >>> ut.from_yaml('a: 1\nb: [x, y]')
                {'a': 1, 'b': ['x', 'y']}
                >>> ut.from_yaml('```YML\nanswer: 42\n```')
                {'answer': 42}
        """
        # I. Parse the content using an external library
        if not file:
            # I.i. Empty case
            return tvar()  # type: ignore
        elif isinstance(file, Path):
            # I.ii. Local case: Read directly from file
            cls.validate_file(file)
            ret = cls._optional_import('srsly').read_yaml(file)
        else:
            # I.iii. Main Case: Attempt to parse in-memory YAML strings
            text = file.decode() if isinstance(file, bytes) else file
            if text.lstrip().startswith('```'):
                match = cls.RGXS['yaml_fence'].fullmatch(text)
                if match is None:
                    raise ValueError(
                        'Invalid YAML fence: expected a complete ```yaml or ```yml block.'
                    )
                text = match.group('content')

            ret = cls._optional_import('srsly').yaml_loads(text)

        # II. Verify & format the response
        # if isinstance(ret, tvar):
        if cls.ty.check(ret, tvar):
            return ret
        elif not ret:
            return tvar()  # type: ignore
        elif cast:
            with ctx.suppress(ValueError):
                return tvar(ret)  # type: ignore
        raise TypeError(f'Expected `{tvar}`, got `{type(ret)}`.')

    @overload
    @classmethod
    def from_toml(cls, file: FileParam) -> dict: ...

    @overload
    @classmethod
    def from_toml(cls, file: FileParam, tvar: type[F], cast: bool = True) -> F: ...

    @classmethod
    def from_toml(
        cls,
        file: FileParam,
        tvar: type[F] = dict,  # type: ignore
        cast: bool = True,
    ) -> F:
        """Load data from TOML file or string, then cast to target type. See `from_file()`.

        Args:
            file: Path to the file to load, or raw TOML string/bytes.
            tvar: Target type to cast the loaded data to (dict by default). Like `cast()`, you
                  can use complex, nested types here if desired.
            cast: If False, data that doesn't match the expected return type raises an error.
        Returns:
            Loaded and cast data from the file/string.
        Examples:
            Parse an in-memory TOML string::

                >>> from my import ut
                >>> ut.from_toml('x = 1')
                {'x': 1}
        """
        tvar = cls.ty.specify(tvar)
        if not file:
            return tvar()  # type: ignore
        elif isinstance(file, Path):
            cls.validate_file(file)
            text = file.read_text()
        else:
            text = file.decode() if isinstance(file, bytes) else file
        ret = tomllib.loads(text)

        if isinstance(ret, tvar):
            return ret
        elif cast:
            return tvar(ret)  # type: ignore
        else:
            raise TypeError(f'Expected `{tvar}`, got `{type(ret)}`.')

    @overload
    @classmethod
    def from_pickle(cls, file: FileParam) -> dict: ...

    @overload
    @classmethod
    def from_pickle(cls, file: FileParam, tvar: type[F], cast: bool = True) -> F: ...

    @classmethod
    def from_pickle(
        cls,
        file: FileParam,
        tvar: type[F] = dict,  # ty:ignore[invalid-parameter-default]
        cast: bool = True,
    ) -> F:
        """Load data from Pickle file or bytes, then cast to target type. See `from_file()`.

        Args:
            file: Path to the file to load, or raw Pickle bytes/string.
            tvar: Target type to cast the loaded data to (dict by default). Like `cast()`, you
                  can use complex, nested types here if desired.
            cast: If False, data that doesn't match the expected return type raises an error.
        Returns:
            Loaded and cast data from the file/string.
        Examples:
            Round-trip through Pickle bytes::

                >>> from my import ut
                >>> ut.from_pickle(ut.to_pickle([1, 2]), list)
                [1, 2]
        """
        if not file:
            return tvar()  # type: ignore
        elif isinstance(file, Path):
            cls.validate_file(file)
            raw = file.read_bytes()
        else:
            raw = file.encode() if isinstance(file, str) else file
        ret = pickle.loads(raw)

        if isinstance(ret, tvar):
            return ret
        elif cast:
            return tvar(ret)  # type: ignore
        else:
            raise TypeError(f'Expected `{tvar}`, got `{type(ret)}`.')

    @classmethod
    def to_yaml(cls, data: Atom | Struct, wrap: bool = False, **kwargs) -> str:
        """Serialize data to a YAML string. See `to_file()` for general details.

        Args:
            data: The data to serialize.
            wrap: If True, wrap the output in markdown backticks for YAML.
            **kwargs: Additional keyword arguments to pass to `srsly.yaml_dumps()`.
        Returns:
            YAML string representation of the data.
        Examples:
            Serialize with the project's block-style indentation::

                >>> from my import ut
                >>> print(ut.to_yaml({'a': 1, 'b': [1, 2]}), end='')
                a: 1
                b:
                    - 1
                    - 2
        """
        obj = cls.ty.serialize(data)
        text = cls._yaml_config().dump(obj, **kwargs)
        assert isinstance(text, str), 'Failed to write YAML data.'

        # If we printed a root array, de-intent it
        if isinstance(data, Vec) and text.startswith(' '):
            text = textwrap.dedent(text)

        # If requested, wrap in markdown bactics
        if wrap:
            text = f'```yaml\n{text}\n```'
        return text

    @classmethod
    def to_json(cls, data: Atom | Struct, wrap: bool = False, **kwargs) -> str:
        """Serialize data to a JSON string. See `to_file()` for general details.

        Args:
            data: The data to serialize.
            wrap: If True, wrap the output in markdown backticks for JSON.
            **kwargs: Additional keyword arguments to pass to `srsly.json_dumps()`.
        Returns:
            JSON string representation of the data.
        Examples:
            Serialize with 4-space indentation::

                >>> from my import ut
                >>> print(ut.to_json({'a': 1}))
                {
                    "a":1
                }
        """
        obj = cls.ty.serialize(data)
        if 'indent' not in kwargs:
            kwargs['indent'] = 4
        text = cls._optional_import('srsly').json_dumps(obj, **kwargs)

        # If requested, wrap in markdown bactics
        if wrap:
            text = f'```json\n{text}\n```'
        return text

    @classmethod
    def to_toml(cls, data: Atom | Struct, wrap: bool = False, **kwargs) -> str:
        """Serialize data to a TOML string. See `to_file()` for general details.

        Args:
            data: The data to serialize.
            wrap: If True, wrap the output in markdown backticks for TOML.
            **kwargs: Additional keyword arguments to pass to `tomli_w.dumps()`.
        Returns:
            TOML string representation of the data.
        Examples:
            Serialize a mapping::

                >>> from my import ut
                >>> print(ut.to_toml({'x': 1}), end='')
                x = 1
        """
        obj = cls.ty.serialize(data)

        # Cast to dict, as toml only accepts dicts at the top level
        if not isinstance(obj, dict):
            if isinstance(obj, Vec) and len(obj) == 1 and isinstance((_obj := mi.first(obj)), dict):
                obj = _obj
            else:
                obj = dict(content=obj)

        # II. Serialize w/ default params
        text = cls._optional_import('tomli_w').dumps(obj, **kwargs)

        # If requested, wrap in markdown bactics
        if wrap:
            text = f'```toml\n{text}\n```'
        return text

    @classmethod
    def to_pickle(cls, data: Atom | Struct, **kwargs) -> bytes:
        """Serialize data to Pickle bytes. See `to_file()` for general details.

        Args:
            data: The data to serialize.
            **kwargs: Additional keyword arguments to pass to `pickle.dumps()`.
        Returns:
            Pickle byte representation of the data.
        Examples:
            Feed the bytes straight back to `from_pickle()`::

                >>> from my import ut
                >>> ut.from_pickle(ut.to_pickle({'a': 1}))
                {'a': 1}
        """
        obj = cls.ty.serialize(data)
        return pickle.dumps(obj, **kwargs)

    @classmethod
    def _yaml_config(cls) -> CustomYaml:
        """Return the shared YAML dumper, building and configuring it on first use.

        Building `CustomYaml` -- and therefore importing `srsly` -- is deferred to this
        accessor (instead of a class-body `ClassVar[CustomYaml] = CustomYaml()`) so that
        importing `SystemUtils`, and therefore bare `import my`, does not require `srsly`
        to be installed. Only a YAML-serializing call pays that cost.

        Returns:
            The process-shared, already-configured `CustomYaml` instance.
        Raises:
            ImportError: If the optional `srsly` dependency is not installed.
        """
        if SystemUtils._YAML_CONFIG is None:
            cls._optional_import('srsly')  # clear error naming `srsly` if entirely missing
            from srsly._yaml_api import CustomYaml as _CustomYaml

            SystemUtils._YAML_CONFIG = _CustomYaml()
            cls._configure_yaml()
        return SystemUtils._YAML_CONFIG

    @staticmethod
    def _configure_yaml(
        mapping: int = 4,
        sequence: int = 6,
        offset: int = 4,
        sort_keys: bool = False,
    ) -> None:
        """Configure the YAML formatting library's defaults up front.

        See the [yaml docs](https://yaml.readthedocs.io/en/latest/detail.html?highlight=indentation#indentation-of-block-sequences)
        for guidance on the meaning of these parameters.

        All of these options can be overriden when calling `to_yaml()`.

        Args:
            mapping: Indentation delta between a parent mapping and its keys.
            sequence: Indentation delta between a parent sequence and a child sequence's contents.
            offset: Indentation delta between a parent and a child sequence's bullet points.
            sort_keys: Whether to sort mapping keys on output.
        """
        cfg = SystemUtils._yaml_config()
        cfg.indent(mapping=mapping, sequence=sequence, offset=offset)
        cfg.sort_base_mapping_type_on_output = sort_keys  # type: ignore

    @classmethod
    def serialize(cls, data: object, full: bool = False) -> Any:
        """Thin wrapper around `Typist.serialize()` -- see there for usage info.

        Examples:
            Reduce rich types to JSON-friendly forms::

                >>> from datetime import datetime, UTC
                >>> from my import ut
                >>> ut.serialize({3, 1, 2})
                [1, 2, 3]
                >>> ut.serialize(datetime(2026, 1, 1, tzinfo=UTC))
                '2026-01-01T00:00:00'
        """
        return cls.ty.serialize(data, full=full)

    # ---------
    # `4` SHELL
    # ---------
    @classmethod
    def _clean_shell_args(
        cls, args: tuple[str | Iterable[str], ...], kwargs: dict[str, Any]
    ) -> Generator[str]:
        """Flatten positional shell tokens and turn keyword arguments into CLI flags.

        Args:
            args: Positional tokens, each a string or an iterable of strings (one level of
                nesting is collapsed); each is further shlex-split.
            kwargs: Keyword arguments, turned into `-x`/`--xyz` flags. A `True` value yields a
                bare flag; a string value yields `flag value`; an iterable yields `flag v1
                flag v2 ...`; anything else is stringified.
        Yields:
            Individual shell tokens, ready to `shlex.join()`.
        """
        for arg in mi.collapse(args, base_type=str, levels=1):
            yield from filter(bool, shlex.split(str(arg).strip()))
        for key, val in kwargs.items():
            if not key.startswith('-'):
                key = f'-{key}' if len(key) == 1 else f'--{key}'

            if isinstance(val, bool) and val is True:
                yield key
            elif isinstance(val, str):
                yield from (key, val)
            elif isinstance(val, Iterable):
                yield from mi.flatten((key, str(v)) for v in val)
            else:
                yield from (key, str(val))

    @staticmethod
    def ex(
        *args: str | list[str],
        cwd: str | Path | None = None,
        **kwargs: Any,
    ) -> str | None:
        """Execute the given command as a shell-interpreted subprocess.

        Any exception (including a non-zero exit) is swallowed; a caller that needs to
        distinguish "failed" from "produced no output" should shell out directly instead.

        Args:
            *args: Command and arguments to execute. Can be multiple strings or lists of strings.
            cwd: Optional working directory to execute the command in.
            **kwargs: Additional keyword arguments that are parsed into command line options
                (see `_clean_shell_args()`).
        Returns:
            The stripped stdout (or stderr, if stdout was empty) on success, else None.
        Examples:
            Run a trivial command and capture its output::

                >>> from my import ut
                >>> ut.ex('echo', 'hi')
                'hi'
        """
        with ctx.suppress(Exception):
            result = sbp.run(
                shlex.join(SystemUtils._clean_shell_args(args, kwargs)),
                shell=True,
                capture_output=True,
                text=True,
                cwd=str(cwd) if cwd else None,
            )
            if result.returncode == 0:
                return (result.stdout or result.stderr).strip('\n').rstrip(' ')
        return None

    @classmethod
    def execute(cls, *args: str | list[str], **kwargs: Any) -> str | None:
        """Alias of `ex()`. Execute the given command as a shell-interpreted subprocess."""
        return cls.ex(*args, **kwargs)

    @staticmethod
    async def exa(
        *args: str | Iterable[str],
        cwd: str | Path | None = None,
        **kwargs: Any,
    ) -> str | None:
        """Execute the given command as a shell-interpreted subprocess, asynchronously.

        See `ex()` for the argument/return contract; this is its `asyncio` counterpart.

        Examples:
            >>> import asyncio
            >>> from my import ut
            >>> asyncio.run(ut.exa('echo', 'hi'))
            'hi'
        """
        with ctx.suppress(Exception):
            proc = await aio.create_subprocess_shell(
                shlex.join(SystemUtils._clean_shell_args(args, kwargs)),
                stdout=aio.subprocess.PIPE,
                stderr=aio.subprocess.PIPE,
                cwd=str(cwd) if cwd else None,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                return (stdout.decode() or stderr.decode()).strip('\n').rstrip(' ')
        return None

    @classmethod
    async def execute_async(cls, *args: str, **kwargs: Any) -> str | None:
        """Alias of `exa()`. Execute the given command as an async shell subprocess."""
        return await cls.exa(*args, **kwargs)


# `_configure_yaml()` is no longer called eagerly here: `_yaml_config()` applies the same
# defaults (4/6/4 indentation, unsorted keys) the first time any `to_yaml()` call builds the
# shared `CustomYaml` instance, keeping `srsly` out of the eager `import my` path.

system_utils = SystemUtils
"""An alias of `SystemUtils`, cased so as to imply static usage."""

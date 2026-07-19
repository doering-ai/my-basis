############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import Any, overload, TypeVar
from collections.abc import Collection, Sequence, Iterable, Generator
from datetime import datetime, timedelta, UTC
from pathlib import Path
from shutil import get_terminal_size
from typing import ClassVar
from unittest.mock import MagicMock
import functools as ft
import contextlib as ctx
import itertools as it
import subprocess as sbp
import sys
import textwrap
import os
import logging
import regex as re

# I/O
import pickle
import tomllib
import srsly
from srsly._yaml_api import CustomYaml
import tomli_w

### EXTERNAL
import pydantic as pyd
import more_itertools as mi

### INTERNAL (NOTE: If adding new internal imports, update the comments in `__init__.py`)
# Local imports
from ..infra.types import (
    Atom,
    Vec,
    Struct,
    String,
)
from ._UtilsBase import _UtilsBase
from .TextUtils import text_utils

# from typing import TYPE_CHECKING
# if TYPE_CHECKING:
#     from ..typing.Typist import Typist

############
### DATA ###
############
_branch = text_utils.multi_rgx

#: A sentinel value that communicates a failure of some kind, or an unininitialized register.
NOWHERE = Path()

# Misc aliases
File = pyd.FilePath
Directory = pyd.DirectoryPath

ClassType = TypeVar('ClassType')

FileParam = String | Path | None
RawJsonData = str | int | float | bool | list | dict | None

F = TypeVar('F', bound=Atom | Struct)
logger = logging.getLogger(__name__)


############
### BODY ###
############
class SystemUtils(_UtilsBase):
    """Methods that deal with low-level system resources & APIs."""

    AUTO_CONFIRM: ClassVar[bool] = False
    YAML_CONFIG: ClassVar[CustomYaml] = CustomYaml()
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
    )

    # ---------------
    # `0` DATE & TIME
    # ---------------
    @classmethod
    def posix(cls, val: int | float | datetime | None = None) -> datetime:
        """Convert a timestamp or datetime to UTC datetime.

        Args:
            val: Unix timestamp (int/float), datetime object, or None for current time.
        Returns:
            Timezone-aware datetime in UTC.
        """
        if val is None:
            return datetime.now(UTC)
        elif isinstance(val, datetime):
            return val.astimezone(UTC)
        else:
            return datetime.fromtimestamp(val, UTC)

    @classmethod
    def posix_since(cls, val: int | float | datetime | None = None) -> timedelta:
        """Calculate time elapsed since a given timestamp.

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
        """Validate that all provided paths are existing directories.

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
        """Validate that all provided paths are existing files.

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
        """Substitute a path component with a new value.

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
    @classmethod
    def get_terminal_width(cls) -> int:
        """Get the current terminal width in characters.

        Returns:
            Terminal width (defaults to 100 if unavailable).
        """
        return get_terminal_size((100, 100))[0]

    @classmethod
    def terminal_linewrap(cls, text: str, indent: int = 0) -> str:
        """Wrap text to fit within terminal width.

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
    def zsh_colorize(
        text: str,
        color: str,
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
    ) -> str:
        """Wrap text in zsh color codes with optional styles.

        Args:
            text: Text to colorize.
            color: Zsh color name or code.
            bold: If True, apply bold style (default: False).
            italic: If True, apply italic style (default: False).
            underline: If True, apply underline style (default: False).
        Returns:
            Colorized text with zsh codes, or original text if color is empty.
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
        """
        if SystemUtils.AUTO_CONFIRM:
            return True
        elif default_no:
            return not input(f'{prompt} [y/N] ').lower().strip().startswith('y')
        else:
            return not input(f'{prompt} [Y/n] ').lower().strip().startswith('n')

    @staticmethod
    def is_installed(*modules: str) -> bool:
        """Check if specified Python modules are installed."""
        try:
            for module in modules:
                __import__(module)
        except ImportError:
            return False
        return True

    @staticmethod
    def mock_if_uninstalled(target: str, *dependencies: str) -> bool:
        """Mock the target module if any of the specified dependencies are not installed."""
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
            Ideally a resolved version of that same path, else the same one.
        """
        return cls._path(str(raw or ''))

    @classmethod
    def log(cls, *args: Any, _level: int = 0, **kwargs: Any) -> None:
        """Log the provided collection of strings, applying common-sense transformations."""
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

    # --------
    # FILE I/O
    # --------
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
        """
        if not file:
            return tvar()  # type: ignore
        elif isinstance(file, Path):
            cls.validate_file(file)
            ret = srsly.read_json(file)
        elif (text := cls.ty.cast(file, str)) is not None:
            ret = srsly.json_loads(text)
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
        """Heuristic check for whether a string looks like a file path."""
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
        """Load data from YAML file or string, then cast to target type. See `from_file()`.

        Args:
            file: Path to the file to load, or raw YAML string/bytes.
            tvar: Target type to cast the loaded data to (dict by default). Like `cast()`, you
                  can use complex, nested types here if desired.
            cast: If False, data that doesn't match the expected return type raises an error.
        Returns:
            Loaded and cast data from the file/string.
        """
        # I. Parse the content using an external library
        if not file:
            # I.i. Empty case
            return tvar()  # type: ignore
        elif isinstance(file, Path):
            # I.ii. Local case: Read directly from file
            cls.validate_file(file)
            ret = srsly.read_yaml(file)
        else:
            # I.iii. Main Case: Attempt to parse in-memory YAML strings
            if isinstance(file, bytes):
                file = file.decode()
            if file.strip().startswith('```yaml'):
                file = '\n\n'.join(cls.RGXS['yaml'].findall(file))

            ret = srsly.yaml_loads(file)

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
        """
        tvar = cls.ty.specify(tvar)
        if not file:
            return tvar()  # type: ignore
        else:
            if isinstance(file, bytes):
                file = file.decode()
            ret = tomllib.loads(file)

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
        """
        if not file:
            return tvar()  # type: ignore
        else:
            if isinstance(file, str):
                file = file.encode()
            ret = pickle.loads(file)

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
        """
        obj = cls.ty.serialize(data)
        text = cls.YAML_CONFIG.dump(obj, **kwargs)
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
        """
        obj = cls.ty.serialize(data)
        if 'indent' not in kwargs:
            kwargs['indent'] = 4
        text = srsly.json_dumps(obj, **kwargs)

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
        """
        obj = cls.ty.serialize(data)

        # Cast to dict, as toml only accepts dicts at the top level
        if not isinstance(obj, dict):
            if isinstance(obj, Vec) and len(obj) == 1 and isinstance((_obj := mi.first(obj)), dict):
                obj = _obj
            else:
                obj = dict(content=obj)

        # II. Serialize w/ default params
        text = tomli_w.dumps(obj, **kwargs)

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
        """
        obj = cls.ty.serialize(data)
        return pickle.dumps(obj, **kwargs)

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
        cfg = SystemUtils.YAML_CONFIG
        cfg.indent(mapping=mapping, sequence=sequence, offset=offset)
        cfg.sort_base_mapping_type_on_output = sort_keys  # type: ignore

    @classmethod
    def serialize(cls, data: object, full: bool = False) -> Any:
        """Thin wrapper around `Typist.serialize()` -- see there for usage info."""
        return cls.ty.serialize(data, full=full)


# `_configure_yaml()` was never invoked, so `YAML_CONFIG` sat at ruamel's own defaults
# (alphabetically-sorted keys, 2-space indent) instead of this project's intended ones.
SystemUtils._configure_yaml()

system_utils = SystemUtils
"""An alias of `SystemUtils`, cased so as to imply static usage."""

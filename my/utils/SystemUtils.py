############
### HEAD ###
############
### STANDARD
from typing import Any
from collections.abc import Collection, Sequence, Iterable, Generator
from datetime import datetime, timedelta, UTC
from pathlib import Path
from shutil import get_terminal_size
from typing import ClassVar
from unittest.mock import MagicMock
import contextlib as ctx
import itertools as it
import subprocess as sbp
import sys
import textwrap

### EXTERNAL
import pydantic as pyd
import more_itertools as mi

### INTERNAL (NOTE: If adding new internal imports, update the comments in `__init__.py`)
from .TextUtils import text_utils


############
### BODY ###
############
class SystemUtils:
    """Methods that deal with low-level system resources & APIs."""

    AUTO_CONFIRM: ClassVar[bool] = False

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
            assert path and path.exists() and path.is_dir(), (
                f"Invalid directory: {path.as_posix()}"
            )
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
            assert path and path.exists() and path.is_file(), (
                f"Invalid file: {path.as_posix()}"
            )
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
            return text or ""

        # II. Wrap text in (relatively-fancy) zsh coloring syntax
        ret = f"%F{{{color}}}{text}%f"

        # III. Wrap result in universal ANSI codes for bold/italic/underline
        if bold:
            ret = f"\033[1m{ret}\033[22m"
        if italic:
            ret = f"\033[3m{ret}\033[23m"
        if underline:
            ret = f"\033[4m{ret}\033[24m"

        return ret

    @classmethod
    def print_in_color(cls, text: str, **kwargs: Any) -> None:
        """Print colored text using zsh prompt expansion.

        Note:
            Requires zsh to be available in the system PATH.

        Args:
            text: Text with zsh color codes already present.
            **kwargs: Additional arguments for `print()`.
        """
        ret = sbp.run(
            f"zsh -c 'print -P \"{text}\"'", capture_output=True, text=True, shell=True
        )
        print((ret.stdout or "").strip("\n"), **kwargs)

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
            return not input(f"{prompt} [y/N] ").lower().strip().startswith("y")
        else:
            return not input(f"{prompt} [Y/n] ").lower().strip().startswith("n")

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
        data: Collection[tuple | pyd.BaseModel | dict]
        | pyd.BaseModel
        | dict
        | Any
        | None,
        shorten: bool = False,
        depth: int = 0,
    ) -> Iterable[str]:
        """Internal method to recursively format nested data structures for `multiprint()`."""
        _in = "\t" * depth
        if data is None:
            return

        # I. Series
        elif isinstance(data, str):
            yield f"{_in}{textwrap.shorten(data, 64, placeholder='...')}"
            return
        elif isinstance(data, (set, Sequence)):
            if len(str(data)) < 32:
                yield f"{_in}{data}"
                return

            for item in data:
                for child_line in cls._multiprint_data(item, shorten, depth + 1):
                    if (
                        mi.ilen(it.takewhile(lambda s: s == "\t", child_line))
                        == depth + 1
                    ):
                        yield f"{_in}- {child_line.strip()}"
                    else:
                        yield f"  {child_line}"

        # II. Mappings
        elif isinstance(data, (dict, pyd.BaseModel)):
            if isinstance(data, pyd.BaseModel):
                data = data.model_dump(exclude_defaults=True)

            if len(str(data)) < 32:
                yield f"{_in}{data}"
                return

            for key, val in data.items():
                children = list(cls._multiprint_data(val, shorten, depth + 1))
                if len(children) == 1:
                    yield f"{_in}{key}: {children[0].strip()}"
                else:
                    yield f"{_in}{key}:"
                    yield from children

        # III. All Others
        elif isinstance(data, type):
            yield f"{_in}{data.__name__}"
        else:
            yield f"{_in}{data}"

    @classmethod
    def multiprint(
        cls,
        *items: Any,
        title: str = "",
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
            prefix = " " * indent
            for i in range(indent_range[0], (indent_range[1] or len(lines))):
                lines[i] = f"{prefix}{lines[i]}"

        # IV. Join the lines into a single result, and optionally print it to stdout if requested
        ret = ("\n" * margins[0]) + "\n".join(lines) + ("\n" * margins[1])
        if not quiet:
            print(ret, **kwargs)
        return ret

    @staticmethod
    @ctx.contextmanager
    def debug_fence(
        content: Any,
        mark: str = "-",
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
            pre = " " * indent
        else:
            pre = ""

        if not width or width <= 0:
            width = SystemUtils.get_terminal_width()

        mark = str(mark).strip()
        if not mark:
            mark = "-"
        delim = (mark * (width // len(mark) + 1))[:width]
        print(f"{pre}{delim}")
        if content:
            content = f" {content} "
            remaining = width - len(content)
            _halves = (remaining // 2, remaining // 2 + (1 if remaining % 2 else 0))
            left, right = tuple(
                (mark * (_half // len(mark) + 1))[:_half] for _half in _halves
            )
            print(f"{pre}{left}{content}{right}")
        yield
        print(f"{pre}{delim}")


system_utils = SystemUtils
"""An alias of `SystemUtils`, cased so as to imply static usage."""

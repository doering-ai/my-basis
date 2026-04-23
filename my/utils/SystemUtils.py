############
### HEAD ###
############
### STANDARD
from types import ModuleType
from datetime import datetime, timedelta, UTC
from pathlib import Path
from shutil import get_terminal_size
from typing import ClassVar
import sys
from unittest.mock import MagicMock
import subprocess as sbp
import textwrap

### EXTERNAL
import pydantic as pyd

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
    def print_in_color(cls, text: str, **kwargs) -> None:
        """Print colored text using zsh prompt expansion.

        Note:
            Requires zsh to be available in the system PATH.

        Args:
            text: Text with zsh color codes already present.
            **kwargs: Additional arguments for `print()`.
        """
        ret = sbp.run(f'zsh -c \'print -P "{text}"\'', capture_output=True, text=True, shell=True)
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


system_utils = SystemUtils
"""An alias of `SystemUtils`, cased so as to imply static usage."""

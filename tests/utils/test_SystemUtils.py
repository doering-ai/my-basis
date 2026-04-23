############
### HEAD ###
############
### STANDARD
from datetime import datetime, timedelta, UTC
from pathlib import Path

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.utils import SystemUtils

cls = SystemUtils


############
### BODY ###
############
class TestSystemUtils:
    """
    NOTE: The following tests are skipped as they require complex setup, external dependencies,
    or would cause side effects:

        - test_terminal_linewrap        (requires TextUtils)
        - test_confirm                  (requires user input)
        - test_print_in_color           (requires zsh subprocess)
    """

    # ---------------
    # `0` DATE & TIME
    # ---------------
    def test_posix_none(self):
        result = cls.posix(None)
        assert isinstance(result, datetime)
        assert result.tzinfo == UTC

    def test_posix_datetime(self):
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        result = cls.posix(dt)
        assert result == dt
        assert result.tzinfo == UTC

    def test_posix_timestamp(self):
        timestamp = 1704110400  # 2024-01-01 12:00:00 UTC
        result = cls.posix(timestamp)
        assert isinstance(result, datetime)
        assert result.tzinfo == UTC

    def test_posix_since(self):
        past = datetime.now(UTC) - timedelta(seconds=5)
        result = cls.posix_since(past)
        assert isinstance(result, timedelta)
        assert result.total_seconds() >= 4  # At least 4 seconds (allowing for execution time)

    def test_posix_since_none(self):
        assert cls.posix_since(None) == timedelta(0)
        assert cls.posix_since(0) == timedelta(0)

    # --------------
    # `1` FILESYSTEM
    # --------------
    def test_validate_dir(self, tmp_path):
        # Valid directory
        assert cls.validate_dir(tmp_path) is True

        # Invalid directory
        with pyt.raises(AssertionError, match='Invalid directory'):
            cls.validate_dir(tmp_path / 'nonexistent')

    def test_validate_file(self, tmp_path):
        # Create a temporary file
        test_file = tmp_path / 'test.txt'
        test_file.write_text('test')

        # Valid file
        assert cls.validate_file(test_file) is True

        # Invalid file
        with pyt.raises(AssertionError, match='Invalid file'):
            cls.validate_file(tmp_path / 'nonexistent.txt')

    @pyt.mark.parametrize(
        'path, old, new, expected',
        [
            (
                Path('/home/user/project/file.py'),
                'project',
                'myproject',
                Path('/home/user/myproject/file.py'),
            ),
            (Path('/a/b/c/d'), 'b', 'x', Path('/a/x/c/d')),
            (Path('/a/b/c'), 'd', 'x', Path('/a/b/c')),  # old not in path
            (Path('relative/path/file'), 'path', 'newpath', Path('relative/newpath/file')),
        ],
    )
    def test_path_sub(self, path: Path, old: str, new: str, expected: Path):
        assert cls.path_sub(path, old, new) == expected

    # ------------
    # `2` TERMINAL
    # ------------
    def test_get_terminal_width(self):
        width = cls.get_terminal_width()
        assert isinstance(width, int)
        assert width > 0

    def test_auto_confirm(self):
        original = cls.AUTO_CONFIRM
        try:
            cls.auto_confirm()
            assert cls.AUTO_CONFIRM is True
        finally:
            cls.AUTO_CONFIRM = original

    @pyt.mark.parametrize(
        'text, color, bold, italic, underline, contains',
        [
            ('Hello', 'red', False, False, False, '%F{red}Hello%f'),
            ('Bold', 'blue', True, False, False, '\033[1m'),  # ANSI code for bold
            ('Italic', 'green', False, True, False, '\033[3m'),  # ANSI code for italic
            ('Underline', 'yellow', False, False, True, '\033[4m'),  # ANSI code for underline
            ('', 'red', False, False, False, ''),  # Empty text
            ('Text', '', False, False, False, 'Text'),  # Empty color
        ],
    )
    def test_zsh_colorize(
        self, text: str, color: str, bold: bool, italic: bool, underline: bool, contains: str
    ):
        result = cls.zsh_colorize(text, color, bold, italic, underline)
        if contains:
            assert contains in result
        else:
            assert result == text or result == ''

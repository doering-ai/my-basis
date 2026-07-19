############
### HEAD ###
############
### STANDARD
from datetime import datetime, timedelta, UTC
from pathlib import Path
import logging
import pickle
from unittest.mock import MagicMock

### EXTERNAL
import pytest as pyt
import pydantic as pyd

### INTERNAL
from my.utils import SystemUtils

cls = SystemUtils


############
### DATA ###
############
class _ExampleModel(pyd.BaseModel):
    """A simple pydantic model for testing _multiprint_data."""

    name: str = 'test'
    count: int = 0


############
### BODY ###
############
class TestSystemUtils:
    """Test suite for SystemUtils."""

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

    def test_terminal_linewrap(self):
        """Test that terminal_linewrap wraps text to terminal width."""
        text = 'This is a test sentence that should be wrapped to the terminal width.'
        result = cls.terminal_linewrap(text)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_terminal_linewrap__with_indent(self):
        """Test terminal_linewrap with an indent value."""
        text = 'This is a test sentence that should be wrapped with an indent.'
        result = cls.terminal_linewrap(text, indent=10)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_print_in_color(self, patch, capsys):
        """Test print_in_color with a mocked subprocess."""
        mock_result = MagicMock()
        mock_result.stdout = 'colored text\n'
        patch.setattr('subprocess.run', lambda *a, **kw: mock_result)
        cls.print_in_color('test text')
        captured = capsys.readouterr()
        assert 'colored text' in captured.out

    def test_print_in_color__no_shell_injection(self, tmp_path):
        """A `$(...)` command substitution in `text` must NOT be executed by a shell.

        Regression test for a shell-injection RCE: `text` used to be interpolated directly
        into a `zsh -c '...'` string run with `shell=True`, so a value like
        `$(touch marker)` would execute the embedded command. It must now reach `print -P`
        purely as an argv value.
        """
        marker = tmp_path / 'marker'
        cls.print_in_color(f'$(touch {marker})')
        assert not marker.exists()

    def test_print_in_color__color_output_unchanged(self, capsys):
        """Normal zsh-colorized text still expands via `print -P` after the argv-based fix."""
        colored = cls.zsh_colorize('Hello', 'red')
        cls.print_in_color(colored)
        captured = capsys.readouterr()
        assert '\x1b[31m' in captured.out
        assert 'Hello' in captured.out

    # -------------------
    # `.` Confirm & Module
    # -------------------
    def test_confirm__auto_confirm(self):
        """Test that confirm returns True when AUTO_CONFIRM is enabled."""
        original = cls.AUTO_CONFIRM
        try:
            cls.AUTO_CONFIRM = True
            assert cls.confirm('Proceed?') is True
        finally:
            cls.AUTO_CONFIRM = original

    def test_confirm__yes_default_yes(self, patch):
        """Test confirm with default_no=False and user types 'y'."""
        patch.setattr('builtins.input', lambda *a: 'y')
        assert cls.confirm('Proceed?') is True

    def test_confirm__no_default_yes(self, patch):
        """Test confirm with default_no=False and user types 'n'."""
        patch.setattr('builtins.input', lambda *a: 'n')
        assert cls.confirm('Proceed?') is False

    def test_confirm__yes_default_no(self, patch):
        """Test confirm with default_no=True and user types 'y'."""
        patch.setattr('builtins.input', lambda *a: 'y')
        assert cls.confirm('Proceed?', default_no=True) is False

    def test_confirm__no_default_no(self, patch):
        """Test confirm with default_no=True and user types 'n'."""
        patch.setattr('builtins.input', lambda *a: 'n')
        assert cls.confirm('Proceed?', default_no=True) is True

    @pyt.mark.parametrize(
        'modules, expected',
        [
            (['os', 'sys'], True),
            (['json'], True),
            (['nonexistent_module_xyz'], False),
            (['os', 'nonexistent_module_xyz'], False),
        ],
    )
    def test_is_installed(self, modules: list[str], expected: bool):
        """Test is_installed with real and non-existent modules."""
        assert cls.is_installed(*modules) is expected

    def test_mock_if_uninstalled__installed(self):
        """Test mock_if_uninstalled returns True when deps are installed."""
        result = cls.mock_if_uninstalled('my.test.target', 'os', 'sys')
        assert result is True

    def test_mock_if_uninstalled__not_installed(self, patch):
        """Test mock_if_uninstalled mocks target when deps are missing."""
        import sys

        target = 'my.test.mock_target_xyz'
        # Clean up any prior entry
        sys.modules.pop(target, None)
        try:
            result = cls.mock_if_uninstalled(target, 'nonexistent_dep_xyz')
            assert result is False
            assert target in sys.modules
            assert isinstance(sys.modules[target], MagicMock)
        finally:
            sys.modules.pop(target, None)

    # -------------------
    # `+` Multiprint & Debug
    # -------------------
    @pyt.mark.parametrize(
        'data, expected',
        [
            (None, []),
            ('short string', ['short string']),
            ([1, 2], ['[1, 2]']),
            ({'a': 1}, ["{'a': 1}"]),
            (42, ['42']),
            (int, ['int']),
        ],
    )
    def test_multiprint_data__simple(self, data, expected: list[str]):
        """Test _multiprint_data with various simple data types."""
        result = list(cls._multiprint_data(data))
        assert result == expected

    def test_multiprint_data__long_string(self):
        """Test _multiprint_data shortens long strings."""
        long_text = 'a' * 100
        result = list(cls._multiprint_data(long_text))
        assert len(result) == 1
        assert '...' in result[0]
        assert len(result[0]) <= 64

    def test_multiprint_data__long_list(self):
        """Test _multiprint_data recursively formats long lists."""
        data = list(range(20))
        result = list(cls._multiprint_data(data))
        assert len(result) == 20
        # Each item should be prefixed with a dash
        assert result[0].startswith('- ')

    def test_multiprint_data__long_dict(self):
        """Test _multiprint_data recursively formats long dicts."""
        data = {f'key_{i}': f'val_{i}' for i in range(10)}
        result = list(cls._multiprint_data(data))
        # Should produce one line per key-value pair
        assert len(result) == 10
        assert 'key_0' in result[0]

    def test_multiprint_data__pydantic_model(self):
        """Test _multiprint_data handles pydantic BaseModel."""
        model = _ExampleModel(name='hello', count=5)
        result = list(cls._multiprint_data(model))
        assert len(result) > 0
        assert any('name' in line for line in result)

    def test_multiprint__basic(self):
        """Test multiprint returns a formatted string with items."""
        result = cls.multiprint('hello', 'world', quiet=True)
        assert 'hello' in result
        assert 'world' in result

    def test_multiprint__with_title(self):
        """Test multiprint includes a title with default indent."""
        result = cls.multiprint('content', title='My Title', quiet=True)
        assert 'My Title' in result
        # Title should be at the top
        lines = result.strip().split('\n')
        assert lines[0].strip() == 'My Title'

    def test_multiprint__with_indent(self):
        """Test multiprint applies indentation."""
        result = cls.multiprint('hello', indent=4, quiet=True)
        assert result.startswith('    hello')

    def test_multiprint__with_data(self):
        """Test multiprint formats data dict."""
        result = cls.multiprint(data={'key': 'value'}, quiet=True)
        assert 'key' in result
        assert 'value' in result

    def test_multiprint__with_lines(self):
        """Test multiprint includes additional lines."""
        result = cls.multiprint(lines=['extra1', 'extra2'], quiet=True)
        assert 'extra1' in result
        assert 'extra2' in result

    def test_multiprint__with_margins(self):
        """Test multiprint adds margin newlines."""
        result = cls.multiprint('hello', margins=(2, 3), quiet=True)
        assert result.startswith('\n\n')
        assert result.endswith('\n\n\n')

    def test_multiprint__quiet_no_print(self, capsys):
        """Test multiprint with quiet=True does not print to stdout."""
        cls.multiprint('hello', quiet=True)
        captured = capsys.readouterr()
        assert captured.out == ''

    def test_multiprint__prints_when_not_quiet(self, capsys):
        """Test multiprint prints to stdout when quiet=False."""
        cls.multiprint('hello', quiet=False)
        captured = capsys.readouterr()
        assert 'hello' in captured.out

    def test_debug_fence__with_content(self, capsys):
        """Test debug_fence prints fence with centered content."""
        with cls.debug_fence('Test', width=40):
            pass
        captured = capsys.readouterr()
        assert 'Test' in captured.out
        # Should have at least 3 lines: top fence, content, bottom fence
        lines = [line for line in captured.out.split('\n') if line]
        assert len(lines) >= 3

    def test_debug_fence__without_content(self, capsys):
        """Test debug_fence with empty content prints just fence lines."""
        with cls.debug_fence('', width=40):
            pass
        captured = capsys.readouterr()
        lines = [line for line in captured.out.split('\n') if line]
        # Only top and bottom fence, no content line
        assert len(lines) == 2

    def test_debug_fence__with_indent(self, capsys):
        """Test debug_fence with indent."""
        with cls.debug_fence('Test', width=40, indent=4):
            pass
        captured = capsys.readouterr()
        # Each line should be indented
        for line in captured.out.split('\n'):
            if line:
                assert line.startswith('    ')

    def test_debug_fence__custom_mark(self, capsys):
        """Test debug_fence with a custom mark character."""
        with cls.debug_fence('Test', mark='=', width=40):
            pass
        captured = capsys.readouterr()
        assert '=' in captured.out

    # ---------------
    # `*` Path & Logging
    # ---------------
    def test_path__empty(self):
        """Test path returns NOWHERE for empty input."""
        result = cls.path('')
        assert result == Path()

    def test_path__none(self):
        """Test path returns NOWHERE for None input."""
        result = cls.path(None)
        assert result == Path()

    def test_path__unexpanded_var(self):
        """Test path returns NOWHERE for unexpanded env vars."""
        result = cls.path('$NONEXISTENT_VAR_XYZ')
        assert result == Path()

    def test_path__absolute(self):
        """Test path resolves an absolute path."""
        cls._path.cache_clear()
        result = cls.path('/tmp')
        assert result.is_absolute()
        assert result.exists()

    def test_log(self):
        """Test log method executes without raising."""
        cls.log('test', 'message')

    def test_info(self):
        """Test info method logs at INFO level."""
        cls.info('info message', kwargs={})

    def test_error(self):
        """Test error method logs at ERROR level."""
        cls.error('error message', kwargs={})

    def test_warn(self):
        """Test warn method logs at WARNING level."""
        cls.warn('warn message', kwargs={})

    # --------------
    # `*2` File I/O
    # --------------
    def test_from_file__empty(self):
        """Test from_file raises ValueError for empty input."""
        with pyt.raises(ValueError, match='No file provided'):
            cls.from_file('')

    def test_from_file__nonexistent(self):
        """Test from_file raises ValueError for non-existent file."""
        with pyt.raises(ValueError, match='No/Invalid file'):
            cls.from_file('/tmp/nonexistent_file_xyz.json')

    def test_from_file__json(self, tmp_path):
        """Test from_file loads a JSON file."""
        cls._path.cache_clear()
        file = tmp_path / 'test.json'
        file.write_text('{"key": "value"}')
        result = cls.from_file(file)
        assert result == {'key': 'value'}

    def test_from_file__yaml(self, tmp_path):
        """Test from_file loads a YAML file."""
        cls._path.cache_clear()
        file = tmp_path / 'test.yaml'
        file.write_text('key: value\n')
        result = cls.from_file(file)
        assert result == {'key': 'value'}

    def test_from_file__unsupported_type(self, tmp_path):
        """Test from_file raises ValueError for unsupported file type."""
        cls._path.cache_clear()
        file = tmp_path / 'test.txt'
        file.write_text('hello')
        with pyt.raises(ValueError, match='Unsupported file type'):
            cls.from_file(file)

    def test_to_file__empty(self):
        """Test to_file does nothing when file is empty."""
        cls.to_file({'key': 'value'}, '')

    def test_to_file__json(self, tmp_path):
        """Test to_file saves data as JSON."""
        file = tmp_path / 'test.json'
        cls.to_file({'key': 'value'}, file)
        assert file.exists()
        import json

        assert json.loads(file.read_text()) == {'key': 'value'}

    def test_to_file__yaml(self, tmp_path):
        """Test to_file saves data as YAML."""
        file = tmp_path / 'test.yaml'
        cls.to_file({'key': 'value'}, file)
        assert file.exists()
        assert 'key' in file.read_text()

    def test_to_file__toml(self, tmp_path):
        """Test to_file saves data as TOML."""
        file = tmp_path / 'test.toml'
        cls.to_file({'key': 'value'}, file)
        assert file.exists()
        assert 'key' in file.read_text()

    def test_to_file__pickle(self, tmp_path):
        """Test to_file saves data as pickle."""
        file = tmp_path / 'test.pkl'
        cls.to_file({'key': 'value'}, file)
        assert file.exists()
        assert pickle.loads(file.read_bytes()) == {'key': 'value'}

    def test_to_file__str_path(self, tmp_path):
        """Test to_file accepts a string path."""
        file = str(tmp_path / 'test.json')
        cls.to_file({'key': 'value'}, file)
        assert Path(file).exists()

    def test_to_file__unsupported(self, tmp_path, caplog):
        """Test to_file logs error for unsupported file type."""
        file = tmp_path / 'test.txt'
        with caplog.at_level(logging.ERROR):
            cls.to_file({'key': 'value'}, file)
        assert any('Unsupported' in r.getMessage() for r in caplog.records)

    # ---------------
    # `*2` from_json
    # ---------------
    def test_from_json__empty(self):
        """Test from_json returns empty dict for empty input."""
        assert cls.from_json(None) == {}
        assert cls.from_json('') == {}

    def test_from_json__string(self):
        """Test from_json parses a JSON string."""
        result = cls.from_json('{"key": "value"}')
        assert result == {'key': 'value'}

    def test_from_json__from_file(self, tmp_path):
        """Test from_json reads from a file path."""
        file = tmp_path / 'test.json'
        file.write_text('{"key": "value"}')
        result = cls.from_json(file)
        assert result == {'key': 'value'}

    def test_from_json__cast_to_list(self):
        """Test from_json casts dict to list when cast=True."""
        result = cls.from_json('{"a": 1}', list, cast=True)
        assert result == ['a']

    def test_from_json__type_mismatch_no_cast(self):
        """Test from_json raises TypeError on type mismatch with cast=False."""
        with pyt.raises(TypeError, match='Expected'):
            cls.from_json('{"a": 1}', list, cast=False)

    def test_from_json__unsupported_type(self):
        """Test from_json raises ValueError for unsupported input type."""
        with pyt.raises(ValueError, match='Unsupported input type'):
            cls.from_json(object())

    # ---------------
    # `*2` is_pathy
    # ---------------
    @pyt.mark.parametrize(
        'text, expected',
        [
            ('/home/user/file.txt', True),
            ('~/Documents', True),
            ('../parent/dir', True),
            ('C:\\Users\\test', True),
            ('hello', False),
            ('abc', False),
            ('a' * 300, False),
        ],
    )
    def test_is_pathy(self, text: str, expected: bool):
        """Test is_pathy heuristic for path-like strings."""
        assert cls.is_pathy(text) is expected

    # ---------------
    # `*2` from_yaml
    # ---------------
    def test_from_yaml__empty(self):
        """Test from_yaml returns empty dict for empty input."""
        assert cls.from_yaml(None) == {}
        assert cls.from_yaml('') == {}

    def test_from_yaml__string(self):
        """Test from_yaml parses a YAML string."""
        result = cls.from_yaml('key: value\n')
        assert result == {'key': 'value'}

    def test_from_yaml__bytes(self):
        """Test from_yaml parses YAML bytes."""
        result = cls.from_yaml(b'key: value\n')
        assert result == {'key': 'value'}

    def test_from_yaml__from_file(self, tmp_path):
        """Test from_yaml reads from a file path."""
        file = tmp_path / 'test.yaml'
        file.write_text('key: value\n')
        result = cls.from_yaml(file)
        assert result == {'key': 'value'}

    def test_from_yaml__null_returns_empty(self):
        """Test from_yaml returns empty dict when YAML parses to None."""
        result = cls.from_yaml('null', dict)
        assert result == {}

    def test_from_yaml__type_mismatch_no_cast(self):
        """Test from_yaml raises TypeError on type mismatch with cast=False."""
        with pyt.raises(TypeError, match='Expected'):
            cls.from_yaml('key: value', list, cast=False)

    def test_from_yaml__cast_fails_raises_typeerror(self):
        """Test from_yaml raises TypeError when cast fails with ValueError."""
        with pyt.raises(TypeError, match='Expected'):
            cls.from_yaml('hello', int, cast=True)

    # ---------------
    # `*2` from_toml
    # ---------------
    def test_from_toml__empty(self):
        """Test from_toml returns empty dict for empty input."""
        assert cls.from_toml(None) == {}
        assert cls.from_toml('') == {}

    def test_from_toml__string(self):
        """Test from_toml parses a TOML string."""
        result = cls.from_toml('key = "value"\n')
        assert result == {'key': 'value'}

    def test_from_toml__bytes(self):
        """Test from_toml parses TOML bytes."""
        result = cls.from_toml(b'key = "value"\n')
        assert result == {'key': 'value'}

    def test_from_toml__cast_to_list(self):
        """Test from_toml casts dict to list when cast=True."""
        result = cls.from_toml('key = "value"', list, cast=True)
        assert result == ['key']

    def test_from_toml__type_mismatch_no_cast(self):
        """Test from_toml raises TypeError on type mismatch with cast=False."""
        with pyt.raises(TypeError, match='Expected'):
            cls.from_toml('key = "value"', list, cast=False)

    # ---------------
    # `*2` from_pickle
    # ---------------
    def test_from_pickle__empty(self):
        """Test from_pickle returns empty dict for empty input."""
        assert cls.from_pickle(None) == {}

    def test_from_pickle__bytes(self):
        """Test from_pickle loads from pickle bytes."""
        data = pickle.dumps({'key': 'value'})
        result = cls.from_pickle(data)
        assert result == {'key': 'value'}

    def test_from_pickle__string(self):
        """Test from_pickle loads from a protocol-0 pickle string."""
        data = pickle.dumps({'key': 'value'}, protocol=0)
        str_data = data.decode('ascii')
        result = cls.from_pickle(str_data)
        assert result == {'key': 'value'}

    def test_from_pickle__cast_to_list(self):
        """Test from_pickle casts dict to list when cast=True."""
        data = pickle.dumps({'a': 1})
        result = cls.from_pickle(data, list, cast=True)
        assert result == ['a']

    def test_from_pickle__type_mismatch_no_cast(self):
        """Test from_pickle raises TypeError on type mismatch with cast=False."""
        data = pickle.dumps({'a': 1})
        with pyt.raises(TypeError, match='Expected'):
            cls.from_pickle(data, list, cast=False)

    # ---------------
    # `*2` Serialization
    # ---------------
    def test_to_yaml__wrap(self):
        """Test to_yaml wraps output in markdown code block."""
        result = cls.to_yaml({'key': 'value'}, wrap=True)
        assert result.startswith('```yaml\n')
        assert result.endswith('```')

    def test_to_json__wrap(self):
        """Test to_json wraps output in markdown code block."""
        result = cls.to_json({'key': 'value'}, wrap=True)
        assert result.startswith('```json\n')
        assert result.endswith('```')

    def test_to_toml__dict(self):
        """Test to_toml serializes a dict."""
        result = cls.to_toml({'key': 'value'})
        assert 'key' in result
        assert 'value' in result

    def test_to_toml__non_dict_wraps_content(self):
        """Test to_toml wraps non-dict data in a content key."""
        result = cls.to_toml([1, 2, 3])
        assert 'content' in result

    def test_to_toml__wrap(self):
        """Test to_toml wraps output in markdown code block."""
        result = cls.to_toml({'key': 'value'}, wrap=True)
        assert result.startswith('```toml\n')
        assert result.endswith('```')

    def test_to_pickle(self):
        """Test to_pickle returns valid pickle bytes."""
        data = {'key': 'value'}
        result = cls.to_pickle(data)
        assert isinstance(result, bytes)
        assert pickle.loads(result) == data

    def test_serialize(self):
        """Test serialize is a thin wrapper around ty.serialize."""
        result = cls.serialize({'key': 'value'})
        assert result == {'key': 'value'}

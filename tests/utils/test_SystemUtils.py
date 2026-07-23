############
### HEAD ###
############
### STANDARD
from datetime import datetime, timedelta, timezone, UTC
from pathlib import Path
from typing import Any
import logging
import time
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

    @pyt.mark.parametrize(
        'value, expected',
        [
            (
                datetime(2024, 1, 1, 12, tzinfo=UTC),
                datetime(2024, 1, 1, 12, tzinfo=UTC),
            ),
            (
                datetime(2024, 1, 1, 12),
                datetime(2024, 1, 1, 12, tzinfo=UTC),
            ),
            (
                datetime(2024, 1, 1, 12, tzinfo=timezone(-timedelta(hours=5))),
                datetime(2024, 1, 1, 17, tzinfo=UTC),
            ),
        ],
    )
    def test_posix_datetime(self, patch, value: datetime, expected: datetime):
        """Test UTC normalization independently of the host's local timezone."""
        try:
            with patch.context() as local_patch:
                local_patch.setenv('TZ', 'America/New_York')
                time.tzset()
                assert cls.posix(value) == expected
        finally:
            time.tzset()

    def test_posix_timestamp(self):
        timestamp = 1704110400  # 2024-01-01 12:00:00 UTC
        result = cls.posix(timestamp)
        assert isinstance(result, datetime)
        assert result.tzinfo == UTC

    @pyt.mark.parametrize(
        'value, expected',
        [
            (None, timedelta(0)),
            (0, datetime(2024, 1, 2, tzinfo=UTC) - datetime.fromtimestamp(0, UTC)),
            (1704067200, timedelta(days=1)),
            (datetime(2024, 1, 1, tzinfo=UTC), timedelta(days=1)),
        ],
    )
    def test_posix_since(
        self,
        patch,
        value: int | datetime | None,
        expected: timedelta,
    ):
        """Test missing, epoch, timestamp, and datetime elapsed-time inputs."""
        now = datetime(2024, 1, 2, tzinfo=UTC)
        original_posix = cls.posix

        def fixed_posix(raw: int | datetime | None = None) -> datetime:
            return now if raw is None else original_posix(raw)

        patch.setattr(cls, 'posix', fixed_posix)
        assert cls.posix_since(value) == expected

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

    @pyt.mark.parametrize(
        'text, indent',
        [
            ('This is a test sentence that should be wrapped to the terminal width.', 0),
            ('This is a test sentence that should be wrapped with an indent.', 10),
        ],
    )
    def test_terminal_linewrap(self, text: str, indent: int):
        """Test terminal_linewrap with and without reserved indentation."""
        result = cls.terminal_linewrap(text, indent=indent)
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

    def test_print_in_color__no_shell_injection(self, patch, capsys):
        """Pass command substitutions to zsh as inert argv data, never shell source."""
        text = '$(touch should-not-run)'
        mock_result = MagicMock(stdout=f'{text}\n')
        mock_run = MagicMock(return_value=mock_result)
        patch.setattr('subprocess.run', mock_run)

        cls.print_in_color(text)

        mock_run.assert_called_once_with(
            ['zsh', '-c', 'print -P -- "$1"', 'zsh', text],
            capture_output=True,
            text=True,
            shell=False,
        )
        assert capsys.readouterr().out == f'{text}\n'

    def test_print_in_color__color_output_unchanged(self, patch, capsys):
        """Print zsh's rendered ANSI output unchanged after argv-based execution."""
        mock_result = MagicMock(stdout='\x1b[31mHello\x1b[39m\n')
        patch.setattr('subprocess.run', MagicMock(return_value=mock_result))

        colored = cls.zsh_colorize('Hello', 'red')
        assert colored == '%F{red}Hello%f'
        cls.print_in_color(colored)

        assert capsys.readouterr().out == '\x1b[31mHello\x1b[39m\n'

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

    @pyt.mark.parametrize(
        'answer, default_no, expected',
        [
            ('y', False, True),
            ('n', False, False),
            ('y', True, True),
            ('n', True, False),
            ('', True, False),
            ('', False, True),
        ],
    )
    def test_confirm(self, patch, answer: str, default_no: bool, expected: bool):
        """Test explicit answers and empty-input defaults."""
        patch.setattr('builtins.input', lambda *a: answer)
        assert cls.confirm('Proceed?', default_no=default_no) is expected

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
            ('a' * 100, ['...']),
            (list(range(20)), [f'- {i}' for i in range(20)]),
            (
                {f'key_{i}': f'val_{i}' for i in range(10)},
                [f'key_{i}: val_{i}' for i in range(10)],
            ),
            (_ExampleModel(name='hello', count=5), ["{'name': 'hello', 'count': 5}"]),
        ],
    )
    def test_multiprint_data(self, data: object, expected: list[str]):
        """Test concise, shortened, recursive, and model data formatting."""
        assert list(cls._multiprint_data(data)) == expected

    @pyt.mark.parametrize(
        'items, kwargs, expected',
        [
            (('hello', 'world'), {}, 'hello\nworld\n'),
            (('content',), {'title': 'My Title'}, 'My Title\n    content\n'),
            (('hello',), {'indent': 4}, '    hello\n'),
            ((), {'data': {'key': 'value'}}, "{'key': 'value'}\n"),
            ((), {'lines': ['extra1', 'extra2']}, 'extra1\nextra2\n'),
            (('hello',), {'margins': (2, 3)}, '\n\nhello\n\n\n'),
        ],
    )
    def test_multiprint(
        self,
        items: tuple[object, ...],
        kwargs: dict[str, Any],
        expected: str,
    ):
        """Test item, title, indentation, data, line, and margin formatting."""
        assert cls.multiprint(*items, quiet=True, **kwargs) == expected

    @pyt.mark.parametrize(
        'quiet, expected_stdout',
        [
            (True, ''),
            (False, 'hello\n\n'),
        ],
    )
    def test_multiprint__printing(self, capsys, quiet: bool, expected_stdout: str):
        """Test quiet and printing output modes."""
        assert cls.multiprint('hello', quiet=quiet) == 'hello\n'
        assert capsys.readouterr().out == expected_stdout

    @pyt.mark.parametrize(
        'content, kwargs, expected',
        [
            (
                'Test',
                {'width': 40},
                '----------------------------------------\n'
                '----------------- Test -----------------\n'
                '----------------------------------------\n',
            ),
            (
                '',
                {'width': 40},
                '----------------------------------------\n'
                '----------------------------------------\n',
            ),
            (
                'Test',
                {'width': 40, 'indent': 4},
                '    ------------------------------------\n'
                '    --------------- Test ---------------\n'
                '    ------------------------------------\n',
            ),
            (
                'Test',
                {'mark': '=', 'width': 40},
                '========================================\n'
                '================= Test =================\n'
                '========================================\n',
            ),
        ],
    )
    def test_debug_fence(
        self,
        capsys,
        content: str,
        kwargs: dict[str, Any],
        expected: str,
    ):
        """Test content, empty, indented, and custom-mark fences."""
        with cls.debug_fence(content, **kwargs):
            pass
        assert capsys.readouterr().out == expected

    # ---------------
    # `*` Path & Logging
    # ---------------
    @pyt.mark.parametrize(
        'raw, expected',
        [
            ('', Path()),
            (None, Path()),
            ('$NONEXISTENT_VAR_XYZ', Path()),
            ('/tmp', Path('/tmp')),
        ],
    )
    def test_path(self, raw: str | None, expected: Path):
        """Test sentinel-producing and absolute path resolution."""
        cls._path.cache_clear()
        assert cls.path(raw) == expected

    def test_log__materializes_message(self, caplog):
        """Test that loose arguments become a real message instead of a live map."""
        with caplog.at_level(logging.DEBUG):
            cls.log('hello', 'world', _level=logging.INFO)
        assert caplog.records[-1].getMessage() == 'hello world'

    @pyt.mark.parametrize(
        'method, level',
        [
            ('info', logging.INFO),
            ('error', logging.ERROR),
            ('warn', logging.WARNING),
        ],
    )
    def test_log_methods(self, caplog, method: str, level: int):
        """Test convenience loggers without an explicit kwargs argument."""
        with caplog.at_level(logging.DEBUG):
            getattr(cls, method)('message')
        assert caplog.records[-1].levelno == level
        assert caplog.records[-1].getMessage() == 'message'

    # --------------
    # `*2` File I/O
    # --------------
    @pyt.mark.parametrize(
        'file, message',
        [
            ('', 'No file provided'),
            ('/tmp/nonexistent_file_xyz.json', 'No/Invalid file'),
        ],
    )
    def test_from_file__invalid(self, file: str, message: str):
        """Test empty and nonexistent file rejection."""
        with pyt.raises(ValueError, match=message):
            cls.from_file(file)

    @pyt.mark.parametrize(
        'suffix, content',
        [
            ('.json', '{"key": "value"}'),
            ('.yaml', 'key: value\n'),
            ('.toml', 'key = "value"\n'),
            ('.pkl', pickle.dumps({'key': 'value'})),
        ],
    )
    def test_from_file(self, tmp_path, suffix: str, content: str | bytes):
        """Test loading every supported file format."""
        file = tmp_path / f'test{suffix}'
        if isinstance(content, bytes):
            file.write_bytes(content)
        else:
            file.write_text(content)
        cls._path.cache_clear()
        assert cls.from_file(file) == {'key': 'value'}

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

    @pyt.mark.parametrize(
        'suffix, as_string',
        [
            ('.json', False),
            ('.yaml', False),
            ('.toml', False),
            ('.pkl', False),
            ('.json', True),
        ],
    )
    def test_to_file(self, tmp_path, suffix: str, as_string: bool):
        """Test every supported format and both accepted path forms."""
        file = tmp_path / f'test{suffix}'
        destination = str(file) if as_string else file
        cls.to_file({'key': 'value'}, destination)
        assert file.exists()
        cls._path.cache_clear()
        assert cls.from_file(file) == {'key': 'value'}

    def test_to_file__unsupported(self, tmp_path, caplog):
        """Test to_file logs error for unsupported file type."""
        file = tmp_path / 'test.txt'
        with caplog.at_level(logging.ERROR):
            cls.to_file({'key': 'value'}, file)
        assert any('Unsupported' in r.getMessage() for r in caplog.records)

    # ---------------
    # `*2` from_json
    # ---------------
    @pyt.mark.parametrize(
        'content, as_file, tvar, cast, expected',
        [
            (None, False, dict, True, {}),
            ('', False, dict, True, {}),
            ('{"key": "value"}', False, dict, True, {'key': 'value'}),
            ('{"key": "value"}', True, dict, True, {'key': 'value'}),
            ('{"a": 1}', False, list, True, ['a']),
        ],
    )
    def test_from_json(
        self,
        tmp_path,
        content: str | None,
        as_file: bool,
        tvar: type[Any],
        cast: bool,
        expected: object,
    ):
        """Test empty, text, file, and casted JSON inputs."""
        source: str | Path | None = content
        if as_file:
            source = tmp_path / 'test.json'
            source.write_text(content or '')
        assert cls.from_json(source, tvar, cast=cast) == expected

    @pyt.mark.parametrize(
        'content, tvar, cast, error, message',
        [
            ('{"a": 1}', list, False, TypeError, 'Expected'),
            (object(), dict, True, ValueError, 'Unsupported input type'),
        ],
    )
    def test_from_json__invalid(
        self,
        content: object,
        tvar: type[Any],
        cast: bool,
        error: type[Exception],
        message: str,
    ):
        """Test type mismatches and unsupported runtime inputs."""
        with pyt.raises(error, match=message):
            cls.from_json(content, tvar, cast=cast)  # pyrefly: ignore[bad-argument-type]

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
    @pyt.mark.parametrize(
        'content, as_file, expected',
        [
            (None, False, {}),
            ('', False, {}),
            ('key: value\n', False, {'key': 'value'}),
            (b'key: value\n', False, {'key': 'value'}),
            ('key: value\n', True, {'key': 'value'}),
            ('null', False, {}),
            ('```yaml\nkey: value\n```', False, {'key': 'value'}),
            ('```yml\nkey: value\n```', False, {'key': 'value'}),
            ('  ``` YAML  \nkey: value\n```  \n', False, {'key': 'value'}),
            ('\t```  YmL\t\r\nkey: value\r\n```\t', False, {'key': 'value'}),
            (b'```YAML\nkey: value\n```', False, {'key': 'value'}),
            ('```yaml\n```', False, {}),
        ],
    )
    def test_from_yaml(
        self,
        tmp_path,
        content: str | bytes | None,
        as_file: bool,
        expected: object,
    ):
        """Test empty, text, bytes, file, and null YAML inputs."""
        source: str | bytes | Path | None = content
        if as_file:
            source = tmp_path / 'test.yaml'
            if isinstance(content, bytes):
                source.write_bytes(content)
            else:
                source.write_text(content or '')
        assert cls.from_yaml(source) == expected

    @pyt.mark.parametrize(
        'content, tvar, cast, error, message',
        [
            ('key: value', list, False, TypeError, 'Expected'),
            ('hello', int, True, TypeError, 'Expected'),
            ('```yaml\nkey: value', dict, True, ValueError, 'Invalid YAML fence'),
            ('```json\n{"key": "value"}\n```', dict, True, ValueError, 'Invalid YAML fence'),
            ('```yaml key: value```', dict, True, ValueError, 'Invalid YAML fence'),
            ('```yaml\nkey: value\n````', dict, True, ValueError, 'Invalid YAML fence'),
        ],
    )
    def test_from_yaml__invalid(
        self,
        content: str,
        tvar: type[Any],
        cast: bool,
        error: type[Exception],
        message: str,
    ):
        """Test type mismatches and malformed fenced YAML."""
        with pyt.raises(error, match=message):
            cls.from_yaml(content, tvar, cast=cast)

    # ---------------
    # `*2` from_toml
    # ---------------
    @pyt.mark.parametrize(
        'content, tvar, expected',
        [
            (None, dict, {}),
            ('', dict, {}),
            ('key = "value"\n', dict, {'key': 'value'}),
            (b'key = "value"\n', dict, {'key': 'value'}),
            ('key = "value"', list, ['key']),
        ],
    )
    def test_from_toml(self, content: str | bytes | None, tvar: type[Any], expected: object):
        """Test empty, text, bytes, and casted TOML inputs."""
        assert cls.from_toml(content, tvar, cast=True) == expected

    def test_from_toml__invalid(self):
        """Test rejecting a type mismatch when casting is disabled."""
        with pyt.raises(TypeError, match='Expected'):
            cls.from_toml('key = "value"', list, cast=False)

    # ---------------
    # `*2` from_pickle
    # ---------------
    @pyt.mark.parametrize(
        'data, tvar, expected',
        [
            (None, dict, {}),
            (pickle.dumps({'key': 'value'}), dict, {'key': 'value'}),
            (
                pickle.dumps({'key': 'value'}, protocol=0).decode('ascii'),
                dict,
                {'key': 'value'},
            ),
            (pickle.dumps({'a': 1}), list, ['a']),
        ],
    )
    def test_from_pickle(
        self,
        data: str | bytes | None,
        tvar: type[Any],
        expected: object,
    ):
        """Test empty, binary, protocol-zero text, and casted pickle inputs."""
        assert cls.from_pickle(data, tvar, cast=True) == expected

    def test_from_pickle__invalid(self):
        """Test rejecting a type mismatch when casting is disabled."""
        with pyt.raises(TypeError, match='Expected'):
            cls.from_pickle(pickle.dumps({'a': 1}), list, cast=False)

    # ---------------
    # `*2` Serialization
    # ---------------
    @pyt.mark.parametrize(
        'method, language',
        [
            ('to_yaml', 'yaml'),
            ('to_json', 'json'),
            ('to_toml', 'toml'),
        ],
    )
    def test_serializers__wrap(self, method: str, language: str):
        """Test markdown fencing for every text serializer."""
        result = getattr(cls, method)({'key': 'value'}, wrap=True)
        assert result.startswith(f'```{language}\n')
        assert result.endswith('```')

    @pyt.mark.parametrize(
        'data, expected',
        [
            ({'key': 'value'}, ('key', 'value')),
            ([1, 2, 3], ('content',)),
        ],
    )
    def test_to_toml(self, data: object, expected: tuple[str, ...]):
        """Test mapping serialization and non-mapping content wrapping."""
        result = cls.to_toml(data)
        assert all(fragment in result for fragment in expected)

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

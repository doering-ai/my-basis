############
### HEAD ###
############
### STANDARD
from typing import Any

### EXTERNAL
import pydantic as pyd
import pytest as pyt

### INTERNAL
from my.types import Command

############
### DATA ###
############
cls = Command


############
### BODY ###
############
class TestCommand:
    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyt.mark.parametrize(
        'command, args, kwargs, expected',
        [
            ('ls', [], {}, 'ls'),
            ('ls', ['/tmp'], {}, 'ls /tmp'),
            ('git', ['status'], {}, 'git status'),
            ('echo', ['hello world'], {}, 'echo "hello world"'),
            ('echo', ['hello', 'world'], {}, 'echo hello world'),
            ('ls', [], {'l': True}, 'ls -l'),
            ('ls', [], {'all': True}, 'ls --all'),
            ('git', ['commit'], {'m': 'test message'}, 'git -m "test message" commit'),
            ('pytest', [], {'verbose': True, 'cov': True}, 'pytest --verbose --cov'),
            (
                'cmd',
                [],
                dict(key_0='v0', options=dict(out='outfile.txt')),
                'cmd --key-0 v0 >> outfile.txt',
            ),
            (
                'cmd',
                ['v1'],
                dict(key_0='v0', options=dict(pipe='echo')),
                'cmd --key-0 v0 v1 | echo',
            ),
            (
                'cmd',
                ['v1'],
                dict(key_0='v0', options=dict(named_args_last=True)),
                'cmd v1 --key-0 v0',
            ),
            (
                'cmd',
                ['v1'],
                dict(key_0='v0', options=dict(single_dashes=True)),
                'cmd -key-0 v0 v1',
            ),
            (
                'cmd',
                ['v1'],
                dict(key_0='v0', options=dict(preserve_underscores=True)),
                'cmd --key_0 v0 v1',
            ),
            (
                'cmd',
                ['v1'],
                dict(key_0='v0', options=dict(flag_assignment=True)),
                'cmd --key-0=v0 v1',
            ),
        ],
    )
    def test_new(self, command: str, args: list[str], kwargs: dict, expected: str):
        cmd = cls.new(command, *args, **kwargs)
        assert cmd.assemble() == expected

    def test_validate_command(self):
        """Test that defining both out and pipe raises validation error."""
        with pyt.raises(pyd.ValidationError):
            cls.new(command='ls', options=dict(out='/tmp/out.txt', pipe=cls(command='grep')))

    # -------------------
    # `-` Private Methods
    # -------------------
    @pyt.mark.parametrize(
        'args, expected',
        [
            (['hello world'], ['"hello world"']),
            (['test'], ['test']),
            ([123], ['123']),
            ([3.14], ['3.14']),
            (['test', 123, 'hello world'], ['test', '123', '"hello world"']),
            (['already "\' quoted'], ['"already \\"\' quoted"']),
            ([], []),
        ],
    )
    def test_positional_args(self, args: list[Any], expected: list[str]):
        cmd = cls(command='test', args=args)
        assert cmd.positional_args == expected

    @pyt.mark.parametrize(
        'kwargs, expected',
        [
            # Boolean flags
            ({'verbose': True}, ['--verbose']),
            ({'v': True}, ['-v']),
            # Numeric values
            ({'count': 5}, ['--count 5']),
            ({'timeout': 3.5}, ['--timeout 3.5']),
            # String values
            ({'message': 'test'}, ['--message test']),
            ({'msg': 'hello world'}, ['--msg "hello world"']),
            # Underscore conversion
            ({'my_arg': 'value'}, ['--my-arg value']),
            # Mixed
            ({'v': True, 'count': 10}, ['-v', '--count 10']),
            # Values with quotes
            ({'msg': 'say "\'gday!"'}, ['--msg "say \\"\'gday!\\""']),
            ({'msg': "it's nice"}, ['--msg "it\'s nice"']),
            # Empty dict
            ({}, []),
        ],
    )
    def test_named_args(self, kwargs: dict[str, Any], expected: list[str]):
        cmd = cls(command='test', kwargs=kwargs)
        result = cmd.named_args
        # Sort both lists since dict ordering might vary
        assert sorted(result) == sorted(expected)

    # -------------------
    # `+` Primary Methods
    # -------------------
    @pyt.mark.parametrize(
        'command, args, kwargs, expected',
        [
            ('ls', [], {}, 'ls'),
            ('ls', ['/tmp'], {}, 'ls /tmp'),
            ('ls', [], {'l': True}, 'ls -l'),
            ('ls', ['/tmp'], {'l': True}, 'ls -l /tmp'),
            ('git', ['commit'], {'m': 'my message'}, 'git -m "my message" commit'),
            ('echo', ['hello', 'world'], {}, 'echo hello world'),
        ],
    )
    def test_assemble(self, command: str, args: list, kwargs: dict, expected: str):
        cmd = cls(command=command, args=args, kwargs=kwargs)
        assert cmd.assemble() == expected

    # ------------------
    # `*` Public Methods
    # ------------------
    def test_execute(self):
        """Test basic command execution."""
        cmd = cls.new('echo', 'hello')
        code, stdout, stderr = cmd.execute()
        assert code == 0
        assert 'hello' in stdout
        assert stderr == ''

    def test_execute__with_error(self):
        """Test command that produces stderr."""
        cmd = cls.new('ls', '/nonexistent_directory_12345')
        code, _, stderr = cmd.execute()
        assert code != 0
        assert stderr != ''

    @pyt.mark.asyncio
    async def test_execute_async(self):
        """Test async command execution."""
        cmd = cls.new('echo', 'hello async')
        code, stdout, stderr = await cmd.execute_async()
        assert code == 0
        assert 'hello async' in stdout
        assert stderr == ''

    @pyt.mark.asyncio
    async def test_execute_async__with_error(self):
        """Test async command with error."""
        cmd = cls.new('ls', '/nonexistent_directory_12345')
        code, _, stderr = await cmd.execute_async()
        assert code != 0
        assert stderr != ''

    @pyt.mark.asyncio
    async def test_call(self):
        """Test calling the command instance directly."""
        cmd = cls.new('echo', 'test call')
        code, stdout, _ = await cmd()
        assert code == 0
        assert 'test call' in stdout

    def test_run__classmethod(self):
        """Test the run classmethod convenience function."""
        code, stdout, stderr = cls.run('echo', 'test run')
        assert code == 0
        assert 'test run' in stdout
        assert stderr == ''

    @pyt.mark.asyncio
    async def test_run_async__classmethod(self):
        """Test the run_async classmethod convenience function."""
        code, stdout, stderr = await cls.run_async('echo', 'test run async')
        assert code == 0
        assert 'test run async' in stdout
        assert stderr == ''

    def test_run__with_flags(self):
        """Test run with keyword arguments converted to flags."""
        code, stdout, _ = cls.run('echo', 'test', n=True)
        assert code == 0
        # The -n flag prevents echo from adding a newline, but output should still contain 'test'
        assert 'test' in stdout

    # ----------------
    # Edge Cases Tests
    # ----------------
    def test_empty_command(self):
        """Test behavior with minimal command."""
        cmd = cls(command='pwd')
        result = cmd.assemble()
        assert result == 'pwd'
        code, stdout, _ = cmd.execute()
        assert code == 0
        assert stdout  # Should return current directory

    def test_complex_quoting(self):
        """Test handling of complex string quoting scenarios."""
        # String with both single and double quotes
        text = """It's a "complex" string"""
        cmd = cls.new('echo', text)
        code, stdout, _ = cmd.execute()
        assert code == 0
        assert stdout == text

    @pyt.mark.parametrize(
        'command, args, kwargs, options',
        [
            ('git', ['commit'], {'m': 'Initial commit'}, {}),
            ('pytest', [], {'verbose': True, 'cov': True, 'cov_report': 'html'}, {}),
            ('docker', ['run'], {'name': 'test', 'rm': True, 'd': True}, {}),
            ('curl', ['https://example.com'], {'output': 'file.txt', 'silent': True}, {}),
        ],
    )
    def test_real_world_commands(self, command: str, args: list, kwargs: dict, options: dict):
        """Test assembly of real-world command patterns."""
        cmd = cls.new(command, *args, **kwargs, **options)
        result = cmd.assemble()
        # Verify basic structure
        assert result.startswith(command)
        for arg in args:
            assert f'"{arg}"' in result or arg in result

    def test_model_serialization(self):
        """Test that Command can be serialized/deserialized as a Pydantic model."""
        cmd = cls.new('ls', '/tmp', l=True)
        # Serialize to dict
        data = cmd.model_dump()
        assert data['command'] == 'ls'
        assert data['args'] == ['/tmp']
        assert data['kwargs'] == {'l': True}

        # Deserialize from dict
        cmd2 = cls.model_validate(data)
        assert cmd2.assemble() == cmd.assemble()

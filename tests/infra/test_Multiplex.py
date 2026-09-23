"""Tests for the `Multiplex` tee writer, ported from mySublimeBasis (LIBS-62)."""

############
### HEAD ###
############
### STANDARD
from io import StringIO
import sys

### EXTERNAL

### INTERNAL
from my.infra.Multiplex import Multiplex, _Mode, _Stream


############
### BODY ###
############
class TestMode:
    """Tests for the ``_Mode`` enum."""

    def test_members(self):
        assert list(_Mode) == [_Mode.PASSIVE, _Mode.WRAPPER, _Mode.CONSUME]

    def test_ordering(self):
        assert _Mode.PASSIVE < _Mode.WRAPPER
        assert _Mode.WRAPPER < _Mode.CONSUME

    def test_lt_with_non_mode(self):
        assert not (_Mode.PASSIVE < 'string')

    def test_le_total_ordering(self):
        assert _Mode.PASSIVE <= _Mode.PASSIVE


class TestStream:
    """Tests for the ``_Stream`` NamedTuple."""

    def test_fields(self):
        s = _Stream(name='test', mode=_Mode.PASSIVE, root=StringIO())
        assert s.name == 'test'
        assert s.mode == _Mode.PASSIVE
        assert isinstance(s.root, StringIO)


class TestMultiplexSingleton:
    """Tests for the Multiplex singleton pattern."""

    def test_inst_returns_same_instance(self):
        m1 = Multiplex.inst()
        m2 = Multiplex.inst()
        assert m1 is m2

    def test_inst_is_multiplex(self):
        assert isinstance(Multiplex.inst(), Multiplex)


class TestMultiplexAddRemove:
    """Tests for add/remove/has/get."""

    def test_has_returns_false_for_nonexistent(self):
        assert not Multiplex.has('nonexistent_stream_xyz')

    def test_add_and_has(self):
        stream = StringIO()
        Multiplex.add('test_add_1', stream)
        assert Multiplex.has('test_add_1')
        # Cleanup
        Multiplex.remove('test_add_1')

    def test_get_returns_stream(self):
        stream = StringIO()
        Multiplex.add('test_get_1', stream)
        result = Multiplex.get('test_get_1')
        assert result is stream
        Multiplex.remove('test_get_1')

    def test_get_returns_none_for_nonexistent(self):
        assert Multiplex.get('nonexistent_xyz') is None

    def test_remove(self):
        stream = StringIO()
        Multiplex.add('test_remove_1', stream)
        assert Multiplex.has('test_remove_1')
        Multiplex.remove('test_remove_1')
        assert not Multiplex.has('test_remove_1')

    def test_remove_nonexistent_noop(self):
        # Should not raise
        Multiplex.remove('nonexistent_xyz_2')

    def test_add_duplicate_ignored(self):
        """Adding an existing name does not replace the stream."""
        stream1 = StringIO()
        stream2 = StringIO()
        Multiplex.add('test_dup_1', stream1)
        Multiplex.add('test_dup_1', stream2)
        assert Multiplex.get('test_dup_1') is stream1
        Multiplex.remove('test_dup_1')

    def test_add_with_string_mode(self):
        stream = StringIO()
        Multiplex.add('test_str_mode_1', stream, mode='CONSUME')
        assert Multiplex.has('test_str_mode_1')
        Multiplex.remove('test_str_mode_1')


class TestMultiplexWrite:
    """Tests for Multiplex.write and flush."""

    def setup_method(self, method):
        """Clear all streams before each test to ensure isolation."""
        m = Multiplex.inst()
        m._streams.clear()
        # Restore stdout if it was wrapped
        if type(sys.stdout).__name__ == 'Multiplex':
            sys.stdout = m.unwrap_stdout(sys.stdout)

    def teardown_method(self, method):
        """Clean up streams after each test."""
        m = Multiplex.inst()
        m._streams.clear()
        if type(sys.stdout).__name__ == 'Multiplex':
            sys.stdout = m.unwrap_stdout(sys.stdout)

    def test_write_to_passive_stream(self):
        stream = StringIO()
        Multiplex.add('test_write_1', stream, mode=_Mode.PASSIVE)
        m = Multiplex.inst()
        m.write('hello')
        assert stream.getvalue() == 'hello'

    def test_write_returns_length(self):
        stream = StringIO()
        Multiplex.add('test_write_2', stream, mode=_Mode.PASSIVE)
        m = Multiplex.inst()
        result = m.write('test')
        assert result == 4

    def test_consume_mode_suppresses_stdout(self):
        """When a CONSUME stream is active, the base stdout does not receive output."""
        stream = StringIO()
        Multiplex.add('test_consume_1', stream, mode=_Mode.CONSUME)
        m = Multiplex.inst()
        assert m.consume_stdout()

    def test_consume_mode_writes_to_consume_and_passive(self):
        """CONSUME active: CONSUME+PASSIVE get data, WRAPPER suppressed."""
        consume_stream = StringIO()
        passive_stream = StringIO()
        wrapper_stream = StringIO()
        Multiplex.add('test_consume_c', consume_stream, mode=_Mode.CONSUME)
        Multiplex.add('test_consume_p', passive_stream, mode=_Mode.PASSIVE)
        Multiplex.add('test_consume_w', wrapper_stream, mode=_Mode.WRAPPER)
        m = Multiplex.inst()
        m.write('test data')
        # CONSUME stream receives data
        assert consume_stream.getvalue() == 'test data'
        # PASSIVE stream also receives data (not suppressed by CONSUME)
        assert passive_stream.getvalue() == 'test data'
        # WRAPPER stream is suppressed when CONSUME is active
        assert wrapper_stream.getvalue() == ''

    def test_wrapper_mode_passes_through_when_no_consume(self):
        wrapper_stream = StringIO()
        Multiplex.add('test_wrapper_1', wrapper_stream, mode=_Mode.WRAPPER)
        m = Multiplex.inst()
        m.write('wrapper test')
        assert wrapper_stream.getvalue() == 'wrapper test'


class TestMultiplexUnwrap:
    """Tests for unwrap_stdout / unwrap_stderr."""

    def test_unwrap_stdout_with_plain_io(self):
        m = Multiplex.inst()
        io = StringIO()
        result = m.unwrap_stdout(io)
        assert result is io

    def test_unwrap_stdout_with_multiplex_instance(self):
        """Unwrap walks the chain of Multiplex instances to find the real stdout."""
        m = Multiplex.inst()
        # m._stdout should be a real TextIO, not a Multiplex
        result = m.unwrap_stdout(m)
        assert type(result).__name__ != 'Multiplex'

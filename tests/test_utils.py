############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from pathlib import Path
from typing import Any
import asyncio

### EXTERNAL

### INTERNAL
from myBasis.infra.utils import ut


############
### DATA ###
############
def _run(coro: Any) -> Any:
    """Run a coroutine synchronously."""
    return asyncio.run(coro)


############
### BODY ###
############
class TestCleanShellArgs:
    """Tests for ``Utils._clean_shell_args``."""

    def test_flattens_and_splits(self):
        result = list(ut._clean_shell_args(('git status', ['--short', '-b']), {}))
        assert result == ['git', 'status', '--short', '-b']

    def test_kwargs_become_flags(self):
        result = list(ut._clean_shell_args(('cmd',), {'v': True, 'depth': '2'}))
        assert result == ['cmd', '-v', '--depth', '2']

    def test_kwargs_iterable_values_repeat_flag(self):
        result = list(ut._clean_shell_args(('cmd',), {'opt': ['a', 'b']}))
        assert result == ['cmd', '--opt', 'a', '--opt', 'b']


class TestEx:
    """Tests for ``Utils.ex`` (sync subprocess wrapper)."""

    def test_basic_output(self):
        assert ut.ex('echo hello') == 'hello'

    def test_failure_returns_none(self):
        assert ut.ex('false') is None

    def test_cwd_is_applied(self, tmp_path: Path):
        """`cwd=` must change the subprocess working directory, not become a CLI flag."""
        assert ut.ex('pwd', cwd=tmp_path) == str(tmp_path.resolve())

    def test_cwd_not_leaked_into_argv(self, tmp_path: Path):
        """If cwd leaked through kwargs it would surface as a literal `--cwd` argument."""
        out = ut.ex('echo marker', cwd=tmp_path)
        assert out == 'marker'
        assert '--cwd' not in (out or '')


class TestExa:
    """Tests for ``Utils.exa`` (async subprocess wrapper)."""

    def test_basic_output(self):
        assert _run(ut.exa('echo hello')) == 'hello'

    def test_failure_returns_none(self):
        assert _run(ut.exa('false')) is None

    def test_cwd_is_applied(self, tmp_path: Path):
        """`cwd=` must change the subprocess working directory, not become a CLI flag."""
        assert _run(ut.exa('pwd', cwd=tmp_path)) == str(tmp_path.resolve())

    def test_cwd_not_leaked_into_argv(self, tmp_path: Path):
        out = _run(ut.exa('echo marker', cwd=tmp_path))
        assert out == 'marker'
        assert '--cwd' not in (out or '')

    def test_nonexistent_cwd_returns_none(self, tmp_path: Path):
        """An invalid cwd fails the subprocess launch and is swallowed to None."""
        assert _run(ut.exa('echo hello', cwd=tmp_path / 'missing')) is None


class TestExecuteAliases:
    """`execute`/`execute_async` forward to `ex`/`exa` including cwd."""

    def test_execute(self, tmp_path: Path):
        assert ut.execute('pwd', cwd=tmp_path) == str(tmp_path.resolve())

    def test_execute_async(self, tmp_path: Path):
        assert _run(ut.execute_async('pwd', cwd=tmp_path)) == str(tmp_path.resolve())

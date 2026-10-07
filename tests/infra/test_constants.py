"""Tests for the regex deadline setting in `my.infra.constants`."""

############
### HEAD ###
############
### STANDARD
import os
import subprocess
import sys
import textwrap

### EXTERNAL
import pytest as pyt

### INTERNAL
from my.infra.constants import regex_timeout

############
### DATA ###
############
VAR = 'MY_REGEX_TIMEOUT'

#: The modules that bind their own `REGEX_TIMEOUT`, in the order the scripts print them.
MODULES = ['my.infra.constants', 'my.types.Buffer', 'my.regex.RegexStore', 'my.apis.Filesystem']


def run_python(script: str, value: str | None) -> subprocess.CompletedProcess[str]:
    """Run `script` in a fresh interpreter, where the variable is `value` (or unset)."""
    env = {k: v for k, v in os.environ.items() if k != VAR}
    if value is not None:
        env[VAR] = value
    return subprocess.run(
        [sys.executable, '-c', textwrap.dedent(script)],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


############
### BODY ###
############
class TestRegexTimeout:
    @pyt.mark.parametrize(
        'value, expected',
        [
            (None, 10.0),
            ('2.5', 2.5),
            ('30', 30.0),
            (' 0.25 ', 0.25),
            ('1e3', 1000.0),
        ],
    )
    def test_regex_timeout(self, monkeypatch: pyt.MonkeyPatch, value: str | None, expected: float):
        if value is None:
            monkeypatch.delenv(VAR, raising=False)
        else:
            monkeypatch.setenv(VAR, value)
        assert regex_timeout() == expected

    @pyt.mark.parametrize('value', ['0', '-1', 'nan', 'inf', '-inf', 'abc', ''])
    def test_regex_timeout__invalid(self, monkeypatch: pyt.MonkeyPatch, value: str):
        monkeypatch.setenv(VAR, value)
        with pyt.raises(ValueError, match=VAR):
            regex_timeout()

    @pyt.mark.parametrize(
        'value, expected',
        [
            (None, 10.0),
            ('2.5', 2.5),
        ],
    )
    def test_modules__import_time(self, value: str | None, expected: float):
        """Each module that guards searches binds the one value, read when it is imported."""
        script = f"""
            import importlib
            for name in {MODULES!r}:
                print(importlib.import_module(name).REGEX_TIMEOUT)
        """
        done = run_python(script, value)
        assert done.returncode == 0, done.stderr
        assert done.stdout.split() == [str(expected)] * len(MODULES)

    def test_modules__invalid(self):
        """An invalid value stops the import of every module that would use it."""
        script = f"""
            import importlib
            for name in {MODULES!r}:
                try:
                    importlib.import_module(name)
                except ValueError as err:
                    print(name, 'MY_REGEX_TIMEOUT' in str(err))
                else:
                    print(name, 'imported')
        """
        done = run_python(script, 'abc')
        assert done.returncode == 0, done.stderr
        assert [line.split()[1] for line in done.stdout.splitlines()] == ['True'] * len(MODULES)

    def test_modules__catastrophic_pattern(self):
        """A short deadline from the variable still stops catastrophic backtracking."""
        script = """
            import regex
            from my.types.Buffer import Buffer
            try:
                list(Buffer.new('a' * 30 + '!').rgx_iterator(regex.compile(r'(a|a)+b')))
            except TimeoutError:
                print('timeout')
        """
        done = run_python(script, '0.2')
        assert done.returncode == 0, done.stderr
        assert done.stdout.split() == ['timeout']

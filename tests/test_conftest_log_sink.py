"""The test-log sink must not outlive the interpreter that made it (MEMY-1220)."""

############
### HEAD ###
############
### STANDARD
from __future__ import annotations

import subprocess as sbp
import sys
from pathlib import Path

### INTERNAL
from tests import conftest


############
### BODY ###
############
def test_log_sink_is_removed_at_interpreter_exit() -> None:
    """Importing the conftest must leave no directory behind once the process ends.

    `mkdtemp` -- unlike `TemporaryDirectory` -- never cleans up, so before the
    `atexit` hook every pytest session in this repo leaked one directory forever;
    107 were counted in /tmp on 2026-08-10. /tmp is tmpfs on the dev box, making
    those inodes RAM that no process kill reclaims.

    A subprocess is the only honest way to assert this: the hook fires at
    interpreter exit, which has not happened inside the running session. Note the
    sink is created at *import*, so this reproduces even with no tests collected.
    """
    probe = 'import tests.conftest as c; print(c.MY_LOGS)'
    result = sbp.run(
        [sys.executable, '-c', probe],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        # Under the suite's own `timeout = 15`, a 60s wait here could never fire: a hung
        # probe would be killed by pytest-timeout instead, reporting a stalled *test*
        # rather than a stalled subprocess. Staying under it keeps the error legible.
        timeout=10,
        check=True,
    )

    sink = Path(result.stdout.strip())
    assert sink.name.startswith('basis-test-logs-'), result.stdout
    assert not sink.exists(), f'{sink} survived interpreter exit'


def test_log_sink_exists_while_the_session_runs() -> None:
    """The cleanup must not be so eager that logging loses its sink mid-session."""
    assert conftest.MY_LOGS.is_dir()

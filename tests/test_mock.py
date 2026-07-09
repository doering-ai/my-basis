############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from pathlib import Path
import sys

### EXTERNAL
import pytest as pyt

### INTERNAL
import myBasis
from myBasis.infra import mock
from myBasis.infra.mock import _sublime


############
### BODY ###
############
class TestIsLive:
    """`IS_LIVE` must be True ONLY inside a real Sublime Text process."""

    def test_false_under_mocks(self):
        """The test suite runs on the mock modules, so IS_LIVE must report False."""
        assert mock.IS_LIVE is False

    def test_reexport_matches(self):
        assert myBasis.IS_LIVE is mock.IS_LIVE

    def test_mock_module_is_installed(self):
        """Sanity: sys.modules['sublime'] is the mock (external mode), not a live ST."""
        assert getattr(sys.modules['sublime'], 'MODE', 'internal') == 'external'

    def test_install_is_idempotent_and_keeps_is_live_false(self):
        """Re-running install() must neither crash nor flip IS_LIVE to True."""
        mock.install()
        mock.install()
        assert mock.IS_LIVE is False
        assert sys.modules['sublime'] is _sublime


class TestInferPaths:
    """Tests for ``mock._sublime.infer_paths`` root resolution.

    Path inference must never raise -- not even at import time, and not even when explicitly
    pointed at a nonexistent directory -- since `import myBasis` has to succeed in a bare Python
    env with no live SublimeText install (MEMY-60). Anything unresolvable degrades gracefully to a
    tmp directory instead, with a `UserWarning` so the situation is still visible.
    """

    def test_valid_st_root(self, tmp_path: Path, monkeypatch: pyt.MonkeyPatch):
        monkeypatch.setenv('ST_ROOT', str(tmp_path))
        _home, _cache, root = _sublime.infer_paths()
        assert root == tmp_path.resolve()

    def test_invalid_st_root_falls_back_to_tmp(self, tmp_path: Path, monkeypatch: pyt.MonkeyPatch):
        """A nonexistent $ST_ROOT must degrade to a tmp dir (with a warning), never raise."""
        monkeypatch.setenv('ST_ROOT', str(tmp_path / 'nonexistent'))
        with pyt.warns(UserWarning, match='root'):
            _home, _cache, root = _sublime.infer_paths()
        assert root != tmp_path / 'nonexistent'
        assert root.exists() and root.is_dir()

    def test_import_never_raises_with_no_st_env(self, monkeypatch: pyt.MonkeyPatch):
        """Nothing in path inference should require a live ST install or any $ST_* env var."""
        for envvar in ('ST_HOME', 'ST_PKGS', 'ST_CACHE', 'ST_ROOT'):
            monkeypatch.delenv(envvar, raising=False)
        home, cache, root = _sublime.infer_paths()
        assert all(p.exists() and p.is_dir() for p in (home, cache, root))
